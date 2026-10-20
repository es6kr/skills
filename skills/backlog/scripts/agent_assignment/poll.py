"""Strict GET-only cursor collection. No credential lookup or live client creation."""
from urllib.error import URLError
from urllib.parse import quote
from plane_client import PlaneError
from .model import Snapshot, ReadClient, normalize_states, normalize_issue
from contextlib import contextmanager
import os

class CycleBusy(Exception):
    pass

@contextmanager
def cycle_lock(path: str):
    """OS-owned nonblocking lock, held across fetch+apply. Never unlink it."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            # A stable first byte; concurrent writers write the same byte before locking.
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                import errno
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise CycleBusy('cycle_busy') from None
                raise
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CycleBusy('cycle_busy') from None
        locked = True
        yield
    finally:
        if locked:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def fetch_snapshot(client: ReadClient, config):
    prefix = f'workspaces/{config.workspace}/projects/{config.project_id}/'
    try:
        states = normalize_states(client.request(prefix + 'states/', method='GET'))
        cursor, visited, issues = '100:0:0', set(), {}
        for index in range(1000):
            if cursor in visited:
                raise ValueError('cursor_cycle')
            visited.add(cursor)
            page = client.request(prefix + 'issues/?cursor=' + quote(cursor, safe=':'), method='GET')
            if isinstance(page, list) and index == 0:
                rows, more, next_cursor = page, False, None
            elif isinstance(page, dict) and isinstance(page.get('results'), list) and type(page.get('next_page_results')) is bool:
                rows, more, next_cursor = page['results'], page['next_page_results'], page.get('next_cursor')
            else:
                raise ValueError('schema_error')
            for raw in rows:
                issue = normalize_issue(raw, config)
                if issue.state_id not in states:
                    raise ValueError('schema_error')
                if issue.id in issues and issues[issue.id] != issue:
                    raise ValueError('snapshot_conflict')
                issues[issue.id] = issue
            if not more:
                return Snapshot(tuple(issues.values()), states, True)
            if not isinstance(next_cursor, str) or not next_cursor:
                raise ValueError('schema_error')
            cursor = next_cursor
        raise ValueError('page_limit')
    except ValueError as exc:
        code = str(exc) if str(exc) in {'cursor_cycle', 'snapshot_conflict', 'page_limit', 'identity_mismatch', 'content_limit'} else 'schema_error'
    except (PlaneError, URLError, TimeoutError, RuntimeError):
        code = 'transport_error'
    return Snapshot((), {}, False, code)

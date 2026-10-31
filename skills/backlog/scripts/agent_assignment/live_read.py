"""Explicit-client GET port; no credential discovery or activation surface."""
from collections.abc import Mapping
from urllib.parse import parse_qsl, quote, urlsplit
from .model import Config, normalize_states


class ReadOnlyPlanePort:
    """Constrain an operator-supplied client, not authenticate its principal.

    The operator separately verifies credential/transport provenance. A matching
    profile is an origin check, never proof of human authorization.
    """
    def __init__(self, client, config):
        if type(config) is not Config or not callable(getattr(client, 'request', None)):
            raise ValueError('schema_error')
        self._client = client
        self._config = config
        self._prefix = f'workspaces/{config.workspace}/projects/{config.project_id}/'
        self._check_identity()

    def _check_identity(self):
        # GUARD: A mutable generic-client profile must not retarget a later page.
        self._config.__post_init__()
        profile = getattr(self._client, 'profile', None)
        if (not isinstance(profile, Mapping)
                or profile.get('plane_host') != self._config.host
                or profile.get('workspace_slug') != self._config.workspace):
            raise ValueError('identity_mismatch')

    def _get(self, path):
        self._check_identity()
        return self._client.request(path, method='GET')

    def request(self, path, method='GET', data=None):
        # GUARD: Read collection cannot write or select arbitrary endpoints.
        if method != 'GET' or data is not None:
            raise ValueError('read_only_required')
        if (not isinstance(path, str) or '#' in path
                or any(ord(char) < 32 or ord(char) == 127 for char in path)):
            raise ValueError('read_path_invalid')
        if path == self._prefix + 'states/':
            return self._states(path)
        parts = urlsplit(path)
        try:
            query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise ValueError('read_path_invalid') from None
        if (parts.scheme or parts.netloc or parts.path != self._prefix + 'issues/'
                or len(query) != 1 or query[0][0] != 'cursor' or not query[0][1]):
            raise ValueError('read_path_invalid')
        return self._get(path)

    def _states(self, path):
        rows, visited = [], set()
        for index in range(1000):
            page = self._get(path)
            if isinstance(page, list) and index == 0:
                rows = page
                break
            if (not isinstance(page, dict) or not isinstance(page.get('results'), list)
                    or type(page.get('next_page_results')) is not bool):
                raise ValueError('schema_error')
            rows.extend(page['results'])
            if not page['next_page_results']:
                break
            cursor = page.get('next_cursor')
            if not isinstance(cursor, str) or not cursor or cursor in visited:
                raise ValueError('schema_error')
            visited.add(cursor)
            path = self._prefix + 'states/?cursor=' + quote(cursor, safe=':')
        else:
            raise ValueError('page_limit')
        # GUARD: Never invent non-triage state or accept duplicate/unknown IDs.
        normalize_states(rows)
        return rows

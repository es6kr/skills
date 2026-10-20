#!/usr/bin/env python3
"""Offline-only Phase 1 collector. No live-read/dispatch/approval activation switch."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
from agent_assignment.model import Config, IdentityScope
from agent_assignment.poll import fetch_snapshot, cycle_lock, CycleBusy
from agent_assignment.ledger import Ledger
from agent_assignment.dispatch import DisabledReceiver, dispatch_one


class FixtureClient:
    """Synthetic GET port; never creates PlaneClient or reads environment secrets."""
    def __init__(self, data, config):
        self.prefix = f'workspaces/{config.workspace}/projects/{config.project_id}/'
        self.states = data['states']
        pages = data.get('pages')
        if pages is None:
            issues = data['issues']
            if not isinstance(issues, list):
                raise ValueError('schema_error')
            pages = [dict(results=issues, next_page_results=False)]
        if not isinstance(pages, list):
            raise ValueError('schema_error')
        self.pages = iter(pages)

    def request(self, path, method='GET', data=None):
        if method != 'GET' or data is not None:
            raise ValueError('schema_error')
        if path == self.prefix + 'states/':
            return self.states
        if not path.startswith(self.prefix + 'issues/?cursor='):
            raise ValueError('schema_error')
        try:
            return next(self.pages)
        except StopIteration:
            raise RuntimeError('fixture_transport_exhausted') from None


def unique_scope_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('schema_error')
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture')
    parser.add_argument('--scope-file')
    parser.add_argument('--db', required=True)
    parser.add_argument('--mode', default='collect-only')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args(argv)
    report = dict(mode=args.mode, complete=False, pending=0, error_code=None)
    code = 0
    if not args.fixture or args.mode != 'collect-only':
        report['error_code'], code = 'activation_required', 4
    elif not args.scope_file:
        report['error_code'], code = 'scope_required', 4
    else:
        try:
            # GUARD: Only this explicit trusted input supplies policy; never fixture config.
            scope_data = json.loads(Path(args.scope_file).read_text(encoding='utf-8'),
                                    object_pairs_hook=unique_scope_object)
            if not isinstance(scope_data, dict):
                raise ValueError('schema_error')
            scope = IdentityScope(**scope_data)
            # GUARD: Acquire before fixture fetch and hold through durable apply/recovery.
            with cycle_lock(str(Path(args.db).resolve().with_name('poll.lock'))):
                data = json.loads(Path(args.fixture).read_text(encoding='utf-8'))
                if not isinstance(data, dict) or not isinstance(data.get('config'), dict):
                    raise ValueError('schema_error')
                config = Config(**data['config'], scope=scope)
                client = FixtureClient(data, config)
                snapshot = fetch_snapshot(client, config)
                report['complete'], report['error_code'] = snapshot.complete, snapshot.error_code
                with Ledger(args.db) as ledger:
                    now = int(time.time())
                    if snapshot.complete:
                        ledger.recover(now)
                        ledger.apply(config, snapshot, now)
                        dispatch_one(ledger, DisabledReceiver(), now)
                    report['pending'] = len(ledger.pending())
                if not snapshot.complete:
                    code = 3 if snapshot.error_code in ('schema_error','identity_mismatch','content_limit','snapshot_conflict') else 2
        except CycleBusy:
            report['error_code'] = 'cycle_busy'
        except ValueError as exc:
            report['error_code'] = 'identity_mismatch' if str(exc) == 'identity_mismatch' else 'schema_error'
            code = 3
        except (TypeError, KeyError):
            report['error_code'], code = 'schema_error', 3
        except (OSError, sqlite3.Error):
            report['error_code'], code = 'storage_error', 3
    if args.report:
        print(json.dumps(report, separators=(',', ':')), file=sys.stderr)
    return code


if __name__ == '__main__':
    raise SystemExit(main())

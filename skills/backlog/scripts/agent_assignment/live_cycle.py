"""Explicitly injected collection/admission; no CLI, auth lookup, or scheduler."""
from pathlib import Path
import re
from .dispatch import DisabledReceiver, dispatch_one
from .ledger import Ledger
from .live_read import ReadOnlyPlanePort
from .model import Receipt, absolute_workspace
from .poll import CycleBusy, cycle_lock, fetch_snapshot


def _lock_path(ledger_path, now):
    # GUARD: Runtime storage and time must come from the trusted host, not issue data.
    if (not absolute_workspace(ledger_path) or type(now) is not int or now < 0):
        raise ValueError('schema_error')
    return str(Path(ledger_path).resolve().with_name('poll.lock'))


def collect_once(config, client, ledger_path, *, now):
    """Apply one complete snapshot. This function never admits a model run.

    pending=None means the ledger was not opened; it is not a claimed zero count.
    """
    lock = _lock_path(ledger_path, now)
    port = ReadOnlyPlanePort(client, config)
    try:
        with cycle_lock(lock):
            snapshot = fetch_snapshot(port, config)
            if not snapshot.complete:
                return dict(complete=False, pending=None, error_code=snapshot.error_code)
            with Ledger(ledger_path) as ledger:
                ledger.recover(now)
                ledger.apply(config, snapshot, now)
                return dict(complete=True, pending=len(ledger.pending()), error_code=None)
    except CycleBusy:
        return dict(complete=False, pending=None, error_code='cycle_busy')


def admit_pending_once(config, client, ledger_path, receiver, *, expected_outbox_id,
                       preflight, now):
    """Admit one exact operator-selected pending request after a fresh full scan.

    Host callbacks are trusted in-process ports, NOT authenticated approval inputs.
    They must be supplied by a separately authorized and verified operator adapter.
    """
    lock = _lock_path(ledger_path, now)
    if (not isinstance(expected_outbox_id, str)
            or not re.fullmatch(r'pa-[0-9a-f]{64}', expected_outbox_id)):
        raise ValueError('outbox_id_invalid')
    identity = getattr(receiver, 'identity_revision', None)
    # GUARD: Missing activation inputs leave even the local claim untouched.
    if (isinstance(receiver, DisabledReceiver) or not callable(preflight)
            or not isinstance(identity, str) or not identity.strip()):
        return 'disabled'
    port = ReadOnlyPlanePort(client, config)
    try:
        with cycle_lock(lock):
            snapshot = fetch_snapshot(port, config)
            if not snapshot.complete:
                return 'partial_snapshot'
            with Ledger(ledger_path) as ledger:
                ledger.recover(now)
                ledger.apply(config, snapshot, now)
                pending = ledger.pending()
                if not pending:
                    return 'idle'
                envelope = pending[0]
                if envelope.outbox_id != expected_outbox_id:
                    return 'candidate_mismatch'
                fresh = next((x for x in snapshot.issues if x.id == envelope.issue_id), None)
                if fresh is None or fresh.revision != envelope.content_revision:
                    return 'revision_changed'
                if envelope.workspace_path != config.repo:
                    return 'workspace_changed'
                try:
                    verified = preflight()
                except Exception:
                    return 'runtime_unverified'
                if verified != identity or getattr(receiver, 'identity_revision', None) != identity:
                    return 'runtime_unverified'
                # GUARD: Shared poll.lock spans candidate validation through admission.
                # This is not a transaction that fences external Plane edits.
                return dispatch_one(ledger, receiver, now)
    except CycleBusy:
        return 'cycle_busy'


def reconcile_known(ledger_path, receiver, *, outbox_id, now):
    """Resolve a stored uncertain admission using lookup only; never call submit."""
    lock = _lock_path(ledger_path, now)
    if not isinstance(outbox_id, str) or not re.fullmatch(r'pa-[0-9a-f]{64}', outbox_id):
        raise ValueError('outbox_id_invalid')
    if not Path(ledger_path).is_file():
        return 'unresolved'
    try:
        with cycle_lock(lock):
            with Ledger(ledger_path) as ledger:
                binding = ledger.delivery_binding(outbox_id)
                if binding is None:
                    return 'unresolved'
                if binding['status'] == 'delivered':
                    return 'delivered'
                if binding['status'] not in ('sending', 'delivery_uncertain'):
                    return 'not_reconcilable'
                identity = binding['receiver_identity_revision']
                if (not identity or getattr(receiver, 'identity_revision', None) != identity
                        or not callable(getattr(receiver, 'lookup', None))):
                    return 'runtime_unverified'
                ledger.recover(now)
                try:
                    receipt = receiver.lookup(outbox_id, binding['request_sha256'])
                    # GUARD: Even a valid receipt for ANOTHER outbox is not this query's result.
                    if (not isinstance(receipt, Receipt) or receipt.outbox_id != outbox_id
                            or receipt.request_sha256 != binding['request_sha256']
                            or receipt.receiver_identity_revision != identity
                            or getattr(receiver, 'identity_revision', None) != identity):
                        return 'unresolved'
                    ledger.record_receipt(receipt)
                except Exception:
                    # An unknown/failed GET is never permission for a new POST or key.
                    return 'unresolved'
                return 'delivered'
    except CycleBusy:
        return 'cycle_busy'

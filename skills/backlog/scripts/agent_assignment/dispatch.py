"""Offline orchestration. DisabledReceiver remains the default activation gate."""
from .model import Receiver

class ReceiverUnavailable(Exception):
    pass

class DeliveryUncertain(Exception):
    pass

class DisabledReceiver:
    def submit(self, envelope):
        raise ReceiverUnavailable('disabled')

    def lookup(self, outbox_id, request_sha256):
        return None


def dispatch_one(ledger, receiver: Receiver, now: int) -> str:
    # GUARD: Never claim or mark sending for the concrete disabled adapter.
    if isinstance(receiver, DisabledReceiver):
        return 'disabled'
    pending = ledger.pending()
    if not pending:
        return 'idle'
    identity = getattr(receiver, 'identity_revision', None)
    if not isinstance(identity, str) or not identity.strip():
        return 'disabled'
    envelope = ledger.claim(pending[0].outbox_id, now)
    if envelope is None:
        return 'idle'
    try:
        ledger.bind_receiver(envelope.outbox_id, identity)
        receipt = receiver.submit(envelope)
        if receipt.outbox_id != envelope.outbox_id:
            raise ValueError('receipt_mismatch')
        ledger.record_receipt(receipt)
    except Exception:
        # An exception/timeout is not proof that the remote side did not accept.
        with ledger.transaction():
            ledger._uncertain(envelope.outbox_id, now, 'delivery_uncertain')
        return 'delivery_uncertain'
    return 'delivered'

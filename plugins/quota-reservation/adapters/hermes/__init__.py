"""Thin native Hermes adapter; the portable package remains plugin.json-owned."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "quota_reservation_policy", PACKAGE / "lib" / "reservation.py")
_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_policy)


def make_consumer(*, settings, scheduler, state_dir, profile_home, runner_script, clock=None):
    return _policy.Consumer(settings=settings, scheduler=scheduler, state_dir=state_dir,
                            profile_home=profile_home, runner_script=runner_script, clock=clock)


def register(ctx):
    async def admitted(**incoming):
        # Resolve on EACH invocation, inside the host's routed profile context.
        # No process-global home/credential mutation and no model-facing scheduling tool.
        from hermes_constants import get_hermes_home
        from cron import jobs
        home = get_hermes_home().resolve()
        state = home / "quota-reservation"
        try:
            settings = _policy.read_json(state / "policy.json")
        except (OSError, ValueError):
            return None  # Missing operator policy means inactive, never implicit permission.
        with jobs.use_cron_store(home):
            consumer = make_consumer(
                settings=settings, scheduler=jobs, state_dir=state, profile_home=home,
                runner_script=home / "scripts" / "quota-reservation" / "first_use.py",
                clock=lambda: datetime.now(timezone.utc),
            )
            # The native dispatcher adds telemetry metadata; only the inspected
            # admission envelope participates in authorization or persisted state.
            envelope = {key: incoming[key] for key in
                        ("session_key", "platform", "source", "message_id", "text")}
            return await consumer(**envelope)
    ctx.register_hook("post_gateway_admission", admitted)

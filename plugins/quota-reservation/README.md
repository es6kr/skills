# Quota Reservation

An independently linkable **Agent Plugin v1**. Shared policy is in
`lib/reservation.py`; `adapters/hermes` is a separate native Python bridge.
There is deliberately no root `plugin.yaml`: native and portable discovery must
not be confused. Nothing here installs or enables either package automatically.

## Implemented source boundary

The native `post_gateway_admission` consumer receives the admitted original
`session_key`, `platform`, `source`, `message_id` and `text`. It handles only a
full, unquoted `agy Refreshes in <hours>h <minutes>m` notice from an explicitly
permitted sender and exact profile/origin. Either hours or minutes may be omitted.
Malformed or unsupported text is not a grant. Countdown minutes must be below 60,
and the supported horizon is at most 72 hours. The original Discord Snowflake,
not processing time, anchors the deadline. Execution is the next whole cron minute;
past deadlines are not rebased. This is minute scheduling, not a buffer.

A profile-local `quota-reservation/policy.json` supplies standing permission.
The example is deliberately disabled, with empty approval/users/origins. Policy
files must have no duplicate JSON keys. `allowed_origins` contains exact objects
with `platform`, `chat_id`, `thread_id`, `scope_id`; `allowed_user_ids` is separate.
A multiplex route resolves its home on every callback. Missing policy is inactive.
The policy file, ledger and request directories are operator-controlled state;
this is **not** a sandbox against another process with the same filesystem rights.
Windows ACL review belongs to the separately approved installation phase.

Before booking, a reviewed byte-identical `scripts/first_use.py` copy must exist
at the current profile's `scripts/quota-reservation/first_use.py`. The bridge never
copies it automatically and never weakens Hermes' script-containment guard.
The CLI must already exist at its absolute operator-configured path. A prepared
request pins that executable's bytes, profile home, OS user home, policy digest,
origin, original event identity, deadline and private working directory.

The consumer registers an enabled, unpinned `no_agent` one-shot directly through
the native cron store, then reads back the exact ID and all relevant fields. It
never modifies other jobs. A SQLite intent committed before submission prevents
blind retry after a crash/timeout. A single exact pre-existing result can be
reconciled; zero/ambiguous/mismatched results stay unknown. A changed body for the
same event identity cannot create a second job.

The standalone runner rechecks policy, deadline, executable and durable binding.
It atomically records submission before invoking the existing CLI/default route.
Only explicit non-secret OS bootstrap/login-directory environment keys survive;
API keys and provider/model overrides are not forwarded. It never logs raw CLI
output or authentication challenges. Only exit zero plus the exact JSON success,
one turn and expected response marker produces a verified response receipt.
Failure/timeout/unknown submission is never automatically retried. Policy change
or a five-minute expired execution window refuses execution, not a late restart.

The CLI prompt requests no tools; the CLI is **not** proved to enforce a tool-free
sandbox. Default-login identity, actual model/quota group, provider reset time,
installation, serving-Gateway reload and real first use require separate live
acceptance. Do not treat source tests as any of those receipts.

## Verification

From the repository root, run the two `tests/test_quota_reservation*.py` modules
with the project's installed pytest, or unittest discovery. They are standard
library tests with explicitly declared in-memory scheduler/CLI collaborators;
no real AGY inference or production scheduler changes are made.

`tests/native_probe.py` in this package is an explicit additional probe, not an
implicitly skipped unit test. It requires an installed Hermes source and its
Python environment, supplied as a command-line argument. It exercises the actual
native admission producer and native cron storage in a temporary profile, without
starting a Gateway/ticker or calling AGY. Preserve its evidence separately.

The portable manifest and bundled skill can be validated without installing the
package. Independent review, publication, installation, enabling, real booking
and provider execution remain separate approvals and evidence layers.

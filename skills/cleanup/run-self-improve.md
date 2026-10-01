# Step 2: Self-Improve (mistake analysis + review + pattern detection)

Step 2 of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 2: Self-Improve (Mistake Analysis + Review + Pattern Detection)

Analyze session mistakes, review hooks/skills, and detect patterns.

**Automated Script Execution**:
- Run `python <fa-skill-dir>/scripts/fa-analyze.py` (the script moved to the `fa` skill with FA lifecycle ownership) to audit the retrospect log's rules and status tags and surface recurring error classes. The log lives in a gitignored data store (`FA_DATA_DIR` resolvable — see fa/SKILL.md "FA data store"), so a fresh install will not have one — the script raises `FileNotFoundError` rather than skipping, so pass `--file` a log that exists.

[claudify/improve.md](../claudify/improve.md) — planned conversion to a `Skill("claudify", "improve")` call.
Currently the procedure below runs directly within cleanup.

Analyze the session's episodic data (mistakes, hook/skill behavior, repeated patterns) to improve the system.

### 2-A. Retrospect (mistake analysis)

Analyze mistakes made during the session and record them to feedback memory + failed-attempts.md.

**Procedure**: see [retrospect.md](../fa/retrospect.md) (owned by the `fa` skill — invoke via `Skill("fa")`) — in Step 6 (FA Prune), when any axis in [fa-prune.md](../fa/fa-prune.md) "Execution trigger (class-based)" fires, calling `Skill("fa", "fa-prune")` is **mandatory** (a text-only note is ❌). Do not restate a numeric threshold here: the flat section-count triggers are deprecated in favour of the class-count / hook-debt / stale-line axes, and a copy of the old number silently diverges from the source the moment it is tuned.

**Findings that imply future work must also reach the tracker (HARD STOP)**: the retrospect log records what went wrong; `fix_plan.md` records what will be done. When a finding's remediation is **not fully executed in this session** — a hook the escalation matrix now mandates, a trigger to register, a rule to strengthen, a defect to check elsewhere — register it as a `- [ ]` item in the tracker, in the same step. 2-C below already carries this obligation for pattern-detect candidates; retrospect findings carry it identically. Without the registration the remediation is invisible to the next session's backlog read, so the escalation the entry itself declares never runs.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Record the finding in the retrospect log and treat 2-A as complete | Also register the outstanding remediation as a tracker `- [ ]` item before closing 2-A |
| 2 | Turn "should we do this remediation?" into a user ask in place of registering it | Registration makes the work visible; it is not a request to run it now. Scheduling is a separate decision |
| 3 | Apply the registration obligation only to 2-C because that is where it is written | 2-A and 2-C are symmetric on this point — the medium differs, the obligation does not |

**Skip condition**: skip if there were no mistakes/corrections in the conversation. The tracker-registration obligation additionally skips when the remediation was fully executed this session (say so in the report) or the finding is purely descriptive.

### 2-B. Automation Review (hook + skill check)

#### Hook behavior review

1. Collect the registered hooks from the canonical inventory first — `Read` the registry at the private companion repo's `hook-registry.yaml` (relocated 2026-09-10; procedure: `hook-kit`'s `registry.md` redirect), then compare it against the live surfaces (`~/.claude/settings.json` `hooks`, each plugin's `hooks/hooks.json`). A settings.json entry whose id is already registered on a plugin surface is a dual registration to remove; a file with no registry row is a backfill candidate, not an orphan to re-point by guesswork
2. **Verify hook file existence**:
   - Extract the executable path from each hook's `command`
   - Check whether the file actually exists
   - **File missing → classify as a "phantom hook"**
3. Check each hook's session-behavior status:
   - Triggered + acted → "OK"
   - Triggered + **did not act** → "**Ignored**"
   - Triggered + errored → record the error content
   - Not triggered → "Not triggered"
   - File missing → "**Phantom**"
4. **Detect ignored hook output**: search for markers such as `<skill-trigger>`, `BUILD_COMPLETED`, `AUTO_AGENTIFY_CANDIDATE:`
5. If there were errors, see [hook-review.md](./hook-review.md)
6. **Summary report** (output immediately):

```
**Hook Behavior Summary**: 16 registered / 10 OK / 6 not triggered / 0 ignored / 0 errors
```

**Skip condition**: none — always run if even 1 hook is registered

#### Skill malfunction check

1. Collect the list of skills invoked via `Skill()` in the session
2. For each skill, check the Post-execution Self-heal checklist:
   - Did the trigger fire correctly?
   - Was the correct topic selected?
   - Was the procedure complete (no manual correction needed)?
   - Were there any missing pieces in the output?
3. Add any discovered malfunctions to **Phase 2 questions array**

##### Detecting non-auto-invoked / late-invoked domain skills (HARD STOP — the invoked-skills list alone is insufficient)

The above check only looks at **invoked skills**. However, a **domain skill that should have surfaced (or surfaced late) but didn't** is not on the invocation list, or is missed because it appeared late (a skill without registered `triggers:` doesn't even have a hook marker, making it invisible even in the hook behavior review). Cross-verify the session's work domain against domain-skill load timing.

**Procedure**:
1. Identify **domain work commands** in the session — `ssh <known-host>` / `docker`·`docker compose` / `curl <infra-endpoint>` / `terraform`·`semaphore`·`kubectl` / Portainer API, etc.
2. Map each domain to its **domain skill** (e.g., map infra hosts → an internal infra skill; k3s → `k3s`)
3. **Cross-verify load timing**: was that domain skill loaded (via Skill call or reading a topic) **before the first domain command**?
   - Loaded before the first command → OK
   - Loaded late after the command / loaded only because the user explicitly instructed it / never loaded at all + reverse-engineering was performed (reading ssh config directly, extracting env via `docker inspect`, searching port listeners) → classify as a **non-auto-invocation defect** and add to Phase 2 questions
4. **Recurrence classification**: if the same domain skill's non-auto-invocation is already recorded in failed-attempts.md, classify it as the Nth occurrence + escalate (rule → trigger registration → PreToolUse hook)

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Only self-heal-check the list of invoked skills and stop | Also detect "should have surfaced but didn't" domain skills via cross-referencing domain command vs load timing |
| 2 | Classify as "normal" just because the domain skill was invoked (even if late) | Late-invoke + preceding reverse-engineering = a defect. The criterion is whether it loaded before the first domain command |
| 3 | "No registered `triggers:` → no hook marker → not visible in the hook review, so it's missed" | A skill without a registered trigger has no marker = invisible. This step (based on work domain) separately detects it |

3. Add discovered malfunctions/non-auto-invocations to **Phase 2 questions array**

**Skip condition**: skip if there were no domain tasks (server SSH/docker/infra/deploy) at all and no invoked skills, or all invoked skills behaved normally

### 2-C. Pattern Detect (detect automation candidates)

> **TODO**: consolidate pattern-detection logic after absorbing auto-agentify.

**⚠️ Always run — do not skip**: do not judge candidate presence in advance.

1. Detect repeated patterns in the conversation context
2. Recommendation route by pattern type:

| Pattern type | Recommendation | Example |
|-----------|------|------|
| Repeated manual verification (same test repeated across multiple targets) | **Write test code** | An SSO callback test repeated across multiple deployment targets → write an E2E spec |
| Repeated workflow (same command sequence repeated) | **Create a skill/agent** (`/skill-kit route`) | A deploy pattern → deploy topic |
| Repeated rule application (same judgment manually made each time) | **Add a rule/hook** | Test Plan check before PR merge → hook |

3. On finding a candidate, **register it as an actual item in fix_plan.md** (HARD STOP):
   - Test code candidate → register `- [ ] Write test code: {target}` in fix_plan.md
   - Mappable to an existing rule/skill → propose upgrade in Phase 2
   - **New pattern that fits nowhere → call `/skill-kit route`** → auto-chaining (upgrade/writer)

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Write only in "next-action recommendation" text and stop | Register as a `- [ ]` item in fix_plan.md — convert into a trackable state |
| 2 | Conclude with "low frequency" | 3 repetitions is a sufficient frequency. Register with whichever of test code/skill/hook is appropriate |

4. Add the candidate to **Phase 2 questions array**

**Ralph mode**: 2-A~2-C all perform detection+recording only (`.ralph/improvements.md`). No direct modification.

---

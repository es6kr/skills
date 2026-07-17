# Background Polling

Mandatory active polling for long-running background work (HARD STOP).

**Immediately after dispatching a background task expected to take 5+ minutes, register a `ScheduleWakeup` or actively poll via `Monitor`.** Never sit idle until the user asks "is it done yet?".

## Notification / polling matrix by dispatch type

| Dispatch method | Automatic notification | Active polling required? |
|-----------------|------------------------|--------------------------|
| `Agent(run_in_background: true)` | ✅ task-notification on completion (but never arrives if the agent hangs) | ⚠️ Register ScheduleWakeup when 5+ min expected |
| `Bash(run_in_background: true)` (command includes a timeout) | ✅ task-notification on completion/failure | ⚠️ Register ScheduleWakeup when 5+ min expected |
| **`Bash(run_in_background: true)` (no timeout — HARD STOP)** | ❌ Never notified on hang (the tool `timeout` parameter does NOT apply to background) | **✅ `timeout N <cmd>` prefix in the command itself is mandatory. Without it, background dispatch is forbidden** |
| **Remote-host nohup detach (e.g. `ssh remote-host 'nohup ... &'`)** | ❌ No automatic notification | **✅ Required** — register `ScheduleWakeup` |
| **External-system async work (CI run, cloud deploy, etc.)** | Partial (`gh run watch` etc.) | **✅ Required** if no native watch |
| **User-triggered CI/deploy (user pushes a tag, runs manual workflow_dispatch, or fires an external trigger)** | ❌ No automatic notification | **✅ Required** — poll primary sources (`gh run list` / `gh release list`) immediately before composing the next response |

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Dispatch a nohup detach, then wait for the next user prompt | Register ScheduleWakeup right after dispatch (delay per the ScheduleWakeup delay guide below; for durations the table does not cover, fall back to 30-50% of the expected duration) |
| 2 | "It'll finish soon — I'll check on the next user prompt" | 5+ min work always gets a wakeup. Report proactively even if the user doesn't ask |
| 3 | Report only once at completion/failure with no interim status | Report progress at the 50% and 100% marks |
| 4 | Register a separate wakeup per background task (duplicates) | One wakeup keyed to the task that finishes last; check all tasks at that point |
| 5 | Receive "stopped by user" → immediately restart the same work directly | **Wait 30 seconds** — the agent process runs independently, so a completed notification can still arrive after "stopped". If it arrives, use that result. Retry directly only if nothing arrives within 30s |
| 6 | A stopped agent's result arrives late but duplicate work already started → ignore the result | Check the arrived result immediately and **stop the in-flight duplicate work** → switch to using the result |
| 7 | Classify work the user said they'd run themselves (tag push + CI, external dispatch) as "tracking ended" | User-triggered automatic workflows can finish within 5-10 min. Check state via primary sources (`gh run list` / `gh release list` / external API) **immediately before composing the next response**. Never assert "in progress" from quoting the user's last message |
| 8 | Call SSH/curl with `run_in_background: true` and no timeout options (relying on the tool `timeout` parameter) | The Bash tool `timeout` parameter is **foreground-only** (default 120s, max 600s). It does not apply to background → prefix the command itself with `timeout N <cmd>` (the Linux `timeout` utility). For SSH add `-o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3`; for curl add `-m 10` / `--max-time 10` |
| 9 | Wait unchecked until the next user prompt after a background dispatch | **5+ min expected** → periodic checks via ScheduleWakeup (or an equivalent active `Monitor` loop — the fallback when the harness lacks ScheduleWakeup). **10+ min** → both a command-level `timeout` and ScheduleWakeup |
| 10 | Wait for a task-notification on a hung background task (a command without timeout never sends one) | Prevent hangs via mandatory timeouts + kill any process with `ps` etime of 1 hour+ immediately (see row 11) |
| 11 | Run new commands while hung processes accumulate (PID pileup) | Right before every new background dispatch, scan the session's tracked background PIDs with `ps -o pid,etime,command -p <pid,...> \| awk 'NR==1 \|\| $2 ~ /-\|^[0-9]+:[0-9]{2}:[0-9]{2}$/'` for 1-hour+ processes (`etime` shows a `-` only at 1+ days; the second alternation catches hour-level). Report to the user + kill after confirmation — never sweep `ps -ax` system-wide into a kill decision |
| 12 | Register a wakeup, then sit idle in the main session while a background agent runs | A wakeup covers hang recovery — it does not license idling. Drive other drivable pending tasks in the same turn; idling past the 5-minute prompt-cache TTL makes the completion wake-up re-read the full context uncached |
| 13 | Chain two network operations (`git push && gh pr create`) under one short foreground timeout budget | One network op per Bash call — a mid-chain timeout kill (exit 143) leaves the first op's state ambiguous (pushed or not?). Size the timeout to the **slowest observed** environment: on hosts with known-slow shells (Windows Git Bash MSYS spawn + per-call hook overhead), give network ops (git push / gh api) an explicit 120-300s foreground timeout instead of the default feel |
| 14 | Escape a foreground timeout failure by re-dispatching the same command as background without a time bound | Background is not the fallback for "foreground timed out" — it drops the tool timeout entirely (row 8). Retry foreground with a larger explicit timeout first; go background only with a `timeout N` prefix + wakeup |

## ScheduleWakeup delay guide

| Expected duration | ScheduleWakeup delay (s) | Notes |
|-------------------|--------------------------|-------|
| 5-10 min | 270 (stays within prompt cache) | Short work |
| 10-30 min | 600-900 | Medium length |
| 30 min - 2 h | 1200-1800 | Long work, one cache miss |
| 2 h+ | 3600 | Long work, hourly checks |

## Self-check (immediately after every background dispatch)

1. **Timeout check (Bash run_in_background only)**: does the command start with a `timeout N <cmd>` prefix? — If not, do not dispatch; rewrite the command
   - If SSH is involved, also check `-o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3`
   - If curl is involved, check `-m 10` or `--max-time 10`
2. Which row of the matrix does the dispatch match? — Agent/Bash (with timeout) run_in_background auto-notify. External nohup / CI need active polling. Timeout-less background Bash is forbidden — rewrite the command per check 1 before dispatching
3. Is the expected duration 5+ minutes? — If yes, ScheduleWakeup (or an equivalent active `Monitor` loop) is mandatory
4. About to end the turn with just "background in progress"? — Ask yourself whether ScheduleWakeup was registered right before that
5. Multiple concurrent background tasks → one wakeup keyed to the latest-finishing task
6. **Stale-process scan**: right before a new background dispatch, check the session's tracked background PIDs for 1-hour+ processes with `ps -o pid,etime,command -p <pid,...> | awk 'NR==1 || $2 ~ /-|^[0-9]+:[0-9]{2}:[0-9]{2}$/'`. If found, report to the user and kill after confirmation
7. **Main-session utilization**: are other pending tasks drivable while the background work runs? Drive them in the same turn — an end-of-turn idle is acceptable only when nothing else is drivable

## Self-check (after user-delegated CI/deploy, immediately before every response)

1. Did the user delegate in the previous turn ("I'll push the tag and CI deploys", "I'll push it myself", "external trigger fired")?
2. Does the delegated work trigger an automatic workflow (GitHub Actions, GitLab CI, ArgoCD sync, etc.)?
3. Did you check state via primary sources (`gh run list` / `gh release list` / `kubectl get app`) immediately before composing the response? — If not, call now and fold in the result
4. About to write "in progress" or "waiting"? — Ask whether the basis is a primary source or a quote of the user's last message. The latter is a violation

## Bash tool timeout behavior spec (HARD STOP companion)

| Invocation | `timeout` parameter applies | Default | Max |
|------------|-----------------------------|---------|-----|
| Foreground (`run_in_background: false`) | ✅ Applies | 120000 ms (2 min) | 600000 ms (10 min) |
| Background (`run_in_background: true`) | **❌ Does not apply** | — | — |

→ The tool `timeout` parameter is meaningless for background calls. **A `timeout N <cmd>` prefix (the Linux `timeout(1)` utility) inside the command itself is mandatory.**

```bash
# ❌ Forbidden: background SSH without a timeout
Bash(command="ssh remote-host 'curl http://internal/api'", run_in_background=true)
# → hangs if curl never responds; SSH has no keepalive either. task-notification never arrives

# ✅ Recommended: timeout prefix + curl/ssh options
Bash(command="timeout 30 ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 remote-host 'curl -m 10 http://internal/api'", run_in_background=true)
# → force-terminated after 30s. task-notification arrives
```

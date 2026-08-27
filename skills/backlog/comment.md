# Topic: comment (Post a Comment onto a Plane Issue)

Attach follow-up notes — or a parent item's nested sub-findings — to an existing Plane
issue as **comments**, rather than creating separate sub-issues. This is the mechanism the
backlog-canonicalization flow uses to preserve a checklist item's nested sub-items (e.g. a
PR's individual review findings) under the single parent issue.

## When to Use

- Canonicalizing a `fix_plan.md` item whose body has nested checkbox sub-items: create one
  Plane issue for the top-level item, then post each nested sub-item as a comment.
- Adding a status update / follow-up note to an already-created issue.

## Execution

Resolve `BACKLOG_SCRIPTS` once per session:

```bash
for d in "${BACKLOG_SCRIPTS:-}" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/backlog/scripts" \
         "${AGENT_SKILLS_HOME:-$HOME/.agents}/skills/backlog/scripts" \
         "${GEMINI_SKILLS_HOME:-$HOME/.gemini/config}/skills/backlog/scripts"; do
  [ -n "$d" ] && [ -d "$d" ] && BACKLOG_SCRIPTS="$d" && break
done
```

```bash
python3 "$BACKLOG_SCRIPTS/plane_create_comment.py" \
  --issue <issue_uuid> --comment "text with **bold**, `code`, and [link](https://...)" --json
```

or read the comment body from a file (multi-line):

```bash
python3 "$BACKLOG_SCRIPTS/plane_create_comment.py" --issue <issue_uuid> --comment-file note.md --json
```

The script resolves the workspace/host/token from the active workspace profile
(`workspace_profile.py`) and auto-resolves the project UUID from the profile's
`default_project` identifier — pass `--project <uuid>` to override.

## Output Schema

```json
{ "success": true, "id": "<comment_uuid>", "issue": "<issue_uuid>",
  "project": "<project_uuid>",
  "url": "https://plane.es6.kr/es6kr/projects/<project_uuid>/issues/<issue_uuid>" }
```

## Correctness Notes (HARD STOP)

The Plane comment endpoint (`POST /issues/<id>/comments/`) validates the submitted
`comment_html`. Three failure modes bite bulk callers — the script handles all three, and a
hand-rolled caller MUST replicate them:

| # | Failure | Cause | Fix (already in script) |
|---|---------|-------|-------------------------|
| 1 | HTTP 400 `Invalid HTML passed` | Raw text containing `<`, `>`, `&` sent as `comment_html` | HTML-escape the text first, THEN re-apply only safe inline markup (link/bold/code) on the escaped string. Never send unescaped angle brackets |
| 2 | HTTP 403 `Forbidden` | Default `Python-urllib` User-Agent blocked by the Cloudflare edge in front of `plane.es6.kr` | Send a browser-like `User-Agent` header on every request |
| 3 | HTTP 429 `RATE_LIMIT_EXCEEDED` | Bulk posting faster than Plane's limiter allows | Space calls out (~0.4–0.6s) and retry 429/502/503 with linear backoff |

## Comment vs Sub-issue (design choice)

Nested sub-items are posted as **comments on the parent**, not as Plane sub-issues. This
keeps the board object count equal to the number of top-level backlog items while preserving
each sub-item's full text under its parent. Use sub-issues only when a nested item needs its
own independent lifecycle (assignee, state, cycle).

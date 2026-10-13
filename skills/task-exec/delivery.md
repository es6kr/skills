# Delivery Topic (`delivery.md`)

## 1. Unit Task Post-Execution & Commit Tidy (HARD STOP)

Upon verifying green implementation:
1. **Mandatory `commit-tidy` Invocation**: Group modifications into logical modification units. Stage and commit atomically using Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`). In-place existing-topic repairs use `fix`; a new topic uses `feat` under repository policy.
2. **Feature-Range Acceptance**: For created/relocated feature branches, run the
   existing feature-base gate supplied by the [git-repo owner](../git-repo/SKILL.md)
   ([feature-base gate](../git-repo/feature-base.md)) in `deliver` mode with the
   task's pinned base SHA, approved final commit count and explicit allowed paths.
   Require exit zero and retain the JSON receipt before reporting local source
   completion. Clean state alone or merge-base equality is not enough. If the owner
   gate is unavailable, report range admission as blocked; do not silently replace
   it with a completion claim. Runtime adapter activation, if in scope, requires
   separate native allow/block receipts; source/tests do not establish it.
3. **Completion State Separation**: Verified implementation, delivery, acceptance
   and canonical Done are separate. Report only the states actually established.
   Local-only authorization ends at reviewed local commits and evidence; it does
   not imply publication. Delegated tasks require the existing PM acceptance
   receipt bound to the current criterion/artifact evidence. Missing acceptance
   remains pending; successful tests or worker completion alone do not accept it.
4. **Canonical Owner Update**: Only after required verification, authorized
   delivery and explicit required acceptance, update the tracker through its
   existing owner helper under current mutation authority, then obtain exact
   read-back of the target task and state. If acceptance exists but the tracker
   mutation is unauthorized or unperformed, report accepted with canonical
   pending. Never fabricate canonical read-back or mark Done from green tests
   alone. Preserve all other tasks and owner statuses.
5. **Walkthrough / Knowledge Persistence**: Record criterion-bound evidence and
   remaining disposition in `.agents/docs/generated/walkthrough-*.md`; index into
   the existing knowledge owner only when in scope. Label source, static, offline
   and live evidence separately; do not promote historical evidence to a fresh run.

---

## 2. Pull Request Delivery

1. **Pre-Push Validation**: Confirm all applicable local pre-push checks
   (`bats tests/`, `pytest tests/`, `lint-frontmatter.sh`) pass. Report unavailable
   tooling or baseline failures accurately; do not claim unexecuted checks green.
2. **Authorization and Fresh Acceptance**: Re-run the same `deliver` gate
   immediately before publication. Push/PR/merge require their own existing task
   authority; local completion alone never grants it. Compare actual base..head
   paths and commits to accepted scope and type semantics; unrelated accumulated
   commits block delivery rather than being silently rewritten.
3. **Push Ref**: Push the feature branch to `origin` only within explicit scope.
4. **Create Pull Request**: Open a draft PR per Draft-to-PR gate with structured
   summary, test plan, and clear context (or use `github-flow/pr`). A draft, ready
   state, merge, release and canonical Done are independent; none substitutes for
   current acceptance evidence. Select the title type from the actual approved
   change: `feat` for a new topic, `fix` for an existing-topic repair.
   ```bash
   gh pr create --draft --title "<type>(<scope>): <description>" --body "..."
   ```

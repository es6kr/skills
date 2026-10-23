# Verify Topic (`verify.md`)

## 1. Physical Verification Gate (HARD STOP)

Never declare completion without running physical tests and inspecting empirical evidence:

1. **Execute Unit Tests**: Run BATS, pytest, or language-specific test suites.
2. **Inspect Empirical Output**: Confirm that all tests pass (`100% Green`) and that zero unexpected warnings or errors are reported.
3. **Regression Check**: Run the full workspace test suite (not just modified files) to ensure changes do not break downstream modules.
4. **Frontmatter & Style Linting**: Run `lint-frontmatter.sh` and `check-hangul.py` to ensure compliance with publishing standards.

## Criterion-Bound Completion Evidence

For every accepted criterion retain the following report projection of existing
owner contracts, not a new shared runtime schema:

| Fields | Required meaning |
|---|---|
| `original_goal`, `owner_scope`, `approved_revision/reference` | Original deliverable and accepted scope identity |
| `authorized_actions`, `next_unfinished_action`, `pending_decisions` | Continuing authority and remaining work |
| `criterion_id`, `artifact_revision/digest` | Exact criterion and evaluated artifact/source revision or digest |
| `evidence_kind`, `procedure`, `exit/outcome` | Observed check, full procedure/command and measured result |
| `observed_at`, `verifier` | Observation time and actual verifier identity |
| `acceptance_owner/receipt`, `canonical_readback` | Explicit acceptance and exact authoritative read-back, or pending/not performed |

Label source/static/offline/live evidence independently. Instruction conformance
is not agent behavioral proof; an offline fixture is not live adapter execution.
Historical evidence is not a fresh run. A changed artifact digest invalidates
prior verification and acceptance claims for that artifact, even if the plan
revision is unchanged. Collect current evidence before renewing those claims.

For any missing or failed criterion, report the verified subset and remaining
failures/blockers. Do not claim accepted or canonical Done for the incomplete
result. A submission receipt or started screen establishes submitted or started
only, not executed, verified or accepted. Use the existing acceptance owner;
tests, reports, or successful dispatch do not impersonate its explicit receipt.

# Verify Topic (`verify.md`)

## 1. Physical Verification Gate (HARD STOP)

Never declare completion without running physical tests and inspecting empirical evidence:

1. **Execute Unit Tests**: Run BATS, pytest, or language-specific test suites.
2. **Inspect Empirical Output**: Confirm that all tests pass (`100% Green`) and that zero unexpected warnings or errors are reported.
3. **Regression Check**: Run the full workspace test suite (not just modified files) to ensure changes do not break downstream modules.
4. **Frontmatter & Style Linting**: Run `lint-frontmatter.sh` and `check-hangul.py` to ensure compliance with publishing standards.

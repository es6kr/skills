# Verification Topic (`verify.md`)

## Evidence Before Assertions Gate

Before claiming any task is complete or passing:
1. Run project test commands (unit tests, integration tests, type checks).
2. Capture empirical exit codes and actual command output.
3. Print measured results before declaring success.

### Superpowers Integration
Delegates to `superpowers:verification-before-completion`.

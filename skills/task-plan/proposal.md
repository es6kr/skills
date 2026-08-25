# Proposal Topic (`proposal.md`)

## Organizational & Business Proposal Extension

When planning tasks targeting organizational stakeholders, management, or multi-departmental approval:

### 3-Stage Proposal Workflow
1. **Stage A: Derivative Document Authoring**:
   - `report-<slug>.md`: Executive 1~2 page summary.
   - `proposal-<slug>.md`: Problem, solution, ROI, and budget justification.
   - `slide-<slug>.md`: Marp/presentation deck outline.
   - `email-<slug>.md`: Decision/approval request email.

2. **Stage B: Decision-Maker Review & Tracking**:
   - Specify communication channel and feedback receipt point.
   - Register review wait state in backlog (`[PROPOSAL_FEEDBACK]`).

3. **Stage C: Approval Ledger & Execution Transition**:
   - Maintain approval history in Plan (`Approval Ledger` table).
   - Transition to `task-exec` only upon verified formal approval.

# Mail Adapter Topic (`mail.md`)

## 1. Scope

The `mail` adapter handles structured email composition, status briefings, and operational dispatch for non-coding workflows.

---

## 2. Dispatch Workflow

1. **Draft Generation**: Author the email draft as a structured markdown file (`email-draft-<subject>.md`).
   - Fields: `To`, `Cc`, `Subject`, `Body`.
2. **Review Gate**: Always present the email draft to the user for explicit confirmation before dispatching.
3. **Dispatch Integration**: Where CLI tooling (e.g. `himalaya`) is available, send or save to Drafts following user approval.

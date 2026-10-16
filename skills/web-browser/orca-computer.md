# Orca Computer Use (web-browser topic)

Drive the user's **real, already-signed-in desktop browser** through Orca's `orca computer`
commands (macOS accessibility + synthetic input). Use this when a task needs the user's actual
browser session, or when a site fingerprints and blocks automation-attached browsers
(see "CDP-hostile services" in [credential-issue.md](./credential-issue.md)).

This is a backend topic: [credential-issue.md](./credential-issue.md) and [ui-test.md](./ui-test.md)
decide *what* to do; this file covers *how to drive the browser* through `orca computer`.

## Why this backend exists

| Property | `orca computer` (real Chrome) | chrome-devtools-mcp / Playwright MCP |
|----------|-------------------------------|---------------------------------------|
| Browser instance | The user's own Chrome, normal profile, existing sign-ins | A separate automation-launched instance |
| Automation signal | No CDP attachment, no `navigator.webdriver` | CDP-attached — fingerprinted by bot-protected sites |
| Visibility | The user watches their own screen | Playwright window is invisible unless headed |
| DOM access | Accessibility tree only (no JS eval, no CSS selectors) | Full DOM / JS |

Consequence: it is the right tool for **sign-in and bot-challenge steps**, and the wrong tool for
bulk DOM work. Switch to a DOM-level backend once past the gate when the remaining steps allow it.

## Availability check (before choosing this backend)

1. Resolve the Orca CLI executable using the `orca` skill's rule (`ORCA_CLI_COMMAND`, then
   `orca-dev`, then `orca-ide` on Linux, else `orca`). Never run bare `orca` on Linux — it can resolve
   to a screen reader.
2. `orca status --json` → `result.app.running` must be true (otherwise `orca open --json`).
3. `orca computer capabilities --json` → confirms the provider (`orca-computer-use-macos`) and which
   actions it supports. **macOS only.**
4. `orca computer list-apps --json` → the browser's bundle id (e.g. `com.google.Chrome`) must be
   listed as running.

Do **not** conclude the capability is absent from an MCP tool search: this is a CLI, not an MCP
server. A zero-hit `ToolSearch` for "computer use" says nothing about `orca computer`.

Confirm current flags with `orca computer <command> --help` or `orca skills get orca-cli` — do not
rely on remembered flag names.

## Procedure

1. **Observe**: `orca computer get-app-state --app <bundleId> --restore-window --json`. Add
   `--no-screenshot` when the accessibility tree is enough. If it returns `window_not_found`, retry
   once with `--restore-window`.
2. **Act** with element indices from the *latest* snapshot (`click`, `set-value`) or with keyboard
   actions (`hotkey`, `press-key`, `type-text`, `paste-text`). Keyboard actions need the window
   focused — pass `--restore-window`.
3. **Re-observe after every action that can change the page.** Element indices are invalidated by
   navigation, scrolling, focus changes and delays (`element_not_found: ... changed since the last
   snapshot`). Never reuse an index across actions.
4. **Verify the result** from the next snapshot (URL field value, page title, field values). A
   `verification.state: unverified` on the action means "sent", not "took effect".

### Navigating to a URL

`hotkey cmd+l` (focus the address bar) → `type-text` the URL → `press-key Return`. Type the URL
rather than pasting it (see gotcha 3 below).

## Measured gotchas

| # | Situation | What happens | Do |
|---|-----------|--------------|-----|
| 1 | Segmented code inputs (GitHub device code, OTP boxes) | Typing the whole code in one call, or pasting it, lands the full string in the first box and corrupts the rest; the form then rejects it (`not_found`) | Type **one character per call**; the page auto-advances focus. Re-read the snapshot to confirm each box before `Continue` |
| 2 | `set-value` on an input | Sets the accessibility value but the page's input listeners never fire, so dependent buttons (e.g. `Continue`) stay disabled | Use real keystrokes for fields that gate a button. Reserve `set-value` for plain fields |
| 3 | `paste-text` | Pastes from the **system clipboard**, which the user also uses — a stale or concurrently changed clipboard pastes the wrong text | Prefer `type-text`. If you must paste, verify the destination field's value before submitting |
| 4 | Chrome autofill popup | Focusing a field can open an autofill suggestion list that appears in the tree and can shadow keystrokes | Dismiss with `Escape` before continuing, and re-check the field values |
| 5 | Query-string prefill (e.g. `?user_code=`) | Not honored on every service | Test once; if the fields stay empty, fall back to per-character entry |
| 6 | `get-app-state` size | Returns the entire tab strip on every call (large output) | Use `--no-screenshot`, and call it only when a decision needs the tree |
| 7 | Shared live window | The user may be typing in the same Chrome window at the same moment | Keep action sequences short; if a field shows text you did not enter, stop and ask rather than overwrite |
| 8 | Step-up authentication (e.g. GitHub "Confirm access" / sudo mode, passkey, mobile approval, emailed code) | Requires the account owner | Stop at that screen and hand off to the user; do not try to bypass, and do not read their email to obtain the code |

## Credential-screen capture rule still applies (HARD STOP)

`get-app-state` returns the accessibility tree, which renders input **values** — including
profile-autofilled passwords — in plaintext. The SKILL.md rule "capturing a credential-input screen
requires an explicit ask" therefore applies to every `get-app-state` / screenshot taken on a page
that accepts a password, token, secret or OTP. On such pages read only the URL and title first, and
ask before a fuller capture.

## Do / Don't

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip this backend because no MCP tool named "computer use" is loaded | Check `orca status` / `orca computer capabilities` — it is a CLI |
| 2 | Open an isolated Playwright window for a sign-in step and hand the login to the user when the user's real browser is drivable | Drive the user's own browser with `orca computer` and let them see it |
| 3 | Treat a successful `type-text`/`click` exit as success | Re-snapshot and check the resulting page state |
| 4 | Drive bulk data extraction through the accessibility tree | Use it for the gate (sign-in / challenge), then switch to a DOM-level backend if one is usable |
| 5 | Close or reload the user's tabs to "reset" state | Open a new tab (`hotkey cmd+t`) for your own navigation and leave the user's tabs alone |

## Relationship to other desktop-control tools

`orca computer` is the Orca runtime's own CLI. It is separate from any harness-provided desktop
control (such as `mcp__computer-use__*` tools): the two do not share access grants or tiers, and
this topic assumes only the Orca CLI.

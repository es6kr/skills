---
name: web-browser
metadata:
  author: es6kr
  version: "0.1.0"
description: |
  Environment-aware browser operations. Detects wmux/cmux/tmux and routes to backend. Topics — ui-test (snapshots, click/fill, shadow DOM), credential-issue (login via backend -> wait sign-in -> issue/refresh token/secret). Use when: "browser", "web-browser", "ui-test", "credential-issue", "playwright", "chrome-devtools", "UI check", "browser test", "screen verify", "Playwright test", "shadow DOM cascade", "::part not working", "CDP trace", "issue token", "service credential", "open login screen", "PAT refresh", "scope expansion", "device-code auth", "browser device-code", "GitHub social login".
---

# Web Browser

Environment-aware browser operations skill. Detects the runtime environment and routes to the
appropriate browser backend, then runs one of two workflows: UI testing/verification (`ui-test`) or
browser-login-assisted credential issuance (`credential-issue`).

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| ui-test | Snapshot analysis, click/fill/verify, page-state diagnosis | [ui-test.md](./ui-test.md) |
| cdp-trace | CDP-based closed shadow DOM cascade diagnosis (DOM.getDocument pierce:true + CSS.getMatchedStylesForNode) | [cdp-trace.md](./cdp-trace.md) |
| credential-issue | service+command param → open login screen → wait for user login → issue access key/token/secret → hand off to automation | [credential-issue.md](./credential-issue.md) |

## Topic Dependencies

```
web-browser (Step 0: environment detection — shared by all topics)
  ├─→ ui-test (UI verification)
  │     └─→ cdp-trace (extends ui-test for closed shadow DOM)
  └─→ credential-issue (browser-login-assisted token/key issuance)
        └─→ chrome-devtools backend preferred (reuses the user's real logged-in session)
```

- **Step 0 (below) is shared** — every topic detects the backend first, then runs its workflow.
- `ui-test`, `cdp-trace` are the UI-testing family.
- `credential-issue` reuses the same backend routing + the user-visibility rule, generalized into a
  service+command parameterized auth flow.
- **Authentik SSO verification** (`sso-verify`) is **not** included in this skill — it remains in a
  separate local-only `sso-verify` skill (user-environment specific, untracked).

## CRITICAL — capturing a credential-input screen requires an explicit ask (HARD STOP)

**Before capturing a sign-in / credential-input screen — accessibility snapshot, screenshot, or any
full page-content read — call `AskUserQuestion` and get explicit approval.** Applies to every topic
in this skill and to every backend.

The reason is not privacy etiquette, it is a measured leak path: a browser profile's saved-password
autofill populates the password field, and the accessibility tree renders that field's **value in
plaintext**. The capture therefore carries a live credential into the transcript even though nothing
was typed and no screenshot of characters was taken. `document.body.innerText` does not expose input
values, but the accessibility snapshot does.

| # | Don't | Do |
|---|-------|-----|
| 1 | Snapshot a sign-in page to "see what step we're on" | Read only `location.href` and `document.title`, or specific marker booleans. Ask before any fuller capture |
| 2 | Assume an empty-looking form is safe because you typed nothing | Profile autofill fills fields without any typing. Emptiness is not verifiable before the capture that would leak it |
| 3 | Redact only the field you expected to carry the secret | Apply redaction to **every** returned field — element text, `aria-label`, `title`, `placeholder`, `value`. A secret leaked through an unredacted sibling field is the common failure |
| 4 | Return page values when a count or boolean answers the question | Prefer structure over content: `hasPasswordField: true`, `blockMarkers: {...}`, `buttonCount: 3` |
| 5 | Treat "the user asked me to test the login" as approval to capture the screen | Testing the flow and capturing the credential screen are separate permissions. Ask for the second one explicitly |

**Self-check (before every snapshot / screenshot / full-text read)**: does the current page accept a
password, token, secret, or OTP? → If yes, or if unsure, restrict to URL + title and ask before
capturing more.

## CRITICAL — user visibility is the top priority (HARD STOP)

**The primary purpose of browser diagnosis/verification is "the user sees it on their own screen"**. Screenshot capture is **supporting evidence**, not a substitute for visibility.

| # | Don't | Do |
|---|-------|-----|
| 1 | Launch with `chromium.launch({ headless: true })` and only attach a screenshot in chat | `chromium.launch({ headless: false, slowMo: 500 })` — let the user follow in real time |
| 2 | "I showed the user a screenshot, so it's fine" | screenshot ≠ visible to the user. If the user says "show me", open a visible browser + slowMo |
| 3 | wmux/cmux/Playwright MCP disconnected → fall back to headless CLI | Even on CLI fallback, force `headless: false`. On a Windows desktop OS, a chromium GUI is available |
| 4 | "headless is faster and more stable by default" mindset | Speed costs user visibility. If the user says "show me", visibility wins |
| 5 | Playwright MCP disconnected → CLI fallback auto-selects headless | CLI fallback is also `headless: false`. headless is only for explicit non-interactive cases (e.g., CI assertion) |
| 6 | SaaS/API task lacks credentials → fallback to manual user UI operation | Do NOT recommend manual user UI clicking when API access is available; fallback to `credential-issue` topic to issue token/key first |

## API-capable environment without credentials — fallback to credential-issue (HARD STOP)

**When a task can be performed via API (e.g., Google Forms API, GitHub API, AWS API), but required API tokens or access keys are missing in the environment, do NOT recommend manual user UI clicking or surrender to direct manual UI operation.** You MUST recommend `credential-issue` topic to issue the access key/token via browser login first, then proceed with backend API automation.

| # | Don't | Do |
|---|-------|----|
| 1 | API token missing → "Please edit/click manually on the website" | Recommend `credential-issue` topic to issue API token/key via browser login |
| 2 | Direct UI automation fails → fallback to manual user operation | Check if API automation is available → issue credential via `credential-issue` → execute API |

### Self-check (every time before launching Playwright/chromium)

1. Did the user use a visibility request keyword such as "show me", "open it", "web-browser", or "browser test"? → If yes, force `headless: false`
2. Is this work interactive verification or diagnosis for the user? → If yes, `headless: false`
3. headless is justified only when (a) CI assertion (b) the user explicitly said "in headless" (c) Playwright MCP is used (the UI shows itself)
4. screenshot is supporting evidence — it can be attached to a chat report, but it does not replace user visibility

### Violation case (2026-05-28, 1st)

During a closed shadow DOM `ak-library` cascade investigation, used a `npx playwright` Bash invocation + `chromium.launch({ headless: true })` and only attached a screenshot in chat. The user requested "show it via web-ui-test" and no visible browser was provided. The user reacted angrily that the Chromium UI never appeared.

## Login wall mid-capture — ask before stopping, don't silently defer (HARD STOP)

**When a capture/documentation task (report evidence, purchase/registration flow guide, etc.) hits a screen that requires login, and completing that login would reveal materially different information than what's already captured (e.g., the real final price vs. a promotional pre-login price, actual post-login UI state vs. an assumption), do NOT silently stop and paper over the gap with a deferral disclaimer.** Ask the user via `AskUserQuestion` whether to continue (via interactive login in a visible backend) or whether the pre-login capture is sufficient for the purpose at hand.

| # | Don't | Do |
|---|-------|----|
| 1 | Hit a login wall → write "please have finance/ops enter payment details themselves for security" and stop, without asking | Decompose the remaining flow: **payment/credential entry** should be deferred to the user/business owner, but **login + viewing the resulting screen** is often just informational — ask which is actually needed before deciding to stop |
| 2 | Treat "login" and "entering payment info" as one bundled decision to skip together | They are different risk levels. Login-then-observe (e.g., see the real cart/checkout price) does not require entering card/account credentials — only the latter needs deferral |
| 3 | Report a pre-login/promotional price or state as if it were final, without flagging the gap | If the login-gated final screen wasn't verified, explicitly flag it ("actual payment screen not verified — may differ from the listed price") instead of presenting the pre-login figure as authoritative |
| 4 | Assume the backend can't support interactive login without checking | Check chrome-devtools connection + visibility (per `credential-issue.md` "Fresh-login flow") first; if visible, open the page there and have the user sign in in that same window, then continue capturing |
| 5 | Decide unilaterally that "this is good enough" when the report's factual accuracy depends on the gated screen | If the gap could make a delivered report/guide factually wrong (e.g., a payment-request report citing a price that turns out incorrect), the stop-vs-continue decision belongs to the user, not the assistant |

### Violation case (2026-07-22, 1st)

While building a domain-registration payment-request report, captured the domain-search-result page (showing a promotional price) and the login screen, then stopped at the login wall with a disclaimer ("have finance/ops enter payment details"), never asking whether to continue via login to verify the real checkout price. The report's stated price differed from the actual payment-screen price. User feedback (paraphrased): "don't arbitrarily skip capturing screens that require login — ask first."

## Known Automation Limitations — SaaS Portal Action-Level CAPTCHA Gates

Some SaaS portals allow full browser login automation but selectively trigger CAPTCHA challenges
on **creation/mutation actions** (not just on login). Document confirmed cases here so agents do
not repeat failed automation attempts.

| Service | Automatable | CAPTCHA-blocked | Fallback |
|---------|-------------|-----------------|----------|
| **Discord Developer Portal** | Login (via persistent profile with saved credentials) | **New application creation**, bot token reset | Keep browser visible (`headless: false`); user handles hCaptcha manually; script polls `page.url()` for `/bot` URL and auto-captures token once user navigates there |
| **Discord Developer Portal** | Reading existing app info, navigating between tabs | _(same)_ | _(same)_ |

### Discord Developer Portal — specific notes (2026-08-18, 1st confirmed)

- **Login**: Playwright persistent context (`launchPersistentContext`) with a saved user data directory
  retains Discord session cookies. Navigation to `discord.com/developers/applications` succeeds
  without re-authentication.
- **Bot creation blocked**: Clicking "New Application" and submitting the modal triggers an hCaptcha
  dialog (e.g. "Hold on! You are human, right?"). The `force: true` checkbox click and JS `dispatchEvent`
  workarounds successfully activate the Create button, but Discord's backend detects the automated
  browser and intercepts submission with CAPTCHA.
- **Recommended hybrid flow**:
  1. Launch Playwright with `headless: false` + `launchPersistentContext` (reuses login session).
  2. Navigate to the applications page.
  3. Set up a polling loop watching `page.url()` for the `/bot` path (every 2s, max ~4min timeout).
  4. Inform user to manually create the application (handle hCaptcha) and navigate to the Bot tab.
  5. When `/bot` URL is detected, script resumes: click "Reset Token" → capture `input[readonly]` value → enable `[role="switch"]` intents → save changes.
  6. Write token to a temp file → hand off to next automation (K8s Secret injection, etc.).

---

## Step 0: Environment & Tool Priority Resolution (MANDATORY — before any browser action)

Resolve which browser capability backend to invoke based on the current environment, prioritizing native/editor plugins over MCP servers.

### Step 0a: Host OS layer — WSL detection (MANDATORY, runs before the Tool Priority Matrix)

The multiplexer matrix below answers *which tool* drives the browser. It does not answer *which OS
the browser process runs on* — and for the CDP-hostile services in
[credential-issue.md](./credential-issue.md) that second axis decides whether automation works at
all. A Playwright MCP server started inside WSL drives a **Linux** Chrome, a different fingerprint
surface from `chrome-devtools-mcp` attaching to the user's **Windows** Chrome. Resolve this layer
first, record the result, and never carry a CDP-hostile verdict across it.

```bash
# WSL detection — either signal is sufficient
[[ -n "$WSL_DISTRO_NAME" ]] && echo "host=wsl"
grep -qi microsoft /proc/version 2>/dev/null && echo "host=wsl"
```

| Host layer | Record as | Consequence for CDP-hostile services |
|---|---|---|
| WSL (either signal true) | `host=wsl` | Playwright MCP (Linux Chrome) is a **first-class candidate**, not a skipped backend — measure before escalating |
| Windows, no WSL signal | `host=windows` | The documented Windows `chrome-devtools-mcp` findings apply as written |
| macOS / Linux native | `host=native` | Unmeasured for these services — treat as unknown and measure before asserting |

| # | Don't | Do |
|---|-------|-----|
| 1 | Jump straight to the Tool Priority Matrix and pick a backend | Resolve `host=` first — it gates the CDP-hostile escalation ladder |
| 2 | Apply a CDP-hostile verdict recorded on one host layer to another | Verdicts are per host layer. A Windows block is not a WSL block |
| 3 | Escalate a CDP-hostile service to wmux/cmux/OS-launch while `host=wsl` is untested | On `host=wsl`, try Playwright MCP first and record the outcome before escalating |

### Tool Priority Matrix

| Environment | 1st Priority (Native Plugin / CLI) | 2nd Priority (MCP Server Fallback) |
|-------------|------------------------------------|------------------------------------|
| **wmux** | `wmux browser` commands via Bash (User-visible) | Playwright MCP (`mcp__playwright__*`) |
| **cmux** | `cmux browser` commands via Bash (User-visible) | Playwright MCP (`mcp__playwright__*`) |
| **Plain / tmux** | Playwright MCP (`mcp__playwright__*`) (Headless default) | Headless Playwright CLI via Bash |

### Backend Availability Check

```bash
# wmux check
[[ -n "$WMUX" ]] || command -v wmux >/dev/null 2>&1

# cmux check (detect via ANY of these; CMUX_SESSION is NOT set by cmux app)
[[ -n "$CMUX_BUNDLE_ID" || -n "$CMUX_PANEL_ID" || -n "$CMUX_BUNDLED_CLI_PATH" ]] || command -v cmux >/dev/null 2>&1
```

### Do & Don't — Browser Backend Selection

| Environment | Detect (ANY true → environment matches) | Do (use this) | Don't (forbidden) |
|-------------|----------------------------------------|---------------|-------------------|
| **wmux** | `$WMUX` set OR `command -v wmux` succeeds | `wmux browser open/snapshot/click/type` commands via Bash | Playwright MCP — user cannot see the invisible Playwright window |
| **cmux** | `$CMUX_BUNDLE_ID` set OR `$CMUX_PANEL_ID` set OR `$CMUX_BUNDLED_CLI_PATH` set OR `command -v cmux` succeeds (e.g. `/Applications/cmux.app/Contents/Resources/bin/cmux`) | cmux browser panel commands | Playwright MCP — same reason |
| **Plain / tmux** | None of wmux/cmux signals present | Playwright MCP (Step 1 below) | — |

#### cmux detection — multi-var OR rationale

cmux app sets several env vars when launching a shell, **but `CMUX_SESSION` is NOT one of them** (a legacy guess by analogy with `WMUX`). Real vars observed in a cmux-launched shell:

- `CMUX_BUNDLE_ID` (e.g. `com.cmuxterm.app`)
- `CMUX_PANEL_ID` (UUID per panel)
- `CMUX_BUNDLED_CLI_PATH` (CLI absolute path)
- `CMUX_SHELL_INTEGRATION_DIR`
- `CMUX_AGENT_LAUNCH_*`
- `GHOSTTY_RESOURCES_DIR` (cmux uses Ghostty-based terminal)

`CMUX_SOCKET` is **set but often empty** — do not use it as the sole signal. Use the OR matrix above.

| # | Don't (single-var assumption) | Do (multi-var OR) |
|---|-------------------------------|-------------------|
| 1 | `[ -n "$CMUX_SESSION" ]` only check → false negative on cmux app | OR across `CMUX_BUNDLE_ID` / `CMUX_PANEL_ID` / `CMUX_BUNDLED_CLI_PATH` |
| 2 | Use `CMUX_SOCKET` as detection (empty in many cases) | Treat empty `CMUX_SOCKET` as no-signal; rely on the 3 vars above + CLI presence |
| 3 | Assume cmux env var name mirrors wmux (`*_SESSION`) | Verify against actual cmux app shell environment — vars differ per terminal multiplexer |

### wmux Browser Commands Reference

When `$WMUX` is set, use these instead of Playwright MCP.

**Invocation form**: the rest of this document uses the bare `wmux browser …` form, which is what runs when `wmux` is on `PATH` (the common case). If `wmux` is **not** on `PATH` in the current environment, substitute `node "$WMUX_CLI"` for `wmux` in every command below — `$WMUX_CLI` points to the same entry point. The two forms are interchangeable; pick whichever resolves on the current shell and use it consistently.

```bash
wmux browser open <url>          # navigate (= playwright navigate)
wmux browser snapshot            # get accessibility tree with @eN refs
wmux browser click @eN           # click element
wmux browser type @eN <text>     # type into element
wmux browser fill @eN <value>    # set input value
wmux browser get-text            # get page text
wmux browser screenshot          # capture screenshot
wmux browser eval <js>           # run JavaScript
wmux browser back                # go back
wmux browser forward             # go forward
wmux browser reload              # reload page
```

**Workflow**: `browser open <url>` → `browser snapshot` → read tree → `browser click/type @eN` → `browser snapshot` again.

**Refs (`@e1`, `@e2`...) expire after page changes** — always re-snapshot.

### Do & Don't — wmux vs Playwright Mapping

| Action | wmux (Do) | Playwright MCP (Don't in wmux) |
|--------|-----------|-------------------------------|
| Navigate | `Bash("wmux browser open <url>")` | `mcp__playwright__browser_navigate` |
| Snapshot | `Bash("wmux browser snapshot")` | `mcp__playwright__browser_snapshot` |
| Click | `Bash("wmux browser click @eN")` | `mcp__playwright__browser_click` |
| Type | `Bash("wmux browser type @eN text")` | `mcp__playwright__browser_type` |
| Screenshot | `Bash("wmux browser screenshot")` | `mcp__playwright__browser_take_screenshot` |
| Evaluate JS | `Bash("wmux browser eval <js>")` | `mcp__playwright__browser_evaluate` |
| Wait for text | Re-snapshot + check | `mcp__playwright__browser_wait_for` |

**Key difference**: wmux browser is visible to the user in real-time on the right panel. Playwright opens an invisible window the user cannot see.

---


## Quick Reference

After Step 0 backend detection, route to the topic:

| Goal | Topic | Entry |
|------|-------|-------|
| Verify a UI change, snapshot, click/fill | `ui-test` | [ui-test.md](./ui-test.md) |
| Diagnose `::part` not applying / closed shadow DOM cascade | `cdp-trace` | [cdp-trace.md](./cdp-trace.md) |
| Open a service login → wait for user login → issue access key/token | `credential-issue` | [credential-issue.md](./credential-issue.md) |

**Step execution order**: Step 0 (this file — detect backend + user-visibility rule) → read the
target topic `.md` → follow its procedure. The topic `.md` files hold the actual procedures; this
file is the shared backend-detection + index.

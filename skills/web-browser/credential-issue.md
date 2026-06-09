# Credential Issue (web-browser topic)

Take a **service** + **command** as parameters, open the service's login screen via the detected
browser backend, wait for the user to sign in, then on a completion signal **issue the requested
access key / token / secret** and hand the result to follow-up automation (aws-cli upload, `gh secret
set`, terraform var injection, etc.).

This generalizes the "open the page + user interaction + collect the result" pattern into a reusable
parameterized flow. It is the credential-issuance counterpart to [ui-test.md](./ui-test.md).

## Parameters

| Param | Meaning | Example |
|-------|---------|---------|
| `service` | The provider whose console issues the credential | `cloudflare-r2`, `github`, `oci`, `aws`, `authentik` |
| `command` | What to issue / do once logged in | `issue R2 S3 token`, `issue fine-grained PAT`, `create OAuth app` |
| `login-url` | Direct URL to the issuance page (when known) | `https://dash.cloudflare.com/?to=/:account/r2/api-tokens` |
| `handoff` | Follow-up automation to run with the issued credential | `aws s3 cp`, `gh secret set`, `vault kv put` |

## Backend selection (Step 0 + credential-specific preference)

Detect the backend via **SKILL.md Step 0** first. For credential issuance the preference order
differs from ui-test, because the user must **sign in** and reusing their real logged-in session is
fastest:

| Priority | Backend | Why | When |
|----------|---------|-----|------|
| 1 | **chrome-devtools** (real session) | Reuses the user's already-logged-in browser session — often no login needed | `chrome-devtools-mcp` connected |
| 2 | **Default browser** (`Start-Process <url>` / `open <url>`) | Opens the user's real browser (real session, fully interactive) | login-required + chrome-devtools absent |
| 3 | **wmux/cmux panel** | User-visible panel, interactive | `$WMUX` / `$CMUX_SESSION` set |
| 4 | Playwright MCP | **Last resort** — invisible window, user cannot log in interactively | only when a persisted/automated session already exists (no fresh login needed) |

**Key rule**: Playwright MCP opens an **invisible** window — the user cannot complete an interactive
login there. For any flow that needs a fresh user sign-in, prefer chrome-devtools (real session) or
the user's default browser. Do not drive an interactive login through invisible Playwright.

**Disconnected automatable backend → offer reconnect before degrading**: if the priority-1
automatable backend (chrome-devtools) is *disconnected*, do NOT silently fall to the manual
default-browser path. The gap is large — chrome-devtools drives the whole token-generation UI
(navigate → fill → click Create → snapshot-extract the token), whereas default browser is fully
manual (the user does every click). Surface the disconnection and offer to reconnect via `/plugin`
(chrome-devtools) first; fall to default browser only after the user declines reconnect or it fails.
The static priority table picks the highest *currently-connected* backend — but a disconnected MCP is
reconnectable, so treat "disconnected" as a reconnect-offer trigger, not a terminal fact, whenever
the flow benefits from backend automation.

## Procedure (automation-first, then login-assisted)

1. **Check stored credentials first (MANDATORY)** — before opening any browser, look in: skill `data/`
   files, project memory, `.env`, the secret store (`vault kv get`, `gh secret list`). If the
   credential already exists and is valid, **skip issuance** and go straight to `handoff`.
2. **Try API/SDK issuance (1st)** — if the provider exposes a token-issuance API and you hold a
   parent credential with sufficient scope, issue programmatically (no browser).
3. **Confirm API impossibility** — verify one of: the console is the only issuance path (e.g., R2
   "Public Development URL" + S3 token, PAT issuance is UI-only), the parent token lacks scope, or
   the SDK does not expose the flow.
4. **Login-assisted issuance (2nd)** — via the selected backend:
   - Open `login-url` (or the service console root) in the **visible** backend.
   - Inspect state (snapshot) — is the user already logged in, or is a login screen shown?
   - **If login required → wait for the user.** Tell them exactly what to do: "I opened {URL}.
     Please sign in and {command}, then tell me the {values}." Provide the direct URL. **Do not close
     the browser** while waiting (an isolated/invisible browser on a login screen is kept open, not
     closed — let the user sign in).
   - Wait for the user's completion signal (their message with the issued values, or an
     AskUserQuestion answer).
5. **Collect the result** — receive the issued access key / token / secret / endpoint / public URL
   from the user (or scrape it from the page if the backend can read it post-issuance).
6. **Hand off to automation** — immediately run `handoff` with the collected credential (e.g.,
   configure aws-cli + `aws s3 cp` upload, `gh secret set`, `vault kv put`), then **store** the
   credential in the appropriate secret store for reuse so the next run skips issuance.
7. **Forbidden**: ending with only "please go to {URL} and issue it yourself" with no browser opened
   and no follow-up.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | End with "issue it from the {service} console yourself" + stop | Open the console in a visible backend → guide the exact steps → collect the result → run `handoff` |
| 2 | Drive an interactive login through invisible Playwright MCP | Use chrome-devtools (real session) or the user's default browser for fresh logins. Playwright MCP only when a session already exists |
| 3 | Close the browser when it lands on a login screen | Keep it open; ask the user to sign in, then continue |
| 4 | Skip the stored-credential check and open a browser immediately | Check skill data / memory / `.env` / secret store first — reuse if present |
| 5 | Collect the credential then stop ("now you have a token") | Run `handoff` with it + store it for reuse. Issuance is a means, the handoff is the goal |
| 6 | Hardcode one provider's flow | Parameterize on `service` + `command`. Provider specifics go in the scenarios table / the caller's args |
| 7 | Leave an issued secret only in chat | Persist to the secret store (`vault kv put`, `gh secret set`) so it is reusable and not lost |
| 8 | After user login completes, delegate the **token generation steps** (clicking "New Token", selecting scopes, clicking "Create", copying value) to the user with text instructions | Once logged in, **drive the token-generation UI via the backend** (chrome-devtools `click`/`fill`/`take_snapshot`) and **extract the token from the page snapshot** programmatically. User typing/copying is a fallback when backend extraction fails (e.g., token shown as `••••` masked, password manager intercepts) |
| 9 | Treat "wait for user" as applying to the entire issuance flow | "Wait for user" applies to **(a) interactive login** and **(b) token reveal/copy when the token is masked or only shown once outside the DOM**. Token generation form-filling and "Create" click are backend-automatable when the user is logged in |

### Login provider preference — GitHub SSO first for Azure/Microsoft (HARD STOP)

**Azure DevOps, VS Code Marketplace publisher, Microsoft Learn, Azure portal, and other Microsoft-account-gated services that accept GitHub SSO MUST use the GitHub sign-in option** instead of direct Microsoft account login.

#### Why

- The user's GitHub account (e.g., `DrumRobot`) is already mapped + auth maintained (gh CLI, browser session, PAT). Reuse it instead of a separate Microsoft account login round-trip
- Microsoft account login often triggers extra MFA prompts / phone verification / device verification. GitHub session is already authenticated on the user's browser
- Single identity surface = easier secret rotation + audit. Azure DevOps user identity links back to GitHub (`@github` suffix), making it traceable in repo audit logs
- vsce / ovsx publisher accounts can be linked to either, but consolidating on GitHub keeps the credential trail single-source

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Open `https://login.microsoftonline.com` directly and ask user to enter Microsoft account password | Open the service (Azure DevOps / Marketplace) and click **"Sign in with GitHub"** (or equivalent third-party SSO button) |
| 2 | Drive Microsoft account 2FA flow through automation | Switch to GitHub SSO — fewer hurdles, reuses existing browser session |
| 3 | Assume "Microsoft service = Microsoft account" without checking | Most Azure DevOps orgs accept GitHub SSO. Check the sign-in page for a "GitHub" button before defaulting to MS account |
| 4 | After failed MS account login, retry MS account with different email | If MS account flow fails / requires verification, switch to GitHub SSO immediately |

#### Self-check (before opening a Microsoft service login page)

1. Does the target service accept GitHub SSO? — Azure DevOps ✅, VS Code Marketplace ✅, Microsoft Learn ✅, Azure portal ⚠️ (org-policy dependent — fall back to MS account)
2. Is the user already signed into GitHub in this browser session? — If yes, GitHub SSO completes in 1-2 clicks (consent screen) vs MS account 3-5 clicks (email → password → 2FA → consent)
3. On the sign-in page snapshot, look for "Sign in with GitHub" / "Continue with GitHub" / GitHub Octocat icon → click that, not the MS account input

#### Scenarios

| Service | GitHub SSO URL pattern | Notes |
|---------|------------------------|-------|
| Azure DevOps (PAT issuance) | `https://dev.azure.com/<org>/_usersSettings/tokens` → "Sign in with GitHub" button on the login screen | The same MS account email backed by GitHub appears as `user@github` in Azure DevOps |
| VS Code Marketplace publisher | `https://marketplace.visualstudio.com/manage/publishers/<publisher>` → GitHub SSO via the same Azure DevOps identity | Publisher = Azure DevOps org membership |
| GitHub itself | direct (no SSO needed) | gh CLI session covers it |

### Boundary: login wait vs token automation

| Phase | Who does it | Why |
|-------|-------------|-----|
| 1. Authentication (Microsoft / OAuth / SSO sign-in) | User (interactive) | Security: credentials must stay with the user; backend cannot enter passwords or pass 2FA |
| 2. Navigation to the token issuance page | Backend (`navigate_page` / `new_page`) | Once authenticated, page navigation is automatable |
| 3. Form fill (token name, scopes, expiration) | **Backend** (`fill` / `click`) | These are deterministic form inputs the caller decided from `command` |
| 4. Click "Create" / "Generate" | **Backend** (`click`) | Automatable |
| 5. Extract the issued token value | **Backend** (`take_snapshot` → parse the textbox containing the token) — fallback to user copy only when the token is masked / behind a copy-only button | The token is visible in the page after generation; extract directly. User-typed input is fragile (typos, partial paste) |
| 6. Handoff (`gh secret set`, `vault kv put`, local CLI publish) | **Backend** (Bash) | Mandatory automation |
| 7. Persist for reuse (skill `data/secrets/`, keychain) | **Backend** (Write) | Mandatory automation |

## Self-check (before opening any browser for issuance)

1. Is the credential already stored (skill data / memory / `.env` / secret store)? → If yes, skip to `handoff`.
2. Can it be issued via API/SDK with a parent credential? → If yes, do that (no browser).
3. Console-only? → Pick the backend: chrome-devtools (real session) > default browser > wmux/cmux > Playwright (only with an existing session).
4. Does the flow need a fresh interactive login? → If yes, the backend MUST be user-visible. Never invisible Playwright.
5. After collecting the credential, did you run `handoff` AND store it for reuse?
6. **Login complete → token generation automation check**: once the user is signed in, did the backend drive the token-generation UI (navigate → fill → click "Create" → snapshot the token) instead of writing text instructions for the user to follow? If text instructions were written, that is a violation of the boundary in the table above unless the token is genuinely behind a masked / copy-only UI element.

## Scenarios

| service / command | API issuance? | Login-assisted issuance (console URL) | handoff |
|-------------------|---------------|----------------------------------------|---------|
| `cloudflare-r2` / issue S3 token + public URL | ❌ console-only (Public Dev URL + token) | `https://dash.cloudflare.com/?to=/:account/r2/overview` → enable R2 → create bucket → Public Development URL → Manage R2 API Tokens | `aws s3 cp --endpoint-url https://<acct>.r2.cloudflarestorage.com` upload → public `https://pub-*.r2.dev/<key>` |
| `github` / issue fine-grained PAT | ❌ security (UI-only) | `https://github.com/settings/personal-access-tokens/new` | `gh secret set` / git remote auth |
| `github` / create OAuth app | ❌ UI-only | `https://github.com/settings/developers` | store client id/secret in `vault kv put` |
| `oci` / Customer Secret Key | ❌ console-only | OCI console → User → Customer Secret Keys | rclone/aws-cli S3 config |
| `authentik` / akadmin API token | ✅ (terraform/API) | (only if console needed) | terraform var / `vault kv put` |
| `vsce` (VS Code Marketplace publisher) / issue Azure DevOps PAT for `vsce publish` | ❌ UI-only (Azure DevOps Personal Access Token) | `https://dev.azure.com/<org>/_usersSettings/tokens` — `<org>` is the Azure DevOps organization linked to the Marketplace publisher (if not provided by caller, **ask via AskUserQuestion** before opening the page). Sign in via "Sign in with GitHub" SSO (see "Login provider preference" above). Token scope: `Marketplace > Manage` | `gh secret set VSCE_PAT -R <owner>/<repo>` + local `npx vsce publish --packagePath <vsix> --pat $VSCE_PAT` |
| `ovsx` (Open VSX Registry publisher) / issue Open VSX PAT for `ovsx publish` | ❌ UI-only | `https://open-vsx.org/user-settings/tokens` — sign in via the **GitHub** option (Open VSX is GitHub-SSO native) | `gh secret set OVSX_PAT -R <owner>/<repo>` + local `npx ovsx publish <vsix> -p $OVSX_PAT` |
| any / register a GitHub Secret | ✅ `gh secret set` | (not needed) | — |

## Note on GitHub PR image hosting (why R2)

GitHub renders inline images via a **Camo proxy** that fetches from GitHub's servers — it **cannot
reach internal hosts** (e.g., `10.0.0.x` MinIO, tailnet `*.ts.net`). A capture hosted on an internal
store will not render inline in a PR. **Cloudflare R2 with a public `r2.dev` / custom-domain URL is
publicly reachable**, so Camo can fetch it → the image renders inline. This is the canonical use of
`service: cloudflare-r2` for PR capture attachment.

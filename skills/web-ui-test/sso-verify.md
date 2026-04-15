# SSO Verification

Automatically verify the Authentik SSO login flow using Playwright.

## When to Use

- After deploying Authentik + dt app to dev/integration server
- To confirm redirect target after changing an OAuth Source URL
- To test the entire login flow end-to-end

## Verification Checklist

| # | Item | Success Criteria | Failure Signal |
|---|------|-----------------|----------------|
| 1 | Authentik accessibility | Login page loads (heading "Login" or form element present) | "authentik starting", blank page |
| 2 | Redirect target | URL navigates to the intended server | Redirect to different server IP/port (Blueprint drift) |
| 3 | OAuth authorize | dt app's authorize endpoint responds normally | `unauthorized_client`, 404, 405 |
| 4 | Login complete | Dashboard redirect after login | Infinite redirect, error page |

## Procedure

### Step 1: Register Playwright

See "Required Setup" in SKILL.md.

### Step 2: Navigate to Authentik Login Page

```typescript
playwright.playwright_browser_navigate({ url: 'http://<host>:9000/if/flow/default-authentication-flow/' });
playwright.playwright_browser_wait_for({ time: 5 });
const snapshot = playwright.playwright_browser_snapshot();
```

### Step 3: Confirm Redirect Target

Analyze the **Page URL** from the snapshot:

| URL Pattern | Meaning | Action |
|-------------|---------|--------|
| `http://<same-host>:<dt-port>/deps_emc/api/oauth/authorize?...` | Normal — redirected to dt app on same server | Go to Step 4 |
| `http://<different-host>/deps_emc/api/oauth/authorize?...` | Blueprint drift — redirected to a different server | DB UPDATE required (see below) |
| `http://<host>:9000/...` (self) | OAuth Source not configured or not connected to flow | Check Authentik admin |
| "authentik starting" or blank page | Server is starting up | Wait and retry |

### Step 4: Check OAuth Authorize Response

Detect errors from the snapshot of the redirected page:

| Response | Cause | Fix |
|----------|-------|-----|
| `{"error":"unauthorized_client"}` | The `client_id` is not registered in the dt app | Check dt app env var `OAUTH_SOURCE_CLIENT_ID` or add the client to the allowed list in code |
| 404 Not Found | `/api/oauth/authorize` endpoint missing | Rebuild dt app image (OAuth Provider code not included) |
| 405 Method Not Allowed | GET not supported | OAuth authorize requires GET; check route handler |
| Login form displayed | Normal — dt app redirecting unauthenticated user to login | Proceed to login |

### Step 5: Login Test (Optional)

If a login form is displayed:

```typescript
// Enter username
playwright.playwright_browser_type({ ref: '<username_ref>', text: 'akadmin' });
// Enter password
playwright.playwright_browser_type({ ref: '<password_ref>', text: '<PASSWORD>', submit: true });
// Check result
playwright.playwright_browser_wait_for({ time: 3 });
playwright.playwright_browser_snapshot();
```

## When Blueprint Drift is Detected

If the redirect points to a different server, fix it with ansible:

```bash
# dry-run
make -C ansible blueprint-<env>-diff

# apply (includes DB UPDATE)
make -C ansible blueprint-<env>-deploy
```

Or manual DB UPDATE:

```bash
ssh <host> "docker exec authentik-postgres psql -U authentik -d authentik -c \"
  UPDATE authentik_sources_oauth_oauthsource
  SET authorization_url='http://<DT_HOST>/deps_emc/api/oauth/authorize',
      access_token_url='http://<DT_HOST>/deps_emc/api/oauth/token',
      profile_url='http://<DT_HOST>/deps_emc/api/oauth/userinfo';
\""
```

Details: `.ralph/docs/generated/authentik-blueprint-drift.md`

## Report Format

```md
## SSO Verification Result

**Server:** <host>:<port>
**Authentik:** <authentik_url>

| # | Item | Result |
|---|------|--------|
| 1 | Authentik access | OK / FAIL |
| 2 | Redirect target | <actual URL> (normal/drift) |
| 3 | OAuth authorize | OK / unauthorized_client / 404 |
| 4 | Login complete | OK / FAIL |

### Issues Found
- [describe if any]

### Actions Taken
- [describe if any]
```

# Changelog

## [0.2.5](https://github.com/es6kr/skills/compare/web-browser-v0.2.4...web-browser-v0.2.5) (2026-08-05)


### Bug Fixes

* promote next-fix staging (38 fixes across 16 skills) ([94f8c33](https://github.com/es6kr/skills/commit/94f8c33800ce411ae63e22c5259cdae8435508a4))
* **web-browser:** CDP-hostile escalation overrides recorded browser preference ([13a13a0](https://github.com/es6kr/skills/commit/13a13a0d6de9a0a9057dbdad1acb9b600710153e))
* **web-browser:** check locally-recorded preferred browser before naming one in OS-level open ([2b9eef2](https://github.com/es6kr/skills/commit/2b9eef283560c0f0b5b8ec40aab79af9f2629fff))
* **web-browser:** preferred-browser check + credential-issue fallback for API tasks ([a5a7859](https://github.com/es6kr/skills/commit/a5a7859d6c0c9ebfc2a7a6417b30e6a6299fd3da))
* **web-browser:** recommend credential-issue instead of manual UI clicking when API access is available ([b127109](https://github.com/es6kr/skills/commit/b127109bcd1fd11c809d1f861c88fcc2cd6c072a))
* **web-browser:** verify app's actual CLI support before borrowing another tool's flag syntax ([7ce4a28](https://github.com/es6kr/skills/commit/7ce4a28937e1c07e95eecfc511802c445385ee6b))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([951c1e6](https://github.com/es6kr/skills/commit/951c1e6871e78e226757c6a7ae5ae53efeb7bfb0))

## [0.2.4](https://github.com/es6kr/skills/compare/web-browser-v0.2.3...web-browser-v0.2.4) (2026-07-23)


### Bug Fixes

* **next-fix:** accumulate bug fixes for docxport, wip, fix-plan, and hook-kit ([6eec083](https://github.com/es6kr/skills/commit/6eec083b7fbc429bdabcfcc89d7778b185dd7497))
* skills body bundle — consolidate/fix/hook-kit refinements + English-clean guard hooks (Ralph-loop bypass) ([2e26f41](https://github.com/es6kr/skills/commit/2e26f412a5b963984898e13caaca186c3617ca08))
* **web-browser:** don't abandon automation on a single login-block signal ([fed542e](https://github.com/es6kr/skills/commit/fed542e600d83979d3e31fde597da13e0ce0e18e))

## [0.2.3](https://github.com/es6kr/skills/compare/web-browser-v0.2.2...web-browser-v0.2.3) (2026-07-07)


### Bug Fixes

* **fix,web-browser:** publish-scope edit gate + managed-surface backend detection ([2e28fc4](https://github.com/es6kr/skills/commit/2e28fc4d39953ee6a88f64bd8c8d20907ba01e39))
* **skills:** review-feedback bundle — consolidate trigger wording + fix wiki paths ([784854e](https://github.com/es6kr/skills/commit/784854e3e07696ca8d16274215004488861862d1))

## [0.2.2](https://github.com/es6kr/skills/compare/web-browser-v0.2.1...web-browser-v0.2.2) (2026-06-30)


### Bug Fixes

* **skills:** add procedural guards + standardize description scalar ([#66](https://github.com/es6kr/skills/issues/66)) ([fcc921f](https://github.com/es6kr/skills/commit/fcc921fba3928aad7421ecff888d5dcee5ae5655))

## [0.2.1](https://github.com/es6kr/skills/compare/web-browser-v0.2.0...web-browser-v0.2.1) (2026-06-19)


### Bug Fixes

* bundle skill patches across 7 scopes ([f18f47c](https://github.com/es6kr/skills/commit/f18f47c2d05f13b8e3f3ad42675a2dabbb31c824))
* **credential:** add PAT scope matrix + Settings UI procedure + Service × Store persist matrix ([c61525b](https://github.com/es6kr/skills/commit/c61525b1a2d886b677c85d2638d39a1e2311c142))
* **web-browser:** compress SKILL.md description + replace credential-issue placeholder ([4fb1148](https://github.com/es6kr/skills/commit/4fb114800991d757c07eb63d1a3d3b8fc19bde4a))

## [0.2.0](https://github.com/es6kr/skills/compare/web-browser-v0.1.0...web-browser-v0.2.0) (2026-06-12)


### Features

* decompose workflow/git rules + rename web-ui-test→web-browser ([#50](https://github.com/es6kr/skills/issues/50)) ([e10d48f](https://github.com/es6kr/skills/commit/e10d48fea4e507b95888de44812b53484d32128d))

## [0.1.0] (2026-06-09)

Initial release. `web-browser` is the environment-aware browser-operations skill, succeeding the
legacy `web-ui-test` skill (which is retained, local-only, for `sso-verify`).

### Features

* **ui-test**: snapshot analysis, click/fill/verify UI, page-state diagnosis (migrated from web-ui-test).
* **cdp-trace**: CDP-based closed shadow DOM cascade diagnosis (migrated from web-ui-test).
* **credential-issue**: new topic — take a service + command as parameters, open the service login
  screen via the detected backend, wait for the user to sign in, then issue the requested access
  key / token / secret and hand the result to follow-up automation (aws-cli upload, gh secret set,
  etc.). chrome-devtools backend preferred for real-session reuse.
* Shared **Step 0** environment detection (wmux/cmux/Playwright) + user-visibility HARD STOP.

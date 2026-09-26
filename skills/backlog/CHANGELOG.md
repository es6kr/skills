# Changelog

All notable changes to the `backlog` skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2](https://github.com/es6kr/skills/compare/backlog-v0.4.1...backlog-v0.4.2) (2026-09-26)


### Bug Fixes

* **backlog:** add scope gate for Plane-issue creation vs. local git housekeeping ([#551](https://github.com/es6kr/skills/issues/551)) ([02e32e2](https://github.com/es6kr/skills/commit/02e32e2345225f256e92fa88983b2b30f6b24f3c))
* **backlog:** make list_issues()/plane_verify_identifier.py see Triage-inbox issues ([#553](https://github.com/es6kr/skills/issues/553)) ([c203652](https://github.com/es6kr/skills/commit/c203652374272f97ef7f0a71fe2d56c8b493717a))

## [0.4.1](https://github.com/es6kr/skills/compare/backlog-v0.4.0...backlog-v0.4.1) (2026-09-24)


### Bug Fixes

* **backlog:** carry the K3s target keys through resolve_profile ([611374f](https://github.com/es6kr/skills/commit/611374f3096ab0d529383f74297371478368face))
* **backlog:** report a missing K3s fallback target as a profile misconfiguration ([c049e3f](https://github.com/es6kr/skills/commit/c049e3fcb40e5a29f6052432238985805b18f32a))
* make the Plane K3s fallback reach its cluster, and stop the retag guard firing on citations ([ce0abde](https://github.com/es6kr/skills/commit/ce0abded29d992ac89b865e806aed9b531d4909d))

## [0.4.0](https://github.com/es6kr/skills/compare/backlog-v0.3.2...backlog-v0.4.0) (2026-09-20)


### Features

* **backlog:** add plane_verify_identifier.py to catch wrong-key references ([#508](https://github.com/es6kr/skills/issues/508)) ([704af59](https://github.com/es6kr/skills/commit/704af59599ed2d848e540f963b8fbc9bccd83d1f))


### Bug Fixes

* address code review feedback ([0c08bfb](https://github.com/es6kr/skills/commit/0c08bfbf2b5b737fdce685c8f15ead56c64290f4))
* **backlog:** add browse_url helper and use it in Plane issue reporting paths ([91ee0ce](https://github.com/es6kr/skills/commit/91ee0ce0a9580283725491ffb08a4013429fdb54))

## [0.3.2](https://github.com/es6kr/skills/compare/backlog-v0.3.1...backlog-v0.3.2) (2026-09-18)


### Bug Fixes

* **cleanup:** make the session-end report table self-sufficient ([#487](https://github.com/es6kr/skills/issues/487)) ([c4a0255](https://github.com/es6kr/skills/commit/c4a02557fb8de3b32cf337c549f62535dabf824b))
* **skills:** document canonical Do/Don't tables for Plane URLs, plan sync, and pre-merge reviews ([7069da8](https://github.com/es6kr/skills/commit/7069da85bb11bdcf0da8d9dc93619eeafc972dd2))

## [0.3.1](https://github.com/es6kr/skills/compare/backlog-v0.3.0...backlog-v0.3.1) (2026-09-08)


### Bug Fixes

* **backlog:** stop forwarding the Plane API key across redirects ([c43c474](https://github.com/es6kr/skills/commit/c43c474f590861101ec68221cfbcf85f5ca87937))
* **tdd:** scope the Red-only commit ban to shared branches ([fc2e6ec](https://github.com/es6kr/skills/commit/fc2e6ecdd1906c41d47955226e247aeb03a6f367))

## [0.3.0](https://github.com/es6kr/skills/compare/backlog-v0.2.0...backlog-v0.3.0) (2026-09-06)


### Features

* **fix-plan:** add claim_item.py and wire it to plane_sync started-transition ([add4069](https://github.com/es6kr/skills/commit/add40691c3a68c1160a43259ca358b74e4bd7518))
* **fix-plan:** add plane_sync transition_issue_to_started ([0a98966](https://github.com/es6kr/skills/commit/0a9896631405139bcf2739127d0a79f3e12a139f))


### Bug Fixes

* **backlog:** require HTTPS, refuse redirects, accept any 2xx in make_plane_request ([fb7b952](https://github.com/es6kr/skills/commit/fb7b952e4bbd67c588ed9450649eb152a20d2d62))

## [0.2.0](https://github.com/es6kr/skills/compare/backlog-v0.1.0...backlog-v0.2.0) (2026-08-29)


### Features

* **backlog:** merge plane-backlog into backlog and register missing skills in release-please ([7ed72a1](https://github.com/es6kr/skills/commit/7ed72a1be1a7df7e91252494828d96f77bb769ad))
* **backlog:** migrate prune_p2p3.py to backlog and implement Option A+B (anchored regex & anomaly gate) ([7bc4fd1](https://github.com/es6kr/skills/commit/7bc4fd197fb5f9cc8bb2b662a8f72f02ed827b9b))
* **backlog:** scaffold initial backlog lifecycle skill v0.1.0 ([6151855](https://github.com/es6kr/skills/commit/6151855ae40fb7f00e8c804795e96159c80d449c))
* promote next-feat batch (backlog skill, hooks JS port, git-repo doctor, pre-push guard) ([0d76a4c](https://github.com/es6kr/skills/commit/0d76a4c01180fbdc78bfeec8dea91373b4912470))


### Bug Fixes

* address CodeRabbit and Copilot review feedback on PR [#385](https://github.com/es6kr/skills/issues/385) ([e94de34](https://github.com/es6kr/skills/commit/e94de34ce5e075c79b7edc5d672813cea94a0acc))
* address CodeRabbit and Copilot review feedback on PR [#389](https://github.com/es6kr/skills/issues/389) ([db4dfff](https://github.com/es6kr/skills/commit/db4dfff2829632bf263d93e0bbfdd1244772a5b2))
* **backlog:** add prune topic for P2/P3 demotion to TODO backlog ([b9f7672](https://github.com/es6kr/skills/commit/b9f7672f261f5e9589e09d167b1b33d781523df2))
* promote next-fix batch (task plugin split, claudify matcher, pr recheck, omz chezmoi fix) ([3e90fd5](https://github.com/es6kr/skills/commit/3e90fd56ade0522d6773eb03f38760a317dd5180))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([4982364](https://github.com/es6kr/skills/commit/49823641a7b08123ebd0325273892bee41bc3280))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([951c1e6](https://github.com/es6kr/skills/commit/951c1e6871e78e226757c6a7ae5ae53efeb7bfb0))

## [0.1.0] - 2026-08-27

### Added
- Initial release of the `backlog` lifecycle and orchestration skill.
- Vendor-agnostic schema and routing interface across session TODOs, file checklists, and issue trackers.
- Lifecycle actions: triage, priority classification, synchronization, and backlog hygiene.

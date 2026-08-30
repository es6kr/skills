# Changelog

All notable changes to the `backlog` skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

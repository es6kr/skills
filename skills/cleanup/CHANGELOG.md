# Changelog

## [0.2.0](https://github.com/es6kr/skills/compare/cleanup-v0.1.0...cleanup-v0.2.0) (2026-08-29)


### Features

* **cleanup,claudify:** route the fa-prune trigger to its class-based source ([a7ba7b4](https://github.com/es6kr/skills/commit/a7ba7b4f6790ca86e6db41d20010d85bdde8d017))
* **cleanup,fix-plan,fix:** add automated fixplan completion triage and schema validation ([cc92243](https://github.com/es6kr/skills/commit/cc922437e86e5ce8ec36a87e870bedb0087b9308))
* **hooks:** migrate standalone hooks into plugin resources and fix test regressions ([897ac2e](https://github.com/es6kr/skills/commit/897ac2e1921115e6e8987b2f8460f2bfded41714))
* merge next-feat into main ([#313](https://github.com/es6kr/skills/issues/313)) ([2d9308a](https://github.com/es6kr/skills/commit/2d9308ab3e7e0086a88a7f64d3ed4d5c4d36e017))
* **plane-backlog:** add Plane backlog skill with client and indexify scripts ([3bcc8cd](https://github.com/es6kr/skills/commit/3bcc8cd8f570bb53697f290e9e6e53069991822b))
* promote next-feat batch (hook registry schema, self-reference path anchoring) ([0c33ffa](https://github.com/es6kr/skills/commit/0c33ffac99a9237f4530566470dabeaea128c209))
* promote next-feat staging (lifecycle guards, triage automation, and workflow safety procedures) ([77d58ac](https://github.com/es6kr/skills/commit/77d58ac3a771a4897043c9eea8b149ea1e8ba2ff))


### Bug Fixes

* accumulate 16 patch-level bug fixes and guard enhancements across skills ([d214e5d](https://github.com/es6kr/skills/commit/d214e5dcc7fac1bc07baf3b6cec62999aea732f0))
* catch omitted cleanup-report mandatory rows (hook-kit guard + run.md Wiki row) ([e4a3cd9](https://github.com/es6kr/skills/commit/e4a3cd92c63609a1562df417b63a927acfb8e36a))
* **cleanup,claudify:** separate ask-bypass axis from RAG-store axis in Ralph Mode ([196da8f](https://github.com/es6kr/skills/commit/196da8fdb30de50bb11296ddf7cae153534bcb67))
* **cleanup,fix-plan:** anchor script paths to the skill directory ([8a2f9be](https://github.com/es6kr/skills/commit/8a2f9be6f5bba1f9a9ec35ca2616fabf7addf847))
* **cleanup:** add Plane-completion-first gate before fix_plan Completed deletion ([bc2adc4](https://github.com/es6kr/skills/commit/bc2adc49fa4ad61c6333c65c5f606b19e73c7350))
* **cleanup:** add the 3-A LLM Wiki scope-check row to Step 5's mandatory rows ([bd5885a](https://github.com/es6kr/skills/commit/bd5885a77472f2eaddab1d7e33202d0441b9e4c8))
* **cleanup:** cover implementation_plan.md in the session-brain Glob check ([c702e46](https://github.com/es6kr/skills/commit/c702e4674ba7862b3e1be376e80d818567e01555))
* **cleanup:** make locale markers additive in block-cleanup-missing-rename hook ([c9d651f](https://github.com/es6kr/skills/commit/c9d651f4e11769b9b89deeee42f499c4731f0658))
* **cleanup:** mandate session identity (UUID + rename recommendation) in end-report ([5ac3e0b](https://github.com/es6kr/skills/commit/5ac3e0bce421f7125eb5e83e91d11aad29cb9456))
* **cleanup:** mandate session identity (UUID + rename recommendation) in end-report ([ea9c4c6](https://github.com/es6kr/skills/commit/ea9c4c66047d7d0ffa49ccccdf1b8094032c9bf1))
* **cleanup:** parse class-format meta-line last= date in fa-classify.py ([#173](https://github.com/es6kr/skills/issues/173)) ([f8f990c](https://github.com/es6kr/skills/commit/f8f990ca29b6af368c925dc8b225c47174548582))
* **cleanup:** recognize plugin-prefixed claudify/cleanup Skill calls ([#382](https://github.com/es6kr/skills/issues/382)) ([0d4521d](https://github.com/es6kr/skills/commit/0d4521d55059d2f67e7d7f2982e77d682ed6d712))
* **cleanup:** redesign fa-prune trigger for class-structured HOT ([#176](https://github.com/es6kr/skills/issues/176)) ([6498af1](https://github.com/es6kr/skills/commit/6498af16a9daa6fd53804ce623b368a0e75e8071))
* **cleanup:** require 3-C.1 to advance the receiver's gap baseline ([1251fb5](https://github.com/es6kr/skills/commit/1251fb581e28210c9e6b5ac7448ec6c406ca0295))
* **cleanup:** require a persistent walkthrough file at Step 4.5 ([a7556c6](https://github.com/es6kr/skills/commit/a7556c6ab18523fbdb0a0cae2514cefe5875a712))
* **cleanup:** require a persistent walkthrough file at Step 4.5 ([45dffb6](https://github.com/es6kr/skills/commit/45dffb661ae08b195f495b7c168e4bcd275aee7e))
* **cleanup:** resolve internal-review findings in session-identity end-report ([86fd1a8](https://github.com/es6kr/skills/commit/86fd1a8afad7a48e5534e60812673910b8de2ba9))
* **cleanup:** sanitize pre-existing real session UUID in run.md example ([#249](https://github.com/es6kr/skills/issues/249)) ([2d593f7](https://github.com/es6kr/skills/commit/2d593f7da71c4d1ba43caeed86d949986650d654))
* **cleanup:** separate ask-bypass from RAG-store axis in Ralph Mode ([93b4a28](https://github.com/es6kr/skills/commit/93b4a28b04ebe9b6137e4ca8713acbbec62670cd))
* **cleanup:** store HOT failed-attempts entries to RAG at write time ([ae03432](https://github.com/es6kr/skills/commit/ae034322ca0beb1895e9d7e0e3633f80b1557c42))
* **consolidate:** address CodeRabbit review feedback on PR [#392](https://github.com/es6kr/skills/issues/392) ([3b50e26](https://github.com/es6kr/skills/commit/3b50e26d53666f069eb489211cc67a2820a7cd8a))
* declare undeclared skill-to-skill dependencies (7 skills) ([#271](https://github.com/es6kr/skills/issues/271)) ([36a9f9d](https://github.com/es6kr/skills/commit/36a9f9d7c1fac9bb1c4c96b325a067ab92ad0da7))
* **fix-plan,cleanup:** replace absolute self-reference script paths with relative form ([91e99e2](https://github.com/es6kr/skills/commit/91e99e2f4f2657b7646a886d4d98ec5e2dbb09c0))
* **fix-plan,cleanup:** replace absolute self-reference script paths with relative form ([8b6a1e6](https://github.com/es6kr/skills/commit/8b6a1e627584866cef43f1866548f3ef32d2a849))
* **fix-plan:** remove plane_bulk_update.py internal-infra hardcoding + add leak guard ([e7cedfd](https://github.com/es6kr/skills/commit/e7cedfdcd5364a26d581286baa8248a2400b8591))
* **git-repo:** document conflict root-cause diagnosis (staleness vs divergence) ([f034168](https://github.com/es6kr/skills/commit/f0341685d6bf07c9d16e9375c93c22fea88b454f))
* **hook-kit:** catch a wholly-omitted Session identity row in cleanup reports ([f4b67ad](https://github.com/es6kr/skills/commit/f4b67ad7f8d3f50c205a0a43aaf6b28fd2fdb029))
* **hook-kit:** relocate cleanup/wip-owned guard hooks to their owning skill ([#330](https://github.com/es6kr/skills/issues/330)) ([9d50cac](https://github.com/es6kr/skills/commit/9d50cac6f4c02357aee334abc8bca35c1e49d0e6))
* **hook-kit:** repair hook paths broken by the within-marketplace relocation ([#340](https://github.com/es6kr/skills/issues/340)) ([0d9b701](https://github.com/es6kr/skills/commit/0d9b70181015e4822c7cf5cd2fe122d5af708d26))
* **hook-kit:** resolve RAG receiver from workspace config instead of mandating --rag ([58e85ec](https://github.com/es6kr/skills/commit/58e85ecbb437557544cd528281aa30b804bd2532))
* **hook-kit:** resolve RAG receiver from workspace config instead of mandating --rag ([1412773](https://github.com/es6kr/skills/commit/1412773466d11354eca7521e4351faa5a78d9081))
* **hook-kit:** scope PR-URL bare-ref check to per-number match, allow force-push in worktrees ([dd50dce](https://github.com/es6kr/skills/commit/dd50dced989eed4847daaf9a0cd4be12a04426e1))
* **next-fix:** promote staged fixes across hook-kit, next, cleanup, fix-plan ([34f1c67](https://github.com/es6kr/skills/commit/34f1c67beee3a8279e0e80de4ab3a87ba2223d5c))
* plan-to-issue frontmatter guard, cleanup gap-baseline sync, pre-commit placeholder exemption ([20e1698](https://github.com/es6kr/skills/commit/20e1698b3b3ee435b8c2705dfe32124567eedd29))
* **plane-backlog,cleanup:** capture intake outcome, guard regex boilerplate, resolve script paths ([a7b0fb3](https://github.com/es6kr/skills/commit/a7b0fb371c4ef0956720b44485b1dd6ba15679ab))
* promote accumulated next-fix fixes to main ([803bbd3](https://github.com/es6kr/skills/commit/803bbd3b9e4f8367ee1b955cfa2b6a536f85cee0))
* promote accumulated next-fix fixes to main ([95656e9](https://github.com/es6kr/skills/commit/95656e9b551ee0bb77904a0a571d49c53bc01cc9))
* promote next-fix batch (consolidate fabrication guard, session rewind, config-driven PR base) ([7ca0ccb](https://github.com/es6kr/skills/commit/7ca0ccbf13cefafedc33a16a7361756c95f8b8f6))
* promote next-fix batch (hook path repair, topic-dispatch scoping, conflict diagnosis) ([eb7ecb6](https://github.com/es6kr/skills/commit/eb7ecb61dda9701d78f12dc810781dc7cb687caa))
* promote next-fix batch (task plugin split, claudify matcher, pr recheck, omz chezmoi fix) ([3e90fd5](https://github.com/es6kr/skills/commit/3e90fd56ade0522d6773eb03f38760a317dd5180))
* promote next-fix staging (38 fixes across 16 skills) ([94f8c33](https://github.com/es6kr/skills/commit/94f8c33800ce411ae63e22c5259cdae8435508a4))
* resolve PR [#197](https://github.com/es6kr/skills/issues/197) review findings (CodeRabbit + Copilot + Internal Review) ([b54236a](https://github.com/es6kr/skills/commit/b54236a4fa4b3fef23645dfc3b184916980b7f65))
* **review:** apply copilot review feedback on hooks and test suites ([cba86f4](https://github.com/es6kr/skills/commit/cba86f4ebbf274a0c979ab21aeea6d483f8cb8f3))
* **skills:** close four gaps found while running consolidate, lint and merge ([0a06faa](https://github.com/es6kr/skills/commit/0a06faa1ab1715c5825b81be11d0721074f9b13a))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([4982364](https://github.com/es6kr/skills/commit/49823641a7b08123ebd0325273892bee41bc3280))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([951c1e6](https://github.com/es6kr/skills/commit/951c1e6871e78e226757c6a7ae5ae53efeb7bfb0))


### Refactor

* **hooks:** sync hook registry, enhance bash-guard, and retire obsolete guards ([15d4a58](https://github.com/es6kr/skills/commit/15d4a58752d0d458f88c86cb41c537f90e3ca4dd))

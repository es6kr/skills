# Changelog

## [0.6.0](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.5...commit-tidy-v0.6.0) (2026-08-29)


### Features

* **works-config:** implement v0.2.0 role-based resolution & neutral SSOT guards config ([e22e117](https://github.com/es6kr/skills/commit/e22e117371370c59b18b77c72bdb926dcb1897cb))


### Bug Fixes

* **hook-kit:** scope PR-URL bare-ref check to per-number match, allow force-push in worktrees ([dd50dce](https://github.com/es6kr/skills/commit/dd50dced989eed4847daaf9a0cd4be12a04426e1))

## [0.5.5](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.4...commit-tidy-v0.5.5) (2026-08-20)


### Bug Fixes

* **commit-tidy:** add 5+ files large-scale modification mandatory gate ([2eca0a0](https://github.com/es6kr/skills/commit/2eca0a085295dae3707bd4447f2ec1996023e1bf))
* **hooks:** correct ghost path for block-wip-register-before-execute.sh ([d5875a2](https://github.com/es6kr/skills/commit/d5875a2e624eeb4a3dce9beba5d96a4365a8f950))
* promote next-fix batch (hook path repair, topic-dispatch scoping, conflict diagnosis) ([eb7ecb6](https://github.com/es6kr/skills/commit/eb7ecb61dda9701d78f12dc810781dc7cb687caa))

## [0.5.4](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.3...commit-tidy-v0.5.4) (2026-08-17)


### Bug Fixes

* **commit-tidy:** cross-reference hunk-split from staging-discipline ([1ef05f3](https://github.com/es6kr/skills/commit/1ef05f31e40fe48c53f1b87ab3d4238db506d2cd))
* promote next-fix staging (30 fixes across 14 skills) ([ee467c0](https://github.com/es6kr/skills/commit/ee467c045d779d7b80d30f160763ec3534a9742b))
* wip single-item ask skip + hunk-split cross-ref ([0c4007a](https://github.com/es6kr/skills/commit/0c4007a18ae65b31ac7d308ea7d96a68b76b9ca4))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([4982364](https://github.com/es6kr/skills/commit/49823641a7b08123ebd0325273892bee41bc3280))

## [0.5.3](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.2...commit-tidy-v0.5.3) (2026-08-11)


### Bug Fixes

* **commit-tidy:** require explicit HEAD ref and hunk inspection in the shared-checkout sanity check ([7274f14](https://github.com/es6kr/skills/commit/7274f143863f27040b4379ea60ee6a4e8a2afbfd))
* **commit-tidy:** require HEAD-diff sanity check before staging shared hardlinked skill files ([b77b597](https://github.com/es6kr/skills/commit/b77b5972350bec1d7f83ea4bcaa45214b9748b10))
* **commit-tidy:** require HEAD-diff sanity check before staging shared hardlinked skill files ([174d27a](https://github.com/es6kr/skills/commit/174d27a2be3512148cd569381958d92908da467e))

## [0.5.2](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.1...commit-tidy-v0.5.2) (2026-08-09)


### Bug Fixes

* **consolidate:** address CodeRabbit/Copilot review findings on PR [#270](https://github.com/es6kr/skills/issues/270) ([3b11a73](https://github.com/es6kr/skills/commit/3b11a730b5ad68803d35a8264eda540e48265d75))
* declare undeclared skill-to-skill dependencies (7 skills) ([#271](https://github.com/es6kr/skills/issues/271)) ([36a9f9d](https://github.com/es6kr/skills/commit/36a9f9d7c1fac9bb1c4c96b325a067ab92ad0da7))
* PR [#195](https://github.com/es6kr/skills/issues/195) review findings batch 2 (github-repo/skill-kit/commit-tidy/hook-kit) ([#264](https://github.com/es6kr/skills/issues/264)) ([d8d9df0](https://github.com/es6kr/skills/commit/d8d9df04bdf178fffa6822c44199a416668c6423))
* promote accumulated next-fix fixes to main ([95656e9](https://github.com/es6kr/skills/commit/95656e9b551ee0bb77904a0a571d49c53bc01cc9))

## [0.5.1](https://github.com/es6kr/skills/compare/commit-tidy-v0.5.0...commit-tidy-v0.5.1) (2026-08-05)


### Bug Fixes

* **commit-tidy:** add full-range squash scan + middle-range squash procedure ([#201](https://github.com/es6kr/skills/issues/201)) ([90e9ae8](https://github.com/es6kr/skills/commit/90e9ae86a3c1e483217b6d7f69b585809bfafd0f))
* promote next-fix staging (38 fixes across 16 skills) ([94f8c33](https://github.com/es6kr/skills/commit/94f8c33800ce411ae63e22c5259cdae8435508a4))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([951c1e6](https://github.com/es6kr/skills/commit/951c1e6871e78e226757c6a7ae5ae53efeb7bfb0))

## [0.5.0](https://github.com/es6kr/skills/compare/commit-tidy-v0.4.3...commit-tidy-v0.5.0) (2026-07-28)


### Features

* bundle next-feat — fix-plan expansion, next reactive guard, github-repo extraction ([#195](https://github.com/es6kr/skills/issues/195)) ([cd65a85](https://github.com/es6kr/skills/commit/cd65a8519c88f080321d746ef197e90713039fa6))
* **commit-tidy:** add hunk-split topic ([050fc07](https://github.com/es6kr/skills/commit/050fc0783c633967d41713ff29de50613a2da4ac))
* **commit-tidy:** add hunk-split topic + commit-review-trigger hook; PR review findings applied in 67f5cae (stdin JSON parsing, detached-HEAD SHA regex, git apply atomicity note). ([8090e9d](https://github.com/es6kr/skills/commit/8090e9def450fae006f5f0f4ebc2a7e2166a2d49))


### Bug Fixes

* **commit-tidy:** correct commit-review-trigger stdin parsing + hunk-split apply note ([67f5cae](https://github.com/es6kr/skills/commit/67f5caefbdd45bfb264f41e25ed62e13a80b6a50))
* **commit-tidy:** track installed hook commit-review-trigger.sh in resources ([144016a](https://github.com/es6kr/skills/commit/144016a308f79f0751bb47de5480c2f6a2b826a6))

## [0.4.3](https://github.com/es6kr/skills/compare/commit-tidy-v0.4.2...commit-tidy-v0.4.3) (2026-07-16)


### Bug Fixes

* **commit-tidy,fix:** content-over-operation subjects + --local rule scoping ([61ba092](https://github.com/es6kr/skills/commit/61ba0929587bfd74b1f0a081ff9b316846c24969))
* **commit-tidy:** enforce staging discipline for plan-listed files ([27ef87d](https://github.com/es6kr/skills/commit/27ef87d640947c18488173f2d4eaf93d99b13887))
* **commit-tidy:** require content-over-operation subjects for mechanical-operation commits ([7573954](https://github.com/es6kr/skills/commit/7573954c253d1d8bc47672d14f6a4267206ebe64))
* **consolidate,fix-plan:** promote next-fix staging (review hardening + periodic archive) ([24726e9](https://github.com/es6kr/skills/commit/24726e99a5b2972f706d8749ea3a45cbc358984b))

## [0.4.2](https://github.com/es6kr/skills/compare/commit-tidy-v0.4.1...commit-tidy-v0.4.2) (2026-06-30)


### Bug Fixes

* **skills:** add procedural guards + standardize description scalar ([#66](https://github.com/es6kr/skills/issues/66)) ([fcc921f](https://github.com/es6kr/skills/commit/fcc921fba3928aad7421ecff888d5dcee5ae5655))

## [0.4.1](https://github.com/es6kr/skills/compare/commit-tidy-v0.4.0...commit-tidy-v0.4.1) (2026-06-25)


### Bug Fixes

* apply PR [#62](https://github.com/es6kr/skills/issues/62) AI review findings (14) ([8132a2b](https://github.com/es6kr/skills/commit/8132a2b001fbd10e3db618decf989f8cf84b1b6b))
* **commit-tidy:** expand message-discipline + add soft-reset-amend / staging-discipline ([0d792cb](https://github.com/es6kr/skills/commit/0d792cbfc76012bd3f14d45c86766df9fc11dd57))
* **fix:** split Step 2 medium by content type — case history to failed-attempts.md ([#62](https://github.com/es6kr/skills/issues/62)) ([747b3f9](https://github.com/es6kr/skills/commit/747b3f957ca0fefdbc5044eb08f66b8aafc1e26a))

## [0.4.0](https://github.com/es6kr/skills/compare/commit-tidy-v0.3.0...commit-tidy-v0.4.0) (2026-06-12)


### Features

* decompose workflow/git rules + rename web-ui-test→web-browser ([#50](https://github.com/es6kr/skills/issues/50)) ([e10d48f](https://github.com/es6kr/skills/commit/e10d48fea4e507b95888de44812b53484d32128d))

## [0.3.0](https://github.com/es6kr/skills/compare/commit-tidy-v0.2.0...commit-tidy-v0.3.0) (2026-06-03)


### Features

* add metadata block (author, version) to all skills ([a36d9a5](https://github.com/es6kr/skills/commit/a36d9a5f029b595847220c3cc867370c7ff30a21))
* **ci:** add lint jobs and untrack LICENSE ([#7](https://github.com/es6kr/skills/issues/7) Phase 1) ([03a8587](https://github.com/es6kr/skills/commit/03a85872c575c6ffdf72f5ca2bdb353fdc947a73))
* **commit-tidy:** add interactive-amend + soft-reset-amend topics ([1146889](https://github.com/es6kr/skills/commit/11468890f1e557251842c36acca666d4a3604c19))

## [0.2.0](https://github.com/es6kr/skills/compare/commit-tidy-v0.1.1...commit-tidy-v0.2.0) (2026-05-24)


### Features

* **ci:** add lint jobs and untrack LICENSE ([#7](https://github.com/es6kr/skills/issues/7) Phase 1) ([03a8587](https://github.com/es6kr/skills/commit/03a85872c575c6ffdf72f5ca2bdb353fdc947a73))

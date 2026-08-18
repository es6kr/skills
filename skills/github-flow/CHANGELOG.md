# Changelog

## [0.8.3](https://github.com/es6kr/skills/compare/github-flow-v0.8.2...github-flow-v0.8.3) (2026-08-17)


### Bug Fixes

* **github-flow:** CI-gate-only base check before ready-transition claims ([435d43c](https://github.com/es6kr/skills/commit/435d43cd023e91688da8e5ffcd5c3c655605abbb))
* **github-flow:** CI-gate-only base means skip ready transition, not just no review cost ([9418c40](https://github.com/es6kr/skills/commit/9418c408a4503402167bbd17706656f62789a287))
* **github-flow:** forbid raw draft paths in plan-to-issue --body-file ([d0911f0](https://github.com/es6kr/skills/commit/d0911f0f0e742dd7cdf239ce880d4dfce3e0ab9e))
* **github-flow:** require CI-gate-only base check before ready-transition claims ([6a94549](https://github.com/es6kr/skills/commit/6a9454941f40e26a9e7ef544db915c63f3b007cf))
* **github-flow:** require open-PR check before repo-wide fix work ([#329](https://github.com/es6kr/skills/issues/329)) ([5da8855](https://github.com/es6kr/skills/commit/5da88554a3e425738ef5003e20ff32b96d96b4a5))
* **github-flow:** verify PR creation via authoritative commit fields, not diff listing ([568ec87](https://github.com/es6kr/skills/commit/568ec874e2ad18f88b1c45bcc15e809786f5822d))
* plan-to-issue frontmatter guard, cleanup gap-baseline sync, pre-commit placeholder exemption ([20e1698](https://github.com/es6kr/skills/commit/20e1698b3b3ee435b8c2705dfe32124567eedd29))
* promote next-fix staging (30 fixes across 14 skills) ([ee467c0](https://github.com/es6kr/skills/commit/ee467c045d779d7b80d30f160763ec3534a9742b))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([4982364](https://github.com/es6kr/skills/commit/49823641a7b08123ebd0325273892bee41bc3280))

## [0.8.2](https://github.com/es6kr/skills/compare/github-flow-v0.8.1...github-flow-v0.8.2) (2026-08-09)


### Bug Fixes

* **consolidate:** address CodeRabbit/Copilot review findings on PR [#270](https://github.com/es6kr/skills/issues/270) ([3b11a73](https://github.com/es6kr/skills/commit/3b11a730b5ad68803d35a8264eda540e48265d75))
* declare undeclared skill-to-skill dependencies (7 skills) ([#271](https://github.com/es6kr/skills/issues/271)) ([36a9f9d](https://github.com/es6kr/skills/commit/36a9f9d7c1fac9bb1c4c96b325a067ab92ad0da7))
* **github-flow:** add merged-PR/stale-tracker branch to review-apply.md ([#237](https://github.com/es6kr/skills/issues/237)) ([5a880fb](https://github.com/es6kr/skills/commit/5a880fb936cc474ea791f2fa2e24edc2fd018142))
* **github-flow:** align merge.md evidence format with fix-plan/format.md schema ([#244](https://github.com/es6kr/skills/issues/244)) ([ea609cf](https://github.com/es6kr/skills/commit/ea609cf3a1725298383d96a297252f19596d0e10))
* **github-flow:** always disclose commit list in merge asks, not just 3+-commit ones ([#248](https://github.com/es6kr/skills/issues/248)) ([8c19508](https://github.com/es6kr/skills/commit/8c19508d6b3967af783fb372d452fecceec6953c))
* **github-flow:** document rebase-conflict cost of squashing distinct-concern PRs ([#245](https://github.com/es6kr/skills/issues/245)) ([dc6cb34](https://github.com/es6kr/skills/commit/dc6cb3417ae945c8e9393d18d700aa6eccb0dfd5))
* **github-flow:** gate squash-merge recommendation on commit count/distinctness ([45176ab](https://github.com/es6kr/skills/commit/45176ab8ee4d7a9e80c58f4062035e64143bc1bf))
* promote accumulated next-fix fixes to main ([95656e9](https://github.com/es6kr/skills/commit/95656e9b551ee0bb77904a0a571d49c53bc01cc9))

## [0.8.1](https://github.com/es6kr/skills/compare/github-flow-v0.8.0...github-flow-v0.8.1) (2026-08-05)


### Bug Fixes

* **github-flow:** correct stale five/four-condition wording after 6th gate added ([738e92e](https://github.com/es6kr/skills/commit/738e92ed078e6c5f81cdc2325f7b85e91d830d14))
* promote next-fix staging (38 fixes across 16 skills) ([94f8c33](https://github.com/es6kr/skills/commit/94f8c33800ce411ae63e22c5259cdae8435508a4))

## [0.8.0](https://github.com/es6kr/skills/compare/github-flow-v0.7.0...github-flow-v0.8.0) (2026-08-03)


### Features

* **github-flow:** add publish topic ([#206](https://github.com/es6kr/skills/issues/206)) ([4aba1b6](https://github.com/es6kr/skills/commit/4aba1b63fdf7357b636118a30d674a0f7db71706))
* promote next-feat to main ([4fbe313](https://github.com/es6kr/skills/commit/4fbe31332c58bf24327d819cc9204ebda2d4afa8))

## [0.7.0](https://github.com/es6kr/skills/compare/github-flow-v0.6.1...github-flow-v0.7.0) (2026-07-23)


### Features

* **hook-kit:** add pre-tool AskUserQuestion context gate ([#123](https://github.com/es6kr/skills/issues/123)) ([271b5b3](https://github.com/es6kr/skills/commit/271b5b37df5e64cf3185b2c81c3d97b66789e9ab))


### Bug Fixes

* **next-fix:** accumulate bug fixes for docxport, wip, fix-plan, and hook-kit ([6eec083](https://github.com/es6kr/skills/commit/6eec083b7fbc429bdabcfcc89d7778b185dd7497))
* skills body bundle — consolidate/fix/hook-kit refinements + English-clean guard hooks (Ralph-loop bypass) ([2e26f41](https://github.com/es6kr/skills/commit/2e26f412a5b963984898e13caaca186c3617ca08))

## [0.6.1](https://github.com/es6kr/skills/compare/github-flow-v0.6.0...github-flow-v0.6.1) (2026-07-19)


### Bug Fixes

* externalize internal-host detection tokens (edit-guard + sanitize doc) ([0bb7f83](https://github.com/es6kr/skills/commit/0bb7f831c752ecc5272611da752325f44e3c32a6))

## [0.6.0](https://github.com/es6kr/skills/compare/github-flow-v0.5.0...github-flow-v0.6.0) (2026-07-17)


### Features

* **github-flow:** add auth-scope, commit-message-discipline topics + review-as.sh script ([907d730](https://github.com/es6kr/skills/commit/907d7307de59725bd15af0a6a64ca4906406242e))
* **github-flow:** add gh-as.sh wrapper for command-scoped gh account switching ([#97](https://github.com/es6kr/skills/issues/97)) ([cd043ed](https://github.com/es6kr/skills/commit/cd043ed54ed5aaa351e65dbe804fededc1842556))
* promote next-feat to main (hook-kit, github-flow, claude-session, todowrite, claudify, cleanup) ([7c598eb](https://github.com/es6kr/skills/commit/7c598ebdbfdb21cf421e8f814ea1a2513ad27a58))


### Bug Fixes

* **github-flow:** genericize private-org name in sanitize.md example ([0acc74a](https://github.com/es6kr/skills/commit/0acc74abc3aeee4de086e4a099b458759b74dda0))
* **github-flow:** harden identity-auth/merge/plan-to-issue/pr/register/sanitize topics ([3458595](https://github.com/es6kr/skills/commit/3458595fbacf8bf21eb474c60f721c5111753291))
* **github-flow:** per-ref evidence gate for mixed-result push output ([ed2d643](https://github.com/es6kr/skills/commit/ed2d6438f64d1a3bc4ce0166717b72b164cdf309))

## [0.5.0](https://github.com/es6kr/skills/compare/github-flow-v0.4.3...github-flow-v0.5.0) (2026-07-07)


### Features

* **docxport:** promote initial registration to main ([8265ba3](https://github.com/es6kr/skills/commit/8265ba33b13ab6054c3595943d068f5c1c13625a))
* **github-flow,next:** draft-PR default + sync remaining pr-review→pr topic refs ([ca64425](https://github.com/es6kr/skills/commit/ca644253c8b84b41f8a90d7869ac16fa8c7c7124))
* **github-flow:** add epic-bundle topic row + [e2e]/[deploy] test plan prefixes + branch verification ([31d629f](https://github.com/es6kr/skills/commit/31d629fa405639995a53ec8296ff95f33672b435))
* **skills:** drift sync bundle — cc-plugin/github-flow/wip/next/check-hangul ([ac5d15d](https://github.com/es6kr/skills/commit/ac5d15d7231e67b3b53cae3861bb6132a2f3beff))

## [0.4.3](https://github.com/es6kr/skills/compare/github-flow-v0.4.2...github-flow-v0.4.3) (2026-07-03)


### Bug Fixes

* **github-flow:** update stale pr-review topic refs to pr after archive ([1e6c0ad](https://github.com/es6kr/skills/commit/1e6c0ad27fa75be13690343b32b3d05e9f4869a4))
* **skills:** patch bundle — consolidate/next/fix/skill-kit/github-flow ([3cb90cb](https://github.com/es6kr/skills/commit/3cb90cb7601f619b63518860bebfb693d58a7633))

## [0.4.2](https://github.com/es6kr/skills/compare/github-flow-v0.4.1...github-flow-v0.4.2) (2026-06-25)


### Bug Fixes

* apply PR [#62](https://github.com/es6kr/skills/issues/62) AI review findings (14) ([8132a2b](https://github.com/es6kr/skills/commit/8132a2b001fbd10e3db618decf989f8cf84b1b6b))
* **fix:** split Step 2 medium by content type — case history to failed-attempts.md ([#62](https://github.com/es6kr/skills/issues/62)) ([747b3f9](https://github.com/es6kr/skills/commit/747b3f957ca0fefdbc5044eb08f66b8aafc1e26a))
* **github-flow:** split [e2e] into PR-CI required vs [deploy] deploy-gated ([f7cdada](https://github.com/es6kr/skills/commit/f7cdada2c06ea0608f1d73aaa8c53fa2d48a5143))
* **github-flow:** translate Artifacts references to English ([1bc17a4](https://github.com/es6kr/skills/commit/1bc17a4e30ddb81f110c4f2cc2d5f232affade4e))

## [0.4.1](https://github.com/es6kr/skills/compare/github-flow-v0.4.0...github-flow-v0.4.1) (2026-06-19)


### Bug Fixes

* bundle skill patches across github-flow, skill-kit, fix ([0ef74c1](https://github.com/es6kr/skills/commit/0ef74c14aabfbdc2f802c34b3a1b431217e95208))
* **github-flow:** abstract ralph references and priority-compatible BLOCKED grep ([b735f41](https://github.com/es6kr/skills/commit/b735f41ccd4b6fedd980895a07b59f7ba3068864))
* **github-flow:** add PR lifecycle guards across identity, workflow YAML, merge, and push ([5c5bc86](https://github.com/es6kr/skills/commit/5c5bc86a1ee1b6fe1bbae8e416afe5b31b790829))
* **skill-kit,github-flow:** address CodeRabbit + Internal Review feedback on PR [#54](https://github.com/es6kr/skills/issues/54) ([c5c741d](https://github.com/es6kr/skills/commit/c5c741da5631a042860e684580d1c92687b59eec))

## [0.4.0](https://github.com/es6kr/skills/compare/github-flow-v0.3.0...github-flow-v0.4.0) (2026-06-12)


### Features

* decompose workflow/git rules + rename web-ui-test→web-browser ([#50](https://github.com/es6kr/skills/issues/50)) ([e10d48f](https://github.com/es6kr/skills/commit/e10d48fea4e507b95888de44812b53484d32128d))

## [0.3.0](https://github.com/es6kr/skills/compare/github-flow-v0.2.0...github-flow-v0.3.0) (2026-06-01)


### Features

* **github-flow:** multi-topic structure + English body + internal-id sanitization ([#39](https://github.com/es6kr/skills/issues/39)) ([881aaf3](https://github.com/es6kr/skills/commit/881aaf3be5cd57edf3173e88f40273ccd3640330))

## [0.2.0](https://github.com/es6kr/skills/compare/github-flow-v0.1.0...github-flow-v0.2.0) (2026-05-24)


### Features

* **ci:** add lint jobs and untrack LICENSE ([#7](https://github.com/es6kr/skills/issues/7) Phase 1) ([03a8587](https://github.com/es6kr/skills/commit/03a85872c575c6ffdf72f5ca2bdb353fdc947a73))
* publish 7 new skills, update 4 existing skills ([dce016d](https://github.com/es6kr/skills/commit/dce016da291f4c9da03746f8be668fa5db04e578))


### Bug Fixes

* address CodeRabbit review findings on PR [#4](https://github.com/es6kr/skills/issues/4) ([bbaefdc](https://github.com/es6kr/skills/commit/bbaefdc8a88f26b0b072e115d0696e732ac52e0c))

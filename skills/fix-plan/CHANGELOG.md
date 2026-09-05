# Changelog

## [0.11.1](https://github.com/es6kr/skills/compare/fix-plan-v0.11.0...fix-plan-v0.11.1) (2026-09-05)


### Bug Fixes

* **fix-plan:** add simple-vs-session self-check before Orca recommendation ask ([46e5d77](https://github.com/es6kr/skills/commit/46e5d77e3faefb0524fb4e4e6e80aa056d2d66ca))
* **fix-plan:** hold the update lock across the write and reject invalid section markers ([b70f95d](https://github.com/es6kr/skills/commit/b70f95d3de46f0b78ff432c007c47ff798b3b54c))
* **fix-plan:** move the update lock out of the tracker's directory ([da58b2d](https://github.com/es6kr/skills/commit/da58b2d9081c6e1bbfad12d55078749a329a43a8))
* **fix-plan:** require RAG pre-lookup before authoring add/upsert items ([#419](https://github.com/es6kr/skills/issues/419)) ([1cff476](https://github.com/es6kr/skills/commit/1cff4767b37443fa57ff7841da3ee6a1bd9e81c0))
* **fix-plan:** resolve remaining PR [#407](https://github.com/es6kr/skills/issues/407) review findings ([708475b](https://github.com/es6kr/skills/commit/708475bd3a882d3c27dd29f3e7b594f53f961e24))

## [0.11.0](https://github.com/es6kr/skills/compare/fix-plan-v0.10.0...fix-plan-v0.11.0) (2026-09-01)


### Features

* staging branch next-feat sync into main ([e582ea2](https://github.com/es6kr/skills/commit/e582ea248beefa70886716741b8965d91cfb7414))


### Bug Fixes

* **fix-plan:** recommend Orca session-launch on pm-profile handoff ([dbbde8a](https://github.com/es6kr/skills/commit/dbbde8a74709b963c62adfc880884fdf02830c17))
* **fix-plan:** warn against issue-comments-only AI Review Summary check ([#401](https://github.com/es6kr/skills/issues/401)) ([2ec416d](https://github.com/es6kr/skills/commit/2ec416d1e1a7c518747ea0f4fd3cb568694c9cb5))

## [0.10.0](https://github.com/es6kr/skills/compare/fix-plan-v0.9.1...fix-plan-v0.10.0) (2026-08-29)


### Features

* **backlog:** migrate prune_p2p3.py to backlog and implement Option A+B (anchored regex & anomaly gate) ([7bc4fd1](https://github.com/es6kr/skills/commit/7bc4fd197fb5f9cc8bb2b662a8f72f02ed827b9b))
* promote next-feat batch (backlog skill, hooks JS port, git-repo doctor, pre-push guard) ([0d76a4c](https://github.com/es6kr/skills/commit/0d76a4c01180fbdc78bfeec8dea91373b4912470))
* **works-config:** implement v0.2.0 role-based resolution & neutral SSOT guards config ([e22e117](https://github.com/es6kr/skills/commit/e22e117371370c59b18b77c72bdb926dcb1897cb))


### Bug Fixes

* address CodeRabbit and Copilot review feedback on PR [#385](https://github.com/es6kr/skills/issues/385) ([e94de34](https://github.com/es6kr/skills/commit/e94de34ce5e075c79b7edc5d672813cea94a0acc))
* address CodeRabbit and Copilot review feedback on PR [#389](https://github.com/es6kr/skills/issues/389) ([db4dfff](https://github.com/es6kr/skills/commit/db4dfff2829632bf263d93e0bbfdd1244772a5b2))
* **fix-plan:** resolve full list-item block before toggling a sync marker ([#378](https://github.com/es6kr/skills/issues/378)) ([342d414](https://github.com/es6kr/skills/commit/342d4146b919c64ddf3d89c211e3e3e44bce2477))
* **hook-kit:** add conditional-deferral gate to check-ask-bypass-keywords.sh ([1a32fe0](https://github.com/es6kr/skills/commit/1a32fe0c716ec4583a09a54004fb9fb86191ea1c))
* **hook-kit:** add conditional-deferral gate to check-ask-bypass-keywords.sh ([49cae3f](https://github.com/es6kr/skills/commit/49cae3f96f08cc54c6dadf4eaf99369e0e9750ef))
* **hook-kit:** document --json mode and scope WSCFG_* to hook scripts ([373634c](https://github.com/es6kr/skills/commit/373634c022b0e2b114a3bbb799bb9a8934c9fbb2))
* **hook-kit:** scope PR-URL bare-ref check to per-number match, allow force-push in worktrees ([dd50dce](https://github.com/es6kr/skills/commit/dd50dced989eed4847daaf9a0cd4be12a04426e1))
* promote next-fix batch (task plugin split, claudify matcher, pr recheck, omz chezmoi fix) ([3e90fd5](https://github.com/es6kr/skills/commit/3e90fd56ade0522d6773eb03f38760a317dd5180))
* **review:** apply copilot review feedback on hooks and test suites ([cba86f4](https://github.com/es6kr/skills/commit/cba86f4ebbf274a0c979ab21aeea6d483f8cb8f3))


### Refactor

* **hooks:** port check-completed-bloat and wip-task-complete-detect to Node.js ([7097526](https://github.com/es6kr/skills/commit/7097526ca208c3106b38a3ac5c317d0eb49eff30))

## [0.9.1](https://github.com/es6kr/skills/compare/fix-plan-v0.9.0...fix-plan-v0.9.1) (2026-08-26)


### Bug Fixes

* accumulate 16 patch-level bug fixes and guard enhancements across skills ([d214e5d](https://github.com/es6kr/skills/commit/d214e5dcc7fac1bc07baf3b6cec62999aea732f0))
* **fix-plan:** accept ASCII arrow delimiter in plane_sync index lines ([c2fd069](https://github.com/es6kr/skills/commit/c2fd06927ab253b81566047f7bfa9ccded7a97d9))
* **fix-plan:** decouple plane_create_issue to plane-backlog and update schema validation ([42273f4](https://github.com/es6kr/skills/commit/42273f46180b0f13bf7e094f6c5bb75adda6ad45))
* **fix-plan:** judge item schema against the file, not the edit window ([e619e33](https://github.com/es6kr/skills/commit/e619e337064687ccb5d79a304a0737004d9d0cda))
* **fix-plan:** parse nested hooks.json schema in hook_integrity_check ([b9bde23](https://github.com/es6kr/skills/commit/b9bde23cf4a60dee28b8ea43462c4d37200e33f4))
* **fix-plan:** require recency-ask answer reuse in default-invocation Step 0 ([c7ad963](https://github.com/es6kr/skills/commit/c7ad963223e50e187442f7eeb271a75baafd4c96))
* **fix-plan:** resolve plane_bulk_update config from workspace profile ([35a664b](https://github.com/es6kr/skills/commit/35a664b460834f4fb2185a48e3b040d72a6707d6))
* **fix-plan:** stop cleanup from dropping non-list lines and the final newline ([36106d1](https://github.com/es6kr/skills/commit/36106d1be814529df933f1a480e3a6bc815dc783))
* promote accumulated skill fixes from the working checkout ([770bed2](https://github.com/es6kr/skills/commit/770bed2386266fc13f7d605505c2996037d4c371))
* promote next-fix batch (consolidate fabrication guard, session rewind, config-driven PR base) ([7ca0ccb](https://github.com/es6kr/skills/commit/7ca0ccbf13cefafedc33a16a7361756c95f8b8f6))
* resolve PR [#363](https://github.com/es6kr/skills/issues/363) audit Pending findings (plane_bulk_update profile, hook checker schema, regex, dedup) ([19ffc83](https://github.com/es6kr/skills/commit/19ffc83f296ad5568b82a85b104fcf419580c102))
* **review-feedback:** apply review feedback for session rewind, cleanup regex, rag test, and resume urls ([543d88f](https://github.com/es6kr/skills/commit/543d88f189c415c5f7a911aa861cde9b382016bd))

## [0.9.0](https://github.com/es6kr/skills/compare/fix-plan-v0.8.0...fix-plan-v0.9.0) (2026-08-20)


### Features

* **fix-plan:** read the role-shaped v2 workspace config, falling back to v1 ([83ec4f0](https://github.com/es6kr/skills/commit/83ec4f016d1f99c00ffa2d612a0b49e7467d48a5))
* promote next-feat batch (hook registry schema, self-reference path anchoring) ([0c33ffa](https://github.com/es6kr/skills/commit/0c33ffac99a9237f4530566470dabeaea128c209))
* promote next-feat staging (lifecycle guards, triage automation, and workflow safety procedures) ([77d58ac](https://github.com/es6kr/skills/commit/77d58ac3a771a4897043c9eea8b149ea1e8ba2ff))


### Bug Fixes

* **cleanup,fix-plan:** anchor script paths to the skill directory ([8a2f9be](https://github.com/es6kr/skills/commit/8a2f9be6f5bba1f9a9ec35ca2616fabf7addf847))
* **fix-plan,cleanup:** replace absolute self-reference script paths with relative form ([91e99e2](https://github.com/es6kr/skills/commit/91e99e2f4f2657b7646a886d4d98ec5e2dbb09c0))
* **fix-plan,cleanup:** replace absolute self-reference script paths with relative form ([8b6a1e6](https://github.com/es6kr/skills/commit/8b6a1e627584866cef43f1866548f3ef32d2a849))
* **fix-plan:** add add_item.py and track the checklist-edit guard ([#339](https://github.com/es6kr/skills/issues/339)) ([b9bbc08](https://github.com/es6kr/skills/commit/b9bbc0829f23ecf8b63d0d4e0f65888dcac5344e))
* **fix-plan:** match multi-segment cwd_match tokens in workspace_profile ([90f942a](https://github.com/es6kr/skills/commit/90f942a25a668b778bedde9d28996c102e91966f))
* **fix-plan:** reconcile plane_create_issue with the repaired plane-backlog copy and inject User-Agent into plane_sync ([69cce36](https://github.com/es6kr/skills/commit/69cce36f645c3106e4bea2c8305330978785f37f))
* **fix-plan:** require artifact verification for subagent-delegated pipeline runs ([7a4e1c0](https://github.com/es6kr/skills/commit/7a4e1c0cb6b8065e4dd3ed3079923967e1d545dc))
* **hook-kit,fix-plan,consolidate:** resolve review findings on registry fail-fast, add-item safety, and mechanical verification ([72fb280](https://github.com/es6kr/skills/commit/72fb28054ccd858aa56617e8a6a5d1fb5b9d2384))
* **hook-kit:** detect v2 config by version, not per-profile roles; probe interpreter in RAG guard ([13042e6](https://github.com/es6kr/skills/commit/13042e6f95ee3e566dd4e029d029bfdcfdb34de6))
* promote next-fix batch (hook path repair, topic-dispatch scoping, conflict diagnosis) ([eb7ecb6](https://github.com/es6kr/skills/commit/eb7ecb61dda9701d78f12dc810781dc7cb687caa))
* repair plane script defects — WAF-safe User-Agent + K3s fallback template ([d8c2871](https://github.com/es6kr/skills/commit/d8c287132867b88225e01f5031e658df1e05d027))

## [0.8.0](https://github.com/es6kr/skills/compare/fix-plan-v0.7.0...fix-plan-v0.8.0) (2026-08-17)


### Features

* **plane-backlog:** add Plane backlog skill with client and indexify scripts ([3bcc8cd](https://github.com/es6kr/skills/commit/3bcc8cd8f570bb53697f290e9e6e53069991822b))


### Bug Fixes

* **fix-plan:** add relocated es6kr skill path to post-ingest fallback chain ([56a8e74](https://github.com/es6kr/skills/commit/56a8e7454f64d70404f393f0ec34ba38a2f7d4ad))
* **fix-plan:** compress SKILL.md description under the 1024-char lint budget ([28edaf2](https://github.com/es6kr/skills/commit/28edaf211196f174adb5f6313356447301dea70b))
* **fix-plan:** keep open plan checklist items as tracker sub-checkboxes on add ([963a4d5](https://github.com/es6kr/skills/commit/963a4d59c01ceb8303156e5b27bcff8ab072394b))
* **fix-plan:** require artifact verification for subagent-delegated pipeline runs ([#333](https://github.com/es6kr/skills/issues/333)) ([44dbf54](https://github.com/es6kr/skills/commit/44dbf5459390efc12b91a1334a1b23542b38aa10))
* **fix-plan:** restore artifact-verification HARD STOP dropped by main merge ([084c669](https://github.com/es6kr/skills/commit/084c66908bceea07f067b9308c15ae88ed206766))
* promote next-fix staging (30 fixes across 14 skills) ([ee467c0](https://github.com/es6kr/skills/commit/ee467c045d779d7b80d30f160763ec3534a9742b))
* **wip:** cross-ref PR-URL and TaskCreate subject repo-qualifier rules ([#186](https://github.com/es6kr/skills/issues/186)) ([4982364](https://github.com/es6kr/skills/commit/49823641a7b08123ebd0325273892bee41bc3280))

## [0.7.0](https://github.com/es6kr/skills/compare/fix-plan-v0.6.2...fix-plan-v0.7.0) (2026-08-16)


### Features

* **fix-plan:** add claim topic — multi-session in-progress lease ([#300](https://github.com/es6kr/skills/issues/300)) ([7bd1439](https://github.com/es6kr/skills/commit/7bd14396cef45738207d400053c8e8aade8d3c94))
* merge next-feat into main ([#313](https://github.com/es6kr/skills/issues/313)) ([2d9308a](https://github.com/es6kr/skills/commit/2d9308ab3e7e0086a88a7f64d3ed4d5c4d36e017))

## [0.6.2](https://github.com/es6kr/skills/compare/fix-plan-v0.6.1...fix-plan-v0.6.2) (2026-08-12)


### Bug Fixes

* **fix-plan:** reclassify model-triage BLOCKED marker as external, not selfable ([#291](https://github.com/es6kr/skills/issues/291)) ([60e687c](https://github.com/es6kr/skills/commit/60e687c36a9e9b16493d8c48711bf14cf01d3441))
* **fix-plan:** route cleanup.py and plane_sync.py through resolve_tracker_root ([#285](https://github.com/es6kr/skills/issues/285)) ([a42af9d](https://github.com/es6kr/skills/commit/a42af9d02cf2f56d9ae082ae7594976484bd7baa))
* promote accumulated next-fix fixes to main ([803bbd3](https://github.com/es6kr/skills/commit/803bbd3b9e4f8367ee1b955cfa2b6a536f85cee0))

## [0.6.1](https://github.com/es6kr/skills/compare/fix-plan-v0.6.0...fix-plan-v0.6.1) (2026-08-11)


### Bug Fixes

* **fix-plan:** resolve Plane issue state via separate states endpoint ([a027c74](https://github.com/es6kr/skills/commit/a027c744bf142fd1b6aec5275d372ba705e6c37d))

## [0.6.0](https://github.com/es6kr/skills/compare/fix-plan-v0.5.1...fix-plan-v0.6.0) (2026-08-09)


### Features

* **fix-plan:** implement plane_sync.py as a real Plane sync engine ([a901895](https://github.com/es6kr/skills/commit/a90189595e3d3487509c4fd0b4889630e438bc39))
* **fix-plan:** implement plane_sync.py as a real Plane sync engine ([4607f13](https://github.com/es6kr/skills/commit/4607f13c15e3572e904dd56b56b4ce36ed462d26))


### Bug Fixes

* **consolidate:** address CodeRabbit/Copilot review findings on PR [#270](https://github.com/es6kr/skills/issues/270) ([3b11a73](https://github.com/es6kr/skills/commit/3b11a730b5ad68803d35a8264eda540e48265d75))
* **fix-plan:** externalize detect_bloated_tasks.py locale patterns to git-ignored data/ ([#258](https://github.com/es6kr/skills/issues/258)) ([0616217](https://github.com/es6kr/skills/commit/0616217a779aac7471e841626e22ba058d16d28f))
* **fix-plan:** guard plane_sync.py write against concurrent tracker edits ([0d34339](https://github.com/es6kr/skills/commit/0d343399d6a7c9f97114c5e85254e65ed93e9d67))
* **fix-plan:** workspace-aware tracker root + broaden stale_check detection ([#255](https://github.com/es6kr/skills/issues/255)) ([b6d041a](https://github.com/es6kr/skills/commit/b6d041a2babb5ed8d9c29979eef96fa4a4fa92ab))
* promote accumulated next-fix fixes to main ([95656e9](https://github.com/es6kr/skills/commit/95656e9b551ee0bb77904a0a571d49c53bc01cc9))

## [0.5.1](https://github.com/es6kr/skills/compare/fix-plan-v0.5.0...fix-plan-v0.5.1) (2026-08-05)


### Bug Fixes

* promote next-fix staging (38 fixes across 16 skills) ([94f8c33](https://github.com/es6kr/skills/commit/94f8c33800ce411ae63e22c5259cdae8435508a4))

## [0.5.0](https://github.com/es6kr/skills/compare/fix-plan-v0.4.0...fix-plan-v0.5.0) (2026-08-03)


### Features

* promote next-feat to main ([4fbe313](https://github.com/es6kr/skills/commit/4fbe31332c58bf24327d819cc9204ebda2d4afa8))

## [0.4.0](https://github.com/es6kr/skills/compare/fix-plan-v0.3.3...fix-plan-v0.4.0) (2026-07-28)


### Features

* bundle next-feat — fix-plan expansion, next reactive guard, github-repo extraction ([#195](https://github.com/es6kr/skills/issues/195)) ([cd65a85](https://github.com/es6kr/skills/commit/cd65a8519c88f080321d746ef197e90713039fa6))
* **fix-plan:** add flowchart layout-ordering with invisible priority columns ([#158](https://github.com/es6kr/skills/issues/158)) ([a216c97](https://github.com/es6kr/skills/commit/a216c97d727e15f88507e866d1c81dc95857a121))
* **fix-plan:** add model-triage and completion-criteria topics ([38ccd87](https://github.com/es6kr/skills/commit/38ccd87da8a4c09c752f8b9023a0236da77ebb77))
* **fix-plan:** add model-triage, completion-criteria, and Plane sync ([f47246a](https://github.com/es6kr/skills/commit/f47246ad158add45448e93734abf3d7414971561))
* **fix-plan:** add Plane REST API sync and multi-workspace profile engine ([3a74bd7](https://github.com/es6kr/skills/commit/3a74bd76f64903eb8582fba17be28c4e128207cf))
* **fix-plan:** harden Completed lifecycle and forbid section-header fragmentation ([5fffdfc](https://github.com/es6kr/skills/commit/5fffdfc252830068685385d297761052618d1cfe))
* **fix-plan:** scope default invocation by role-profile (--role=pm|deep|impl) ([d290c7a](https://github.com/es6kr/skills/commit/d290c7ad4145860ced78f35e7483a21595688695))


### Bug Fixes

* **fix-plan:** add secondary-tracker sync cadence contract ([5f0cea9](https://github.com/es6kr/skills/commit/5f0cea9749fe735c0d3fb061afe08212162cd93f))
* **fix-plan:** add secondary-tracker sync cadence contract ([f7b1ee5](https://github.com/es6kr/skills/commit/f7b1ee5c9c151e9cebe46bef0dbc4e024b7f9ed8))
* **fix-plan:** add whole-file grep sub-step to flowchart Sync procedure ([7fb859f](https://github.com/es6kr/skills/commit/7fb859facdb057e29e63f60a7e0cc3457c2d8686))
* **fix-plan:** block stale-Completed edits with exit 2, add python fallback ([7dfc178](https://github.com/es6kr/skills/commit/7dfc178d85212ffe585f42482bc49565a6e9c38d))
* **fix-plan:** correct plane_sync.py's docstring to match its actual scope ([b26a76e](https://github.com/es6kr/skills/commit/b26a76eb9ae2b9f9c3bcb5c68bd119fb2b9ca84e))
* **fix-plan:** document secondary-sync-receiver in Configuration table ([c975300](https://github.com/es6kr/skills/commit/c9753004f53fa89e3383c076b714b69d696dbf14))
* **fix-plan:** document secondary-sync-receiver in Configuration table ([39492c0](https://github.com/es6kr/skills/commit/39492c03d4e0be0946acc1bdd0307d23eab820fb))
* **fix-plan:** document secondary-sync-receiver in Configuration table ([#165](https://github.com/es6kr/skills/issues/165)) ([c975300](https://github.com/es6kr/skills/commit/c9753004f53fa89e3383c076b714b69d696dbf14))
* **fix-plan:** forbid hybrid pending/blocked marker in tracker schema ([f1bfcd8](https://github.com/es6kr/skills/commit/f1bfcd83137f6e80156896ebbcd32e2548c75a59))
* **fix-plan:** forbid hybrid pending/blocked marker in tracker schema ([9262ce0](https://github.com/es6kr/skills/commit/9262ce0665fdb9f72b82f6272a40a48ed5abdfae))
* **fix-plan:** implement register_tasks_to_fix_plan write-back ([cb6d351](https://github.com/es6kr/skills/commit/cb6d351c35209665602258fb4b5a1c6ec57d65d3))
* **fix-plan:** kill schema-hook insert-before false positive + add draft promote premise re-check ([#143](https://github.com/es6kr/skills/issues/143)) ([e826d59](https://github.com/es6kr/skills/commit/e826d5923c491ac6b8a5f915694e751fedf65756))
* **fix-plan:** preserve subtree children when moving completed entries ([080a61d](https://github.com/es6kr/skills/commit/080a61dbe244a2fbd8d3fa8dbf85938a146a037c))
* **fix-plan:** reconcile default-pipeline order across SKILL.md/format.md ([7a3aea5](https://github.com/es6kr/skills/commit/7a3aea5d282a3933e18be341ee2508b6085eab55))
* **fix-plan:** register tasks before default-invocation pipeline runs ([#168](https://github.com/es6kr/skills/issues/168)) ([e796862](https://github.com/es6kr/skills/commit/e796862a558f72c4c9094a7b50f8ae93c6c492bd))
* **fix-plan:** require full session UUID in Completed references ([90f8c3f](https://github.com/es6kr/skills/commit/90f8c3f7daf8d713d3d91c927fdbda11805b36b2))
* **next-fix:** promote staged fixes across hook-kit, next, cleanup, fix-plan ([34f1c67](https://github.com/es6kr/skills/commit/34f1c67beee3a8279e0e80de4ab3a87ba2223d5c))
* resolve PR [#197](https://github.com/es6kr/skills/issues/197) review findings (CodeRabbit + Copilot + Internal Review) ([b54236a](https://github.com/es6kr/skills/commit/b54236a4fa4b3fef23645dfc3b184916980b7f65))

## [0.3.3](https://github.com/es6kr/skills/compare/fix-plan-v0.3.2...fix-plan-v0.3.3) (2026-07-23)


### Bug Fixes

* **fix-plan:** record model name alongside session ID in move.md ([#126](https://github.com/es6kr/skills/issues/126)) ([78b5471](https://github.com/es6kr/skills/commit/78b5471f26b51dd7dc523d7fc1b4e96d7cd77d9c))
* **next-fix:** accumulate bug fixes for docxport, wip, fix-plan, and hook-kit ([6eec083](https://github.com/es6kr/skills/commit/6eec083b7fbc429bdabcfcc89d7778b185dd7497))

## [0.3.2](https://github.com/es6kr/skills/compare/fix-plan-v0.3.1...fix-plan-v0.3.2) (2026-07-16)


### Bug Fixes

* **consolidate,fix-plan:** promote next-fix staging (review hardening + periodic archive) ([24726e9](https://github.com/es6kr/skills/commit/24726e99a5b2972f706d8749ea3a45cbc358984b))
* **fix-plan:** add receiver-independent periodic archive for Completed section ([#73](https://github.com/es6kr/skills/issues/73)) ([122b179](https://github.com/es6kr/skills/commit/122b179d381f33f8345848f2a364c01ce8cb0ab1))
* **fix-plan:** batch GitHub API queries and allow automated cleanup ([8f35c45](https://github.com/es6kr/skills/commit/8f35c4588d465acffa58f19f61795c364936688f))
* **fix-plan:** guard subtree-archival against burying open children ([#91](https://github.com/es6kr/skills/issues/91)) ([3389987](https://github.com/es6kr/skills/commit/33899876e1c6f12ee059d19f2f811c27672d3d0c))

## [0.3.1](https://github.com/es6kr/skills/compare/fix-plan-v0.3.0...fix-plan-v0.3.1) (2026-06-25)


### Bug Fixes

* **fix-plan:** require sync as Step 0 of priority triage ([0ce37e9](https://github.com/es6kr/skills/commit/0ce37e9af80e0d453d8441ad730ea2d6d88b226e))
* **fix:** split Step 2 medium by content type — case history to failed-attempts.md ([#62](https://github.com/es6kr/skills/issues/62)) ([747b3f9](https://github.com/es6kr/skills/commit/747b3f957ca0fefdbc5044eb08f66b8aafc1e26a))

## [0.3.0](https://github.com/es6kr/skills/compare/fix-plan-v0.2.0...fix-plan-v0.3.0) (2026-06-19)


### Features

* **fix-plan:** add priority + draft topics + refine move procedure ([c1b3cb5](https://github.com/es6kr/skills/commit/c1b3cb57b3e340bc06fb1639b0542ea9664b8bec))
* skill-kit graph topic + harness Phase 1 + auxiliary improvements ([01437f2](https://github.com/es6kr/skills/commit/01437f2135d5729eee16f074cb77e52b3cb1772c))

## [0.2.0](https://github.com/es6kr/skills/compare/fix-plan-v0.1.0...fix-plan-v0.2.0) (2026-06-11)


### Features

* **fix-plan:** introduce standalone schema/lifecycle skill ([#47](https://github.com/es6kr/skills/issues/47)) ([4c356f8](https://github.com/es6kr/skills/commit/4c356f8daf16bcd78c9cad871e46c686145e845b))

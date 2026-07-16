# consolidate

Consolidate and respond to external PR/issue feedback — gather AI reviews (CodeRabbit, Copilot), classify findings by type and severity, post an AI Review Summary and Formal Review, then register deferred items.

## Installation

```bash
npx skills add es6kr/skills --skill consolidate
```

Browse on ClawHub: <https://clawhub.ai/skills/consolidate>

### Peer skills

`consolidate` depends on `git-repo` and `github-flow`. Install them so all flows work:

```bash
npx skills add es6kr/skills --skill git-repo --skill github-flow
```

It also uses the [`superpowers`](https://github.com/obra/superpowers) plugin for its code-review primitives. Install either the specific skills or the full plugin:

```bash
# Option 1 — just the code-review skills
npx skills add obra/superpowers --skill requesting-code-review --skill receiving-code-review

# Option 2 — the full superpowers plugin (covers the whole dependency tree)
npx skills add obra/superpowers
```

## Usage

Invoke with `/consolidate <topic>` (for example `/consolidate pr <N>`). See [`SKILL.md`](./SKILL.md) for the full topic list and workflow.

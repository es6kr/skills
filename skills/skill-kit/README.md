# skill-kit

Claude Code skill authoring and management — create, lint, merge, upgrade, and route skills, plus multi-topic architecture, dependency-graph, and publishing tooling.

## Installation

```bash
npx skills add es6kr/skills --skill skill-kit
```

Browse on ClawHub: <https://clawhub.ai/skills/skill-kit>

### Peer skills

`skill-kit` depends on `cc-plugin` and `clawhub` (a companion skill for ClawHub publishing). Install the published peer:

```bash
npx skills add es6kr/skills --skill cc-plugin
```

## Usage

Invoke with `/skill-kit <topic>` (for example `/skill-kit lint`). See [`SKILL.md`](./SKILL.md) for the full topic list.

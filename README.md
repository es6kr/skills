# es6kr/skills

Reusable AI coding skills for Claude Code, Cursor, Codex, and Gemini.

## Skills

| Skill | Description |
|-------|-------------|
| [chezmoi](skills/chezmoi/) | Chezmoi dotfile template management |
| [claude-session](skills/claude-session/) | Claude Code session management |
| [claudify](skills/claudify/) | Convert workflows into Claude Code automation |
| [code-workflow](skills/code-workflow/) | Coding workflow with plan-first approach |
| [commit-tidy](skills/commit-tidy/) | Commit splitting and squashing strategies |
| [dotfile](skills/dotfile/) | Dotfile sync with chezmoi, syncthing, and MCP |
| [fix](skills/fix/) | User behavior correction from feedback |
| [git-repo](skills/git-repo/) | Git repository and SourceGit management |
| [mcp-config](skills/mcp-config/) | MCP server configuration management |
| [next-action](skills/next-action/) | Suggest follow-up actions after task completion |
| [omz](skills/omz/) | Oh My Zsh plugin management |
| [repo](skills/repo/) | Project initialization toolkit |
| [skill-kit](skills/skill-kit/) | Skill lifecycle management |
| [tdd](skills/tdd/) | Test-Driven Development workflow |
| [todowrite](skills/todowrite/) | TODO checklist routing |
| [wip](skills/wip/) | In-session work progress tracking |

## Installation

### Claude Code

```bash
claude plugin marketplace add https://github.com/es6kr/skills
claude plugin install es6kr-skills@es6kr-skills
```

### ClawHub

```bash
clawhub install <skill-name>
```

### Context7

```bash
npx ctx7 skills install es6kr/skills --all --global --universal --yes
```

Browse at [context7.com/es6kr/skills](https://context7.com/es6kr/skills)

## Development

```bash
# Run all tests
make test

# Quick frontmatter check
make lint
```

## Author

- **es6.kr** - drumrobot43@gmail.com

## License

MIT

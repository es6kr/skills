---
name: hook-kit
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - archive
  - safe-delete
description: "Hook management. audit - reference/permission/orphan checks (stale references + chmod +x missing + unowned hook detection) [audit.md]. edit - hook script modification + dual-sync [edit.md]. install - install from resources/ to hooks/ + settings.json registration [install.md]. move - move hooks from scripts/ to hooks/ + update settings.json paths [move.md]. remove - remove hook entries from settings.json [remove.md]. Use when: \"hook cleanup\", \"hook audit\", \"hook edit\", \"hook install\", \"hook move\", \"hook remove\", \"install hook\", \"edit hook\", \"edit guard\", \"bash-guard\", \"hook sync\", \"hook permission\", \"orphan hook\", \"chmod +x hook\", \"exit 126\""
allowed-tools:
  - Read
  - Edit
  - Grep
  - Bash(cp:*)
  - Bash(diff:*)
  - Bash(ls:*)
  - Bash(mkdir:*)
  - Bash(mv:*)
  - Bash(bash -n:*)
  - Bash(jq:*)
  - Bash(chmod:*)
  - Bash(test:*)
  - Bash(find:*)
  - AskUserQuestion
---

# Hook Management

Manage hooks and script files in `~/.claude/settings.json`. Includes resource (source) ↔ hooks/ (installed) dual-sync.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| audit | reference/permission/orphan checks (stale + chmod +x + resources matching) | [audit.md](./audit.md) |
| edit | hook script modification + source sync | [edit.md](./edit.md) |
| install | resources → hooks/ installation + settings.json registration | [install.md](./install.md) |
| move | scripts/ → hooks/ migration + path update | [move.md](./move.md) |
| remove | remove hook entries from settings.json | [remove.md](./remove.md) |

## Quick Reference

```bash
/hook audit    # check stale references in hook scripts
/hook edit     # modify hook script + dual-sync
/hook install  # install resources → hooks/
/hook move     # move scripts/ → hooks/
/hook remove   # remove hook
```

## Dual-Sync Structure

```
Source of Truth                    Active (installed)
skills/hook-kit/resources/*.sh ←→  ~/.claude/hooks/*.sh
```

Changes must be reflected on the opposite side. `/hook edit` handles this automatically.

## Display Format

```
SessionStart:
  1. session-id-inject.sh (hooks/)
PreToolUse:Bash:
  2. bash-guard.sh (hooks/)
PostToolUse:Bash:
  3. trigger-PostToolUse.sh (hooks/)
Stop:
  4. trigger-Stop.sh (hooks/)
```

## Rules

- Display by basename, operate by full path
- Validate JSON before completing
- After move/remove, verify settings.json paths match actual files

## Event-specific Output Channel Spec (HARD STOP — verify before writing any hook)

Claude Code hook events each have different stdout/stderr/exit code semantics. **Only a limited set of events expose stdout to the LLM** — for example, stdout markers in Stop hooks are not visible to the LLM. Always consult this table before writing a hook.

| Event | stdout (exit 0) | stderr (exit 2) | JSON `decision` |
|-------|-----------------|----------------|-----------------|
| UserPromptSubmit | ✅ LLM exposed (injected as context) | blocks prompt | — |
| UserPromptExpansion | ✅ LLM exposed | blocks prompt | — |
| SessionStart | ✅ LLM exposed | — | — |
| PreToolUse | debug log only | blocks tool + message LLM exposed | `decision:"block"/"approve"` |
| PostToolUse | debug log only | message LLM exposed | `decision:"block"` |
| Stop | debug log only | blocks stop + message LLM exposed | `decision:"block", reason:"..."` |

**Source**: `https://code.claude.com/docs/en/hooks` official docs — "For most events, stdout is written to the debug log but not shown in the transcript. The exceptions are `UserPromptSubmit`, `UserPromptExpansion`, and `SessionStart`".

### Don't / Do table

| # | Don't | Do (correct alternative) |
|---|-------|--------------------------|
| 1 | In Stop hook, attempt `cat <<EOF ... EOF; exit 0` to deliver message to LLM | `echo '{"decision":"block","reason":"..."}'` or `echo "..." >&2; exit 2` |
| 2 | Skip 5+ true-positive sample tests after registering a hook | Immediately after registration, force-trigger 5+ times → verify marker/message actually appears in transcript |
| 3 | Assume "worked in PreToolUse so it works in Stop too" | Check this table each time. Channel semantics differ per event |
| 4 | Smoke-test only the **condition-detection** logic (e.g. "does it find the missing Skill call?") and trust the **trigger gate** (the marker/keyword that decides whether the hook engages at all) | Test the trigger gate separately with **phrasing variants** — capitalization (`Cleanup` vs `cleanup`), locale synonyms, spacing. A case-sensitive/narrow gate silently no-ops the whole hook: a correct condition check is never reached if the gate never opens. Grep gates default to `grep -qiE` unless case matters (see failed-hooks.md "marker gate case-sensitivity") |

### Two-part smoke test for detection hooks (HARD STOP — before declaring a detection hook done)

A detection hook has **two independent parts**: (a) a **trigger gate** (a marker/keyword regex deciding whether the hook engages) and (b) a **condition check** (the actual thing being enforced). Both must pass real-data smoke tests, and the gate must be tested with phrasing variants — a gate that fails to match a legitimate completion phrase disables the hook regardless of how correct the condition check is.

1. **Gate test**: feed 3+ realistic trigger phrasings including case/locale/spacing variants → gate must open (proceed to condition check) for each.
2. **Condition test**: with the gate open, feed a payload where the enforced condition is violated → must block; and one where it is satisfied → must pass.
3. **False-positive test**: feed 5+ normal responses that mention the topic casually but are NOT the trigger event → must NOT block.

### Self-check (before writing/modifying any hook)

1. Look up the event for the hook being written/modified in this table → classify whether stdout is LLM-exposed
2. For non-exposed events (Stop, PostToolUse, PreToolUse) — are you trying to deliver a message via stdout marker? → change channel (stderr/JSON decision)
3. After registering the hook, verify actual marker/message exposure with 5+ samples. Zero matches = channel defect
4. For detection hooks: did you run the **two-part smoke test** above (gate with phrasing variants + condition present/absent + false-positive set)? A case-sensitive/narrow trigger gate is the silent-no-op failure mode (see failed-hooks.md "marker gate case-sensitivity", cleanup self-compress 5th recurrence)

## skill-trigger Marker Recognition (LLM behavior contract)

When a hook script emits a `<skill-trigger>` marker, the LLM **must execute the named skill via the `Skill` tool**.

### Marker Format

```
<skill-trigger name="cleanup" topic="run">
Run /cleanup run.
</skill-trigger>
```

### Contract

| Marker shape | Required action |
|--------------|-----------------|
| `<skill-trigger name="X">` | Mandatory `Skill("X")` call |
| `<skill-trigger name="X" topic="Y">` | Mandatory `Skill("X", "Y")` call |
| Multiple markers in one hook output | Execute each in order |
| Legacy markers (`BUILD_COMPLETED`, `AUTO_AGENTIFY_CANDIDATE:`) | Same recognition rules apply |

### Channel Requirements (cross-reference Event Channel spec above)

The marker only reaches the LLM if the event surfaces stdout to the transcript (`UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`) or if the hook uses stderr + exit 2 (any event). For non-stdout events (`Stop`, `PreToolUse`, `PostToolUse`), emit the marker via stderr + exit 2, or as the `reason` field of a `{"decision":"block"}` JSON response.

## Default Installer Role

**The hook skill is the default installer for all hook scripts.** Every hook must have an owning skill (with an install procedure), and hooks that have no domain skill are managed by importing them into the hook skill's `resources/`.

| Hook type | Owning skill | resources location |
|-----------|-------------|-------------------|
| Domain-specific (e.g., openclaw, semaphore, ralph related) | Corresponding domain skill | `<domain-skill>/resources/*.sh` |
| General/system (Bash guard, session management, validation) | **hook skill** | `~/.claude/skills/hook-kit/resources/*.sh` |

**Principles**:
- Every `~/.claude/hooks/*.sh` must have been installed from some skill's `resources/` — orphan hooks are forbidden
- If a domain skill uses a hook, that skill's SKILL.md must document the install procedure and the source must live in its `resources/`
- If a hook belongs to no skill → the hook skill takes ownership (import to resources/ + register via install procedure)
- The audit topic detects orphan hooks (installed copies with no resources/ source) and suggests either assigning an owning skill or importing into the hook skill

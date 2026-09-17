REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/task-flow"

@test "task-flow: skill directory and SKILL.md exist" {
  [ -d "$SKILL_DIR" ]
  [ -f "$SKILL_DIR/SKILL.md" ]
}

@test "task-flow: SKILL.md has valid name and metadata.version" {
  run grep -E "^name: task-flow" "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -E '^[[:space:]]*version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "task-flow: pipeline.md and compat-codeworkflow.md exist" {
  [ -f "$SKILL_DIR/pipeline.md" ]
  [ -f "$SKILL_DIR/compat-codeworkflow.md" ]
}

@test "task-flow: pipeline.md binds task-plan and task-exec" {
  run grep -qi "task-plan" "$SKILL_DIR/pipeline.md"
  [ "$status" -eq 0 ]

  run grep -qi "task-exec" "$SKILL_DIR/pipeline.md"
  [ "$status" -eq 0 ]
}

@test "task-flow: compat-codeworkflow.md specifies backward-compatibility for code-workflow" {
  run grep -qi "code-workflow" "$SKILL_DIR/compat-codeworkflow.md"
  [ "$status" -eq 0 ]
}

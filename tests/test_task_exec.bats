REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/task-exec"

@test "task-exec: skill directory and SKILL.md exist" {
  [ -d "$SKILL_DIR" ]
  [ -f "$SKILL_DIR/SKILL.md" ]
}

@test "task-exec: SKILL.md has valid name and metadata.version" {
  run grep -E "^name: task-exec" "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -E '^[[:space:]]*version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "task-exec: all 7 topic documents exist" {
  [ -f "$SKILL_DIR/gate.md" ]
  [ -f "$SKILL_DIR/implement.md" ]
  [ -f "$SKILL_DIR/code-discipline.md" ]
  [ -f "$SKILL_DIR/doc.md" ]
  [ -f "$SKILL_DIR/mail.md" ]
  [ -f "$SKILL_DIR/verify.md" ]
  [ -f "$SKILL_DIR/delivery.md" ]
}

@test "task-exec: gate.md specifies plan acceptance prerequisite gate" {
  run grep -qi "plan acceptance" "$SKILL_DIR/gate.md"
  [ "$status" -eq 0 ]
}

@test "task-exec: implement.md specifies TDD Red-Green-Refactor cycle" {
  run grep -qi "Red-Green-Refactor" "$SKILL_DIR/implement.md"
  [ "$status" -eq 0 ]
}

@test "task-exec: delivery.md specifies commit-tidy and PR delivery" {
  run grep -qi "commit-tidy" "$SKILL_DIR/delivery.md"
  [ "$status" -eq 0 ]
}

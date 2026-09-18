REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/task-plan"

@test "task-plan: skill directory and SKILL.md exist" {
  [ -d "$SKILL_DIR" ]
  [ -f "$SKILL_DIR/SKILL.md" ]
}

@test "task-plan: SKILL.md has valid name and metadata.version" {
  run grep -E "^name: task-plan" "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -E '^[[:space:]]*version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$SKILL_DIR/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "task-plan: all 7 topic documents exist" {
  [ -f "$SKILL_DIR/pre-search.md" ]
  [ -f "$SKILL_DIR/research.md" ]
  [ -f "$SKILL_DIR/plan.md" ]
  [ -f "$SKILL_DIR/plan-guard.md" ]
  [ -f "$SKILL_DIR/proposal.md" ]
  [ -f "$SKILL_DIR/artifact-rules.md" ]
  [ -f "$SKILL_DIR/review.md" ]
}

@test "task-plan: pre-search.md specifies RAG and canonical medium gate" {
  run grep -qi "canonical medium gate" "$SKILL_DIR/pre-search.md"
  [ "$status" -eq 0 ]
}

@test "task-plan: plan.md specifies 3-tier deliverable hierarchy" {
  run grep -qi "3-tier" "$SKILL_DIR/plan.md"
  [ "$status" -eq 0 ]
}

@test "task-plan: review.md specifies User Review Gate" {
  run grep -qi "User Review Gate" "$SKILL_DIR/review.md"
  [ "$status" -eq 0 ]
}

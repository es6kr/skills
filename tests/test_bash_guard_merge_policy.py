r"""Unit tests for merge policy guards in skills/hook-kit/resources/bash-guard.py.

Guards under test:
  1. check_pr_merge_squash_policy(command)
     - Blocks `gh pr merge --squash` on multi-commit PRs to prevent collapsing Conventional Commit history.
     - Requires `gh pr merge --merge` to maintain per-package semantic version bumps in release-please.
  2. check_feat_tag_file_addition_integrity(commit_msg, staged_files)
     - Blocks `feat:` commit tag if no new skill/topic/script file was added (prevents false minor bumps).
     - Enforces `feat:` commit tag if a new skill/topic/script file was added (prevents missed minor bumps).
  3. check_pr_create_routing_and_file_limit(command, changed_files, commit_count)
     - Enforces routing to `develop` staging branch; blocks direct PR to `main` if commit count < 5 and files < 10.
     - Blocks PR creation if changed files > 50 (CodeRabbit review limit).

Run:
  python -m pytest tests/test_bash_guard_merge_policy.py -v
"""
import importlib.util
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "skills", "hook-kit", "resources", "bash-guard.py")


def _load():
    spec = importlib.util.spec_from_file_location("bash_guard", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ==============================================================================
# 1. Squash-Merge Prevention Guard Tests
# ==============================================================================

def test_squash_merge_is_blocked_by_default():
    cmd = "gh pr merge 460 --squash"
    reason = mod.check_pr_merge_squash_policy(cmd)
    assert reason is not None
    assert "squash" in reason.lower()
    assert "--merge" in reason


def test_squash_merge_with_admin_is_blocked():
    cmd = "gh pr merge 460 --squash --admin"
    reason = mod.check_pr_merge_squash_policy(cmd)
    assert reason is not None
    assert "--merge" in reason


def test_merge_commit_is_allowed():
    cmd = "gh pr merge 460 --merge"
    assert mod.check_pr_merge_squash_policy(cmd) is None


def test_merge_commit_with_admin_is_allowed():
    cmd = "gh pr merge 460 --merge --admin"
    assert mod.check_pr_merge_squash_policy(cmd) is None


def test_rebase_merge_is_blocked_on_multi_commit():
    cmd = "gh pr merge 460 --rebase"
    reason = mod.check_pr_merge_squash_policy(cmd)
    assert reason is not None
    assert "--merge" in reason


def test_squash_merge_bypass_with_env():
    cmd = "ALLOW_SQUASH_MERGE=1 gh pr merge 460 --squash"
    assert mod.check_pr_merge_squash_policy(cmd) is None


def test_non_merge_commands_mentioning_squash_are_not_blocked():
    assert mod.check_pr_merge_squash_policy('echo "use --squash with caution"') is None
    assert mod.check_pr_merge_squash_policy('git rebase -i --autosquash HEAD~3') is None


# ==============================================================================
# 2. Feat Tag File-Addition Integrity Guard Tests
# ==============================================================================

def test_feat_tag_without_added_file_is_blocked():
    # Modifying existing files only with feat: tag
    commit_msg = "feat(cleanup): update context gate threshold"
    staged = [("M", "skills/cleanup/run.md")]
    reason = mod.check_feat_tag_file_addition_integrity(commit_msg, staged)
    assert reason is not None
    assert "feat" in reason.lower()
    assert "adding a new" in reason.lower()


def test_feat_tag_with_new_skill_md_is_allowed():
    commit_msg = "feat(autofix): add autofix skill documentation"
    staged = [("A", "skills/autofix/SKILL.md")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


def test_feat_tag_with_new_topic_is_allowed():
    commit_msg = "feat(backlog): add plane integration topic"
    staged = [("A", "skills/backlog/topics/plane.md")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


def test_feat_tag_with_new_script_is_allowed():
    commit_msg = "feat(fix-plan): add draft restore helper script"
    staged = [("A", "skills/fix-plan/scripts/add_draft.py")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


def test_fix_tag_when_adding_new_skill_file_is_blocked():
    # Adding a new skill/topic/script file under fix: tag must be blocked (requires feat:)
    commit_msg = "fix(backlog): add plane delete issue script"
    staged = [("A", "skills/backlog/scripts/plane_delete_issue.py")]
    reason = mod.check_feat_tag_file_addition_integrity(commit_msg, staged)
    assert reason is not None
    assert "feat:" in reason


def test_fix_tag_modifying_existing_files_is_allowed():
    commit_msg = "fix(cleanup): fix context usage check regex"
    staged = [("M", "skills/cleanup/run.md")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


def test_chore_tag_modifying_files_is_allowed():
    commit_msg = "chore(release): release main"
    staged = [("M", "package.json")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


def test_non_skill_new_file_with_chore_or_test_is_allowed():
    # Adding a new test file under test: or chore: tag is allowed without feat:
    commit_msg = "test(hook-kit): add unit tests for merge policy"
    staged = [("A", "tests/test_bash_guard_merge_policy.py")]
    assert mod.check_feat_tag_file_addition_integrity(commit_msg, staged) is None


# ==============================================================================
# 3. Direct Main PR Threshold & CodeRabbit 50-File Guard Tests
# ==============================================================================

def test_pr_create_targeting_develop_is_allowed():
    cmd = "gh pr create --base develop --draft --title 'feat: add merge guard'"
    assert mod.check_pr_create_routing_and_file_limit(cmd, changed_files=["a.py"], commit_count=1) is None


def test_direct_main_pr_with_few_commits_and_files_is_blocked():
    # Only 2 commits and 3 files directly targeting main -> should route to develop
    cmd = "gh pr create --base main --draft --title 'fix: small patch'"
    changed_files = ["a.py", "b.py", "c.py"]
    reason = mod.check_pr_create_routing_and_file_limit(cmd, changed_files=changed_files, commit_count=2)
    assert reason is not None
    assert "develop" in reason.lower()


def test_direct_main_pr_with_5_commits_is_allowed():
    cmd = "gh pr create --base main --draft --title 'chore: promote develop batch'"
    changed_files = ["a.py", "b.py", "c.py"]
    assert mod.check_pr_create_routing_and_file_limit(cmd, changed_files=changed_files, commit_count=5) is None


def test_direct_main_pr_with_10_files_is_allowed():
    cmd = "gh pr create --base main --draft --title 'chore: promote large batch'"
    changed_files = [f"file_{i}.py" for i in range(12)]
    assert mod.check_pr_create_routing_and_file_limit(cmd, changed_files=changed_files, commit_count=2) is None


def test_direct_main_pr_bypass_with_env():
    cmd = "ALLOW_DIRECT_MAIN_PR=1 gh pr create --base main --draft --title 'hotfix: critical fix'"
    changed_files = ["a.py"]
    assert mod.check_pr_create_routing_and_file_limit(cmd, changed_files=changed_files, commit_count=1) is None


def test_pr_create_exceeding_50_files_is_blocked():
    cmd = "gh pr create --base develop --draft --title 'feat: massive changeset'"
    changed_files = [f"file_{i}.py" for i in range(55)]
    reason = mod.check_pr_create_routing_and_file_limit(cmd, changed_files=changed_files, commit_count=10)
    assert reason is not None
    assert "50" in reason
    assert "coderabbit" in reason.lower()

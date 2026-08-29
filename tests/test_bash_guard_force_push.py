r"""Unit tests for check_git_force_push() in skills/hook-kit/resources/bash-guard.py.

Regression class under test (PR #374 CodeRabbit review, all Major):
  - FORCE_PUSH_SUB is matched with `.` (no DOTALL), so `.*` cannot cross a
    newline. A `git push \` + newline + `--force ...` continuation slipped
    past detection entirely, allowing an unconditional force push.
  - _extract_dash_c_path(command) searched the WHOLE (possibly compound)
    command for the FIRST `-C <path>`, not the one on the invocation that
    actually carries --force. `git -C <worktree> status && git -C <primary>
    push --force ...` verified <worktree> but pushed from <primary>.
  - branch_bare = branch.rsplit("/", 1)[-1] does not parse a push refspec's
    destination side. `push --force origin feature:main` resolved
    branch_bare to the literal "feature:main", which matches neither
    "main" nor "master", so a push whose destination IS main slipped
    through the "not main/master" check.

Fake, nonexistent paths (as bash-guard.py's own self_test() uses for the
`(True, False, "git -C /p ...")` cases) cannot distinguish "picked the right
path and correctly fell through to fail-closed" from "picked the wrong path
and correctly fell through to fail-closed" -- both dead ends look identical
when neither path resolves to a real git repo. These tests build real git
repos (a primary checkout + a worktree off it) so the worktree-exception
ALLOW path is actually exercised, not just its fail-closed fallback.

Run:
  python -m pytest tests/test_bash_guard_force_push.py -v

CI (.github/workflows/test.yml) collects via `python -m pytest tests -v`, so
this file must live under tests/. The script under test stays in
skills/hook-kit/resources/ and is loaded by path.
"""
import importlib.util
import os
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "skills", "hook-kit", "resources", "bash-guard.py")


def _load():
    spec = importlib.util.spec_from_file_location("bash_guard", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()

# Isolate every git call from the developer's/CI runner's own global config
# (gpgsign, hooksPath, etc. must not affect these throwaway repos) AND from
# any GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE/etc. this test process itself
# inherited -- these tests run fine standalone but fail when this suite is
# invoked FROM a git hook (e.g. this repo's own pre-push CI-parity check),
# because git hooks set exactly those vars for the enclosing repo, and an
# inherited GIT_DIR silently redirects `git init`/`git commit` in the temp
# fixture dirs below onto the OUTER repo instead of the throwaway one.
_GIT_ENV = {
    k: v for k, v in os.environ.items()
    if not k.startswith("GIT_") or k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                                          "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
}
_GIT_ENV.update({
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
})


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True, text=True)


@pytest.fixture
def repos(tmp_path):
    """A primary checkout on `main`, plus a worktree off it on `feature`."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git("init", "-q", cwd=primary)
    _git("checkout", "-q", "-B", "main", cwd=primary)
    (primary / "README.md").write_text("x")
    _git("add", "README.md", cwd=primary)
    _git("commit", "-q", "-m", "init", cwd=primary)

    worktree = tmp_path / "wt"
    _git("worktree", "add", "-q", "-b", "feature", str(worktree), cwd=primary)

    return {"primary": str(primary), "worktree": str(worktree)}


# --- legitimate exception still works (no regression) ---

def test_worktree_force_push_to_feature_branch_allowed(repos):
    cmd = f"git -C {repos['worktree']} push --force origin feature"
    assert mod.check_git_force_push(cmd) is None


# --- baseline: the two conditions still block on their own ---

def test_worktree_force_push_to_main_blocked(repos):
    cmd = f"git -C {repos['worktree']} push --force origin main"
    assert mod.check_git_force_push(cmd) is not None


def test_primary_checkout_force_push_blocked(repos):
    cmd = f"git -C {repos['primary']} push --force origin feature"
    assert mod.check_git_force_push(cmd) is not None


# --- CodeRabbit finding 1: escaped-newline continuation before --force ---

def test_escaped_newline_before_force_still_detected_and_blocked_on_main(repos):
    cmd = f"git -C {repos['worktree']} push \\\n  --force origin main"
    assert mod.check_git_force_push(cmd) is not None


def test_escaped_newline_before_force_blocked_from_primary(repos):
    cmd = f"git -C {repos['primary']} push \\\n  --force origin feature"
    assert mod.check_git_force_push(cmd) is not None


def test_escaped_newline_before_force_still_allowed_for_legitimate_case(repos):
    cmd = f"git -C {repos['worktree']} push \\\n  --force origin feature"
    assert mod.check_git_force_push(cmd) is None


# --- CodeRabbit finding 2: -C must resolve from the invocation that has --force ---

def test_decoy_dash_c_does_not_launder_a_primary_checkout_push(repos):
    # The FIRST -C in the command points at a real worktree; the actual
    # (force-flagged) push runs from the primary checkout via the SECOND -C.
    # Before the fix, _extract_dash_c_path picked the worktree path from the
    # first -C, so this force push was wrongly allowed.
    cmd = f"git -C {repos['worktree']} status && git -C {repos['primary']} push --force origin feature"
    assert mod.check_git_force_push(cmd) is not None


def test_decoy_dash_c_does_not_block_a_genuinely_scoped_worktree_push(repos):
    # Sanity check in the other direction: an unrelated earlier git
    # invocation must not cause a false BLOCK of a legitimate worktree push.
    cmd = f"git -C {repos['primary']} status && git -C {repos['worktree']} push --force origin feature"
    assert mod.check_git_force_push(cmd) is None


# --- CodeRabbit finding 3: refspec destination (src:dst) must be parsed ---

def test_refspec_destination_main_blocked(repos):
    # branch_bare used to be the literal "feature:main", matching neither
    # "main" nor "master" -- this refspec pushes a local `feature` branch to
    # the remote's `main`, and must be blocked regardless.
    cmd = f"git -C {repos['worktree']} push --force origin feature:main"
    assert mod.check_git_force_push(cmd) is not None


def test_refspec_destination_non_main_allowed(repos):
    cmd = f"git -C {repos['worktree']} push --force origin feature:other-feature"
    assert mod.check_git_force_push(cmd) is None


# --- false positives: quoted mentions of "git push --force" are not commands ---

def test_quoted_mention_in_printf_not_treated_as_invocation():
    assert mod.check_git_force_push('printf "%s" "git push --force is dangerous"') is None


def test_quoted_mention_in_commit_message_not_treated_as_invocation():
    assert mod.check_git_force_push('git commit -m "fix: git push --force guard"') is None

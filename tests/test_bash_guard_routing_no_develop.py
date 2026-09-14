"""Regression tests scoping the Direct-Main-PR threshold to plugin repositories.

The threshold tells a small PR to "target `develop` instead". That remedy only
exists in repositories that actually run the develop/main staging flow — the
plugin repositories this skill set maintains. Applied everywhere it denies the
only PR a repo can open: `daegunsoftDev/gitops` has `master` plus feature
branches and nothing else, every merged PR there targets `master`, and `master`
is the default branch. There the guard's required action is impossible and
`ALLOW_DIRECT_MAIN_PR=1` — an override meant for urgent hotfixes — becomes the
only way through routine work, which is how an override stops meaning anything.

So the threshold is scoped to plugin repositories, detected structurally by a
`.claude-plugin/marketplace.json` at the git toplevel (the same marker
dev-reflect uses to recognise a marketplace source) rather than a hardcoded
repo list that would drift. The 50-file CodeRabbit limit is unrelated to
staging flow and stays global.
"""

import importlib.util
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "skills", "hook-kit", "resources", "bash-guard.py")


def _load():
    spec = importlib.util.spec_from_file_location("bash_guard", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()

SMALL_PR_TO_MASTER = (
    'GH_TOKEN="$(gh auth token --user someone)" gh pr create '
    "-R owner/repo --base master --head feat/x --title t --body b --draft"
)
SMALL_PR_TO_MAIN = (
    'GH_TOKEN="$(gh auth token --user someone)" gh pr create '
    "-R owner/repo --base main --head feat/x --title t --body b --draft"
)


def _check(command, *, is_plugin_repo, files=None, commits=1):
    return mod.check_pr_create_routing_and_file_limit(
        command,
        changed_files=files if files is not None else ["apps/authentik.yaml"],
        commit_count=commits,
        is_plugin_repo=is_plugin_repo,
    )


# --- non-plugin repo: the staging-flow threshold must not fire --------------


def test_small_pr_to_master_allowed_in_non_plugin_repo():
    assert _check(SMALL_PR_TO_MASTER, is_plugin_repo=False) is None


def test_small_pr_to_main_allowed_in_non_plugin_repo():
    assert _check(SMALL_PR_TO_MAIN, is_plugin_repo=False) is None


def test_fifty_file_limit_still_applies_in_non_plugin_repo():
    """The CodeRabbit limit is about review capacity, not staging flow."""
    reason = _check(
        SMALL_PR_TO_MASTER,
        is_plugin_repo=False,
        files=[f"f{i}.yaml" for i in range(51)],
    )
    assert reason is not None
    assert "50-file" in reason


# --- plugin repo: unchanged behaviour --------------------------------------


def test_small_pr_to_master_still_blocked_in_plugin_repo():
    reason = _check(SMALL_PR_TO_MASTER, is_plugin_repo=True)
    assert reason is not None
    assert "develop" in reason


def test_large_pr_to_master_allowed_in_plugin_repo():
    assert (
        _check(
            SMALL_PR_TO_MASTER,
            is_plugin_repo=True,
            files=[f"f{i}.yaml" for i in range(12)],
            commits=6,
        )
        is None
    )


def test_override_still_works_in_plugin_repo():
    cmd = "ALLOW_DIRECT_MAIN_PR=1 " + SMALL_PR_TO_MASTER
    assert _check(cmd, is_plugin_repo=True) is None


def test_pr_to_develop_is_never_blocked():
    cmd = SMALL_PR_TO_MASTER.replace("--base master", "--base develop")
    assert _check(cmd, is_plugin_repo=True) is None


# --- structural detection ---------------------------------------------------


def test_plugin_repo_detected_by_marketplace_manifest(tmp_path):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text("{}")
    assert mod.is_plugin_repo_root(str(tmp_path)) is True


def test_plain_repo_is_not_a_plugin_repo(tmp_path):
    (tmp_path / "apps").mkdir()
    assert mod.is_plugin_repo_root(str(tmp_path)) is False

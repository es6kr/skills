"""TDD tests for the FA Fast Staging Inbox (ES6KR-189, Phase 1-2).

Spec sources (do not invent beyond these):
  - .agents/docs/generated/plan-fa-staging-inbox-integration.md
    Sec.2.1/Sec.2.2 (original code skeletons) + Sec.5 "Automated Verification"
    (zero-modal write, parser integrity, encoding hardening).
  - .agents/docs/generated/roadmap-followup-fa-prep-20261010.md Sec.3.1
    (Fable-audit-corrected fa-fast-record.py contract: explicit
    workspace-root walk via a `.git` ancestor, no silent global fallback,
    UTF-8 enforced, atomic-append verification) and Sec.3.2 (fa-inbox-triage.py
    parser skeleton, unchanged from the plan).

Red phase (commit a3706626): these 7 tests were written and run against
`skills/fa/scripts/fa-fast-record.py` / `fa-inbox-triage.py` before either
file existed -- all 7 failed with FileNotFoundError, the expected reason.

Green phase (this revision): both scripts now exist. Per parent-session
direction (2026-10-11), two further test classes were added here --
`TestFastRecordAtomicFailureDetection` (negative-path: inject a partial
`os.write()` and confirm the implementation detects it, rather than
asserting only that the files now exist) and `TestFastRecordConcurrencySafety`
(empirical concurrency audit of the atomic-append guarantee) -- see
fa-green-report.md for the audit that found and fixed a TOCTOU race in the
original prep-doc's stat-delta verification before these tests were written
against the corrected implementation.

Run: uvx --python 3.12 pytest tests/test_fa_fast_inbox_tdd.py -v
     (also discovered by the repo-wide `python -m pytest tests -v` CI job,
     which pins Python 3.12 -- see .github/workflows/test.yml)
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
FA_SCRIPTS_DIR = os.path.join(HERE, "..", "skills", "fa", "scripts")


def _load_module(module_name, filename):
    """Load a hyphenated-filename script module by explicit file path.

    `skills/fa/scripts/*.py` files use hyphens (fa-fast-record.py,
    fa-inbox-triage.py), which a plain `import` statement cannot resolve --
    the same constraint `skills/fa/scripts/test-fa-classify-meta.py` already
    works around in this skill via importlib. Raises FileNotFoundError when
    the target script does not exist yet (the expected Red-phase outcome).
    """
    path = os.path.join(FA_SCRIPTS_DIR, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build a module spec for {filename} at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_MIXED_INBOX = (
    "# Improvements Ledger\n"
    "\n"
    "## [Fast Record] 2026-10-11 09:00:00 (session aaaa1111, source: ralph)\n"
    "- **Observation**: Ralph loop flagged a repeated denied-command pattern.\n"
    "  Line two of the same observation, still part of the body.\n"
    "  Line three keeps going before the tag.\n"
    "- **Tag**: [NEEDS_REVIEW]\n"
    "\n"
    "## [Fast Record] 2026-10-11 09:05:00 (session bbbb2222, source: interactive)\n"
    "- **Observation**: human noted this mid-task without a modal.\n"
    "  Second line of the interactive note.\n"
    "- **Tag**: [NEEDS_REVIEW]\n"
    "\n"
    "## [Fast Record] 2026-10-11 09:10:00 (session cccc3333, source: interactive)\n"
    "- **Observation**: Already triaged and promoted, must not resurface.\n"
    "- **Tag**: [APPLIED]\n"
)

KOREAN_OBSERVATION = "한글 관찰 내용 — 유니코드 경간 테스트"


class FastRecordWorkspaceTestCase(unittest.TestCase):
    """Shared fixture: an isolated synthetic workspace (a fresh temp-dir with
    its own `.git` marker), never the real `.agents/improvements.md`."""

    def setUp(self):
        self._orig_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        (self.workspace / ".git").mkdir()
        (self.workspace / ".agents").mkdir()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()


class TestFastRecordZeroModalWrite(FastRecordWorkspaceTestCase):
    """plan Sec.5 item 1 + prep-doc Sec.3.1 corrected contract."""

    def test_zero_modal_write_exits_0_and_appends_needs_review_entry(self):
        fa_fast_record = _load_module("fa_fast_record_zm", "fa-fast-record.py")

        start = time.monotonic()
        rc = fa_fast_record.fast_record(
            "temp-dir synthetic observation", session_id="abcdef1234567890", source="interactive"
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        self.assertEqual(rc, 0)
        self.assertLess(
            elapsed_ms, 100, f"fast_record took {elapsed_ms:.2f}ms, expected <100ms (zero-modal)"
        )

        inbox_path = self.workspace / ".agents" / "improvements.md"
        self.assertTrue(inbox_path.exists())
        content = inbox_path.read_text(encoding="utf-8")
        self.assertIn("## [Fast Record]", content)
        self.assertIn("session abcdef12", content)  # session_id[:8]
        self.assertIn("source: interactive", content)
        self.assertIn("temp-dir synthetic observation", content)
        self.assertIn("[NEEDS_REVIEW]", content)

    def test_resolves_the_synthetic_workspace_not_any_real_ancestor(self):
        fa_fast_record = _load_module("fa_fast_record_root", "fa-fast-record.py")
        resolved = fa_fast_record.resolve_workspace_root(Path.cwd())
        self.assertEqual(resolved, self.workspace.resolve())


class TestFastRecordAtomicAppendSafety(FastRecordWorkspaceTestCase):
    """prep-doc Sec.3.1 'Atomic append verification' correction -- the
    externally observable half: a complete, untruncated entry per write,
    and append-mode ordering that never clobbers a prior entry.

    Not covered here: forcing the internal fsync/stat size-mismatch branch
    to return 1. Exercising that branch would require either modifying the
    not-yet-written implementation to inject a test seam, or reflection-based
    mocking the source docs do not specify -- left to the Green-phase
    implementer and flagged as a gap in fa-red-report.md rather than
    invented here.
    """

    def test_single_write_produces_a_complete_untruncated_entry(self):
        fa_fast_record = _load_module("fa_fast_record_atomic1", "fa-fast-record.py")
        note = "byte-exact growth check, must not be truncated mid-entry"

        rc = fa_fast_record.fast_record(note, session_id="11112222", source="interactive")
        self.assertEqual(rc, 0)

        inbox_path = self.workspace / ".agents" / "improvements.md"
        content = inbox_path.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.strip()]
        # A truncated/partial atomic-append failure would cut the entry off
        # before its closing Tag line; the Tag line must be the trailing
        # content of a single-entry file, with the Observation line before it.
        self.assertEqual(lines[-1].strip(), "- **Tag**: [NEEDS_REVIEW]")
        obs_idx = next(i for i, l in enumerate(lines) if note in l)
        self.assertLess(obs_idx, len(lines) - 1)

    def test_sequential_writes_append_without_clobbering_prior_entries(self):
        fa_fast_record = _load_module("fa_fast_record_atomic2", "fa-fast-record.py")
        rc1 = fa_fast_record.fast_record(
            "first entry must survive the second write", session_id="first0001", source="ralph"
        )
        rc2 = fa_fast_record.fast_record(
            "second entry appended after the first", session_id="second002", source="interactive"
        )
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)

        content = (self.workspace / ".agents" / "improvements.md").read_text(encoding="utf-8")
        self.assertIn("first entry must survive the second write", content)
        self.assertIn("second entry appended after the first", content)
        first_idx = content.index("first entry must survive the second write")
        second_idx = content.index("second entry appended after the first")
        self.assertLess(first_idx, second_idx, "append must preserve write order, not overwrite")


class TestFastRecordNoSilentGlobalFallback(unittest.TestCase):
    """prep-doc Sec.3.1 correction: the plan's `~/.agents/improvements.md`
    fallback must NOT be auto-created; fail loudly instead."""

    def setUp(self):
        self._orig_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        # Deliberately no `.git` anywhere under this tempdir.
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()

    def test_missing_workspace_root_fails_loudly_without_creating_global_fallback(self):
        fa_fast_record = _load_module("fa_fast_record_nofallback", "fa-fast-record.py")
        global_fallback = Path(os.path.expanduser("~/.agents/improvements.md"))
        existed_before = global_fallback.exists()
        size_before = global_fallback.stat().st_size if existed_before else None

        rc = fa_fast_record.fast_record("must never land in a silently-created global fallback")

        self.assertNotEqual(rc, 0)
        if existed_before:
            self.assertEqual(global_fallback.stat().st_size, size_before)
        else:
            self.assertFalse(
                global_fallback.exists(), "fast_record must not auto-create the global fallback"
            )


class TestFastRecordNestedRepoWorkspaceRoot(unittest.TestCase):
    """PR #625 review finding 1: the real workspace layout is
    `<ghq>/<host>/<org>/.agents/` with NO `.git` at the org level, while each
    repo under it has its own `.git` and no `.agents/`. Anchoring on the
    nearest `.git` therefore resolves to a repo that has no `.agents/` and
    every invocation from inside it fails. The root must be the nearest
    ancestor that actually owns `.agents/` -- but never one at or above the
    directory that contains `ghq` (that would be the user's global
    `~/.agents`, i.e. the forbidden silent global fallback)."""

    def setUp(self):
        self._orig_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name).resolve()
        self.org = self.home / "ghq" / "github.com" / "acme"
        self.repo = self.org / "skills"
        self.nested = self.repo / ".workspaces" / "skills" / "wt"
        self.nested.mkdir(parents=True)
        (self.repo / ".git").mkdir()  # repo-level .git, no .agents here
        (self.nested / ".git").write_text("gitdir: ../../../.git/worktrees/wt\n")

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()

    def test_resolves_org_level_agents_dir_when_repo_has_no_agents(self):
        (self.org / ".agents").mkdir()
        os.chdir(self.nested)
        fa_fast_record = _load_module("fa_fast_record_nested", "fa-fast-record.py")

        self.assertEqual(fa_fast_record.resolve_workspace_root(Path.cwd()), self.org)

        rc = fa_fast_record.fast_record("written from inside a nested repo worktree")
        self.assertEqual(rc, 0)
        self.assertIn(
            "written from inside a nested repo worktree",
            (self.org / ".agents" / "improvements.md").read_text(encoding="utf-8"),
        )

    def test_never_resolves_an_agents_dir_at_or_above_the_ghq_parent(self):
        (self.home / ".agents").mkdir()  # global-style dir, above `ghq`
        os.chdir(self.nested)
        fa_fast_record = _load_module("fa_fast_record_ceiling", "fa-fast-record.py")

        self.assertIsNone(fa_fast_record.resolve_workspace_root(Path.cwd()))
        self.assertNotEqual(fa_fast_record.fast_record("must not reach the global dir"), 0)
        self.assertFalse((self.home / ".agents" / "improvements.md").exists())


class TestInboxTriageParserIntegrity(unittest.TestCase):
    """plan Sec.2.2 skeleton (unchanged) + Sec.5 item 2 'Parser Integrity'."""

    def test_scan_inbox_parses_mixed_ralph_and_interactive_without_dropping_multiline(self):
        fa_inbox_triage = _load_module("fa_inbox_triage_mixed", "fa-inbox-triage.py")

        fd, fixture_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            with open(fixture_path, "w", encoding="utf-8") as f:
                f.write(SAMPLE_MIXED_INBOX)
            entries = fa_inbox_triage.scan_inbox(fixture_path)
        finally:
            os.unlink(fixture_path)

        self.assertEqual(
            len(entries),
            2,
            "the [APPLIED] entry must be excluded; both [NEEDS_REVIEW] entries must survive",
        )
        self.assertEqual(entries[0]["type"], "Fast Record")
        self.assertIn("source: ralph", entries[0]["title"])
        self.assertIn("Line two of the same observation", entries[0]["body"])
        self.assertIn("Line three keeps going before the tag", entries[0]["body"])

        self.assertIn("source: interactive", entries[1]["title"])
        self.assertIn("Second line of the interactive note", entries[1]["body"])


class TestFastRecordEncodingHardening(FastRecordWorkspaceTestCase):
    """plan Sec.5 item 3 -- UTF-8 Korean round-trip, no cp949 corruption."""

    def test_korean_observation_round_trips_without_corruption(self):
        fa_fast_record = _load_module("fa_fast_record_utf8", "fa-fast-record.py")

        rc = fa_fast_record.fast_record(KOREAN_OBSERVATION, session_id="deadbeef0000", source="interactive")
        self.assertEqual(rc, 0)

        inbox_path = self.workspace / ".agents" / "improvements.md"
        raw_bytes = inbox_path.read_bytes()
        self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "must not write a UTF-8 BOM")
        content = raw_bytes.decode("utf-8")
        self.assertIn(KOREAN_OBSERVATION, content)


class TestFastRecordAtomicFailureDetection(FastRecordWorkspaceTestCase):
    """Green-phase negative-path test (user-directed, 2026-10-11): the Red
    report flagged that the internal write-verification failure branch was
    untested because no implementation existed yet to inject a seam into.
    Now that the Green implementation verifies via `os.write()`'s own
    return value (see fa-fast-record.py module docstring for why), that
    seam is exactly `os.write` itself -- inject a short return and confirm
    the function reports failure instead of a false [OK]."""

    def test_partial_write_is_detected_and_reported_as_failure(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest.mock import patch

        fa_fast_record = _load_module("fa_fast_record_partial", "fa-fast-record.py")
        out, err = io.StringIO(), io.StringIO()
        with patch("os.write", return_value=3):  # pretend only 3 of N bytes landed
            with redirect_stdout(out), redirect_stderr(err):
                rc = fa_fast_record.fast_record("this entry must be reported as failed, not OK")

        self.assertEqual(rc, 1)
        self.assertIn("[FAIL]", err.getvalue())
        self.assertNotIn("[OK]", out.getvalue())


class TestFastRecordConcurrencySafety(FastRecordWorkspaceTestCase):
    """Green-phase audit test (user-directed, 2026-10-11): empirically verify
    that concurrent writers (e.g. a Ralph loop and an interactive `/fa fast`
    call appending around the same time) neither corrupt nor lose entries,
    and that the atomic-append check does not spuriously fail under
    concurrency. Spawns real OS subprocesses (not threads/multiprocessing)
    so the write actually crosses process boundaries, matching the real
    Ralph-vs-interactive scenario. See fa-green-report.md for the standalone
    audit (audit_original_atomic_check.py / audit_fixed_atomic_check.py)
    that reproduced 7/8 spurious failures against the original prep-doc
    algorithm and 0/8 against this fix, which this test re-confirms against
    the actual shipped module rather than a throwaway copy of it."""

    def test_concurrent_writers_all_succeed_without_corruption_or_loss(self):
        n = 8
        script_path = str(Path(FA_SCRIPTS_DIR) / "fa-fast-record.py")
        procs = []
        for i in range(n):
            code = (
                "import importlib.util, os, sys\n"
                f"spec = importlib.util.spec_from_file_location('w{i}', {script_path!r})\n"
                "m = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(m)\n"
                f"os.chdir({str(self.workspace)!r})\n"
                f"sys.exit(m.fast_record('concurrent worker note {i}', "
                f"session_id='cw{i:06d}', source='ralph'))\n"
            )
            procs.append(subprocess.Popen([sys.executable, "-c", code]))

        returncodes = [p.wait(timeout=10) for p in procs]
        self.assertEqual(returncodes, [0] * n, f"all {n} concurrent writers must succeed: {returncodes}")

        content = (self.workspace / ".agents" / "improvements.md").read_text(encoding="utf-8")
        for i in range(n):
            self.assertIn(f"concurrent worker note {i}", content, f"entry {i} missing or corrupted")
        self.assertEqual(
            content.count("[NEEDS_REVIEW]"), n,
            "entry count must equal writer count -- no loss, no duplication",
        )


if __name__ == "__main__":
    unittest.main()

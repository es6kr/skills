import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import scan_unmigrated_artifacts as scanner

class TestScanUnmigratedArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        
        # Setup simulated brain directories
        self.ide_brain = self.root / ".gemini" / "antigravity-ide" / "brain"
        self.cli_brain = self.root / ".gemini" / "antigravity-cli" / "brain"
        
        self.ide_brain.mkdir(parents=True)
        self.cli_brain.mkdir(parents=True)
        
        # Session in IDE
        s1 = self.ide_brain / "session-1"
        s1.mkdir()
        (s1 / "roadmap-agent-harness.md").write_text("# Roadmap: Agent Harness", encoding="utf-8")
        (s1 / "plan-knowledge-fa.md").write_text("# Plan: FA Overhaul", encoding="utf-8")
        
        # Session in CLI
        s2 = self.cli_brain / "session-2"
        s2.mkdir()
        (s2 / "walkthrough-agent-deliverables.md").write_text("# Walkthrough: Deliverables", encoding="utf-8")
        (s2 / "research-agent-deliverables.md").write_text("# Research: Deliverables", encoding="utf-8")
        
        # Target canonical dir
        self.canonical_dir = self.root / "workspace" / ".agents" / "docs" / "generated"
        self.canonical_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_multi_runtime_brain_roots_detected(self):
        roots = scanner.get_default_brain_roots(user_home=self.root)
        self.assertIn(self.ide_brain, roots)
        self.assertIn(self.cli_brain, roots)

    def test_scan_artifacts_across_both_runtimes(self):
        roots = [self.ide_brain, self.cli_brain]
        artifacts = scanner.scan_brain_artifacts_multi(brain_roots=roots, search_dirs=[self.canonical_dir])
        
        filenames = {a["filename"] for a in artifacts}
        self.assertIn("roadmap-agent-harness.md", filenames)
        self.assertIn("plan-knowledge-fa.md", filenames)
        self.assertIn("walkthrough-agent-deliverables.md", filenames)
        self.assertIn("research-agent-deliverables.md", filenames)
        self.assertEqual(len(artifacts), 4)

    def test_migration_action(self):
        roots = [self.ide_brain, self.cli_brain]
        artifacts = scanner.scan_brain_artifacts_multi(brain_roots=roots, search_dirs=[self.canonical_dir])
        
        migrated = scanner.migrate_artifacts(artifacts, target_dir=self.canonical_dir, dry_run=False)
        self.assertEqual(len(migrated), 4)
        
        # Verify files now exist in canonical dir
        self.assertTrue((self.canonical_dir / "roadmap-agent-harness.md").is_file())
        self.assertTrue((self.canonical_dir / "plan-knowledge-fa.md").is_file())
        self.assertTrue((self.canonical_dir / "walkthrough-agent-deliverables.md").is_file())
        self.assertTrue((self.canonical_dir / "research-agent-deliverables.md").is_file())

if __name__ == "__main__":
    unittest.main()

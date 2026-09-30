import os
import sys
import tempfile
import unittest

# Add fa scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'fa', 'scripts'))
from rotate_improvements import parse_improvements, rotate_file, is_resolved_tag

SAMPLE_IMPROVEMENTS = """# Improvements Ledger

<!-- archive-link: improvements.archive.md -->

## [2026-08-15] Topic A
### Item 1
- **Tag**: [APPLIED]
- Description: Completed improvement 1.

### Item 2
- **Tag**: [NEEDS_REVIEW]
- Description: Needs user attention.

## [2026-08-18] Topic B
### Item 3
- **Tag**: [IMPLEMENTED:PR#123]
- Description: Implemented via PR.

### Item 4
- **Tag**: [BLOCKED]
- Description: Waiting on dependency.
"""

# Carries content in both positions the rewrite must not destroy:
#   1. preamble  -- lines before the first `##`, beyond the generated header
#   2. section prose -- lines after a `##` but before that section's first `###`
SAMPLE_WITH_PROSE = """# Improvements Ledger

<!-- archive-link: improvements.archive.md -->

> Ledger policy: entries stay until adjudicated. Do not hand-edit tags.

## [2026-08-15] Topic A

Context for Topic A: raised during the September audit, owner unassigned.

### Item 1
- **Tag**: [APPLIED]
- Description: Completed improvement 1.

### Item 2
- **Tag**: [NEEDS_REVIEW]
- Description: Needs user attention.
"""

class TestRotateImprovements(unittest.TestCase):
    def test_is_resolved_tag(self):
        self.assertTrue(is_resolved_tag('[APPLIED]'))
        self.assertTrue(is_resolved_tag('[IMPLEMENTED]'))
        self.assertTrue(is_resolved_tag('[IMPLEMENTED:PR#123]'))
        self.assertTrue(is_resolved_tag('[NO-ACTION]'))
        self.assertTrue(is_resolved_tag('[DONE]'))
        self.assertFalse(is_resolved_tag('[NEEDS_REVIEW]'))
        self.assertFalse(is_resolved_tag('[BLOCKED]'))
        self.assertFalse(is_resolved_tag('[HOLD]'))
        self.assertFalse(is_resolved_tag(''))

    def test_parse_improvements(self):
        preamble, active, resolved = parse_improvements(SAMPLE_IMPROVEMENTS)
        self.assertEqual(len(resolved), 2)  # Item 1, Item 3
        self.assertEqual(len(active), 2)    # Item 2, Item 4
        # The parser collects the preamble; it must also hand it back so the
        # caller can put it in the rewritten file instead of discarding it.
        self.assertIn('archive-link', preamble)

    def test_parse_returns_section_prose(self):
        _preamble, active, _resolved = parse_improvements(SAMPLE_WITH_PROSE)
        # Prose sitting between `## Topic A` and its first `###` belongs to that
        # section, not to the document preamble, and must survive as such.
        topic_a = [e for e in active if 'Topic A' in e['h2']]
        self.assertTrue(topic_a, 'Topic A section should retain an active entry')
        self.assertIn('raised during the September audit', topic_a[0]['section_prose'])

    def test_rotate_preserves_preamble_and_section_prose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'improvements.md')
            archive_path = os.path.join(tmpdir, 'improvements.archive.md')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_WITH_PROSE)

            rotate_file(src_path, archive_path, dry_run=False)

            with open(src_path, 'r', encoding='utf-8') as f:
                src_content = f.read()

            # The rotation removed Item 1 (resolved); everything that was not an
            # entry must still be there.
            self.assertIn('Ledger policy: entries stay until adjudicated', src_content)
            self.assertIn('raised during the September audit', src_content)
            self.assertIn('[NEEDS_REVIEW]', src_content)
            self.assertNotIn('[APPLIED]', src_content)

    def test_rotate_file_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'improvements.md')
            archive_path = os.path.join(tmpdir, 'improvements.archive.md')
            
            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(SAMPLE_IMPROVEMENTS)
                
            stats = rotate_file(src_path, archive_path, dry_run=False)
            self.assertEqual(stats['resolved_count'], 2)
            self.assertEqual(stats['active_count'], 2)
            
            with open(src_path, 'r', encoding='utf-8') as f:
                src_content = f.read()
            self.assertIn('[NEEDS_REVIEW]', src_content)
            self.assertIn('[BLOCKED]', src_content)
            self.assertNotIn('[APPLIED]', src_content)
            self.assertNotIn('[IMPLEMENTED:PR#123]', src_content)
            
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_content = f.read()
            self.assertIn('[APPLIED]', archive_content)
            self.assertIn('[IMPLEMENTED:PR#123]', archive_content)

if __name__ == '__main__':
    unittest.main()

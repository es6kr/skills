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

# Unlike SAMPLE_IMPROVEMENTS -- whose preamble happens to be byte-identical to
# the header the formatter used to regenerate -- this fixture carries preamble
# prose and section-level prose that no reconstruction can invent. It is the
# regression guard for the rotation that silently deleted both.
RICH_IMPROVEMENTS = """# Improvements Ledger

Project-specific ledger notes that must survive rotation.
Do not delete this paragraph.

<!-- archive-link: improvements.archive.md -->

## [2026-09-01] Topic C

Section-level context for Topic C.
Every item under this heading is resolved, so the section itself is archived --
the prose must still survive in the active ledger.

### Item 5
- **Tag**: [APPLIED]
- Description: Resolved.

## [2026-09-02] Topic D

Context for Topic D.

### Item 6
- **Tag**: [BLOCKED]
- Description: Still open.
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
        _preamble, _sections, active, resolved = parse_improvements(SAMPLE_IMPROVEMENTS)
        self.assertEqual(len(resolved), 2)  # Item 1, Item 3
        self.assertEqual(len(active), 2)    # Item 2, Item 4

    def test_parse_preserves_non_item_content(self):
        preamble, sections, _active, _resolved = parse_improvements(RICH_IMPROVEMENTS)
        preamble_text = "".join(preamble)
        self.assertIn('Project-specific ledger notes', preamble_text)
        self.assertIn('Do not delete this paragraph.', preamble_text)
        section_prose = "".join(sections['## [2026-09-01] Topic C\n'])
        self.assertIn('Section-level context for Topic C.', section_prose)

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

    def test_rotate_preserves_non_item_content_round_trip(self):
        """The defect this guards: preamble + section prose were dropped from
        BOTH the source and the archive, with no backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'improvements.md')
            archive_path = os.path.join(tmpdir, 'improvements.archive.md')
            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(RICH_IMPROVEMENTS)

            rotate_file(src_path, archive_path, dry_run=False)

            with open(src_path, 'r', encoding='utf-8') as f:
                src_content = f.read()

            # File preamble survives.
            self.assertIn('Project-specific ledger notes', src_content)
            self.assertIn('Do not delete this paragraph.', src_content)
            # Section prose survives even though every item in that section was
            # archived -- the section would otherwise vanish with its items.
            self.assertIn('Section-level context for Topic C.', src_content)
            self.assertIn('Context for Topic D.', src_content)
            # The active item stays, the resolved one leaves.
            self.assertIn('[BLOCKED]', src_content)
            self.assertNotIn('[APPLIED]', src_content)
            # The archive banner is not duplicated when the preamble has one.
            self.assertEqual(src_content.count('<!-- archive-link:'), 1)

    def test_rotate_is_idempotent(self):
        """A second rotation with nothing resolved must not mutate the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'improvements.md')
            archive_path = os.path.join(tmpdir, 'improvements.archive.md')
            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(RICH_IMPROVEMENTS)

            rotate_file(src_path, archive_path, dry_run=False)
            with open(src_path, 'r', encoding='utf-8') as f:
                after_first = f.read()

            rotate_file(src_path, archive_path, dry_run=False)
            with open(src_path, 'r', encoding='utf-8') as f:
                after_second = f.read()

            self.assertEqual(after_first, after_second)


if __name__ == '__main__':
    unittest.main()

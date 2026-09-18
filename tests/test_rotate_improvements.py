import os
import sys
import tempfile
import unittest

# Add cleanup and fa scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'fa', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'cleanup', 'scripts'))
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
        active, resolved = parse_improvements(SAMPLE_IMPROVEMENTS)
        self.assertEqual(len(resolved), 2)  # Item 1, Item 3
        self.assertEqual(len(active), 2)    # Item 2, Item 4

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

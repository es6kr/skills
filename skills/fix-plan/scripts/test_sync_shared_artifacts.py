#!/usr/bin/env python3
"""
test_sync_shared_artifacts.py - Unit tests for sync_shared_artifacts.py
"""

import os
import sys
import tempfile
import unittest
import filecmp

from sync_shared_artifacts import (
    parse_frontmatter,
    upsert_frontmatter_fields,
    process_artifact,
)


class TestSyncSharedArtifacts(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_dir = os.path.join(self.temp_dir.name, "generated")
        self.dest_dir = os.path.join(self.temp_dir.name, "shared")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.dest_dir, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_frontmatter_with_fm(self):
        content = "---\ntitle: Sample Doc\ncreated: 2026-09-16\n---\n# Sample Heading\nBody text"
        fm, body = parse_frontmatter(content)
        self.assertIsNotNone(fm)
        self.assertEqual(fm, "title: Sample Doc\ncreated: 2026-09-16")
        self.assertEqual(body, "# Sample Heading\nBody text")

    def test_parse_frontmatter_without_fm(self):
        content = "# No Frontmatter\nJust body"
        fm, body = parse_frontmatter(content)
        self.assertIsNone(fm)
        self.assertEqual(body, content)

    def test_upsert_frontmatter_existing(self):
        fm = "title: Doc\ncollabmd_url: https://old.url\nstatus: draft"
        new_fm = upsert_frontmatter_fields(
            fm,
            collabmd_url="https://new.url",
            output_dir=".agents/docs/shared"
        )
        self.assertIn("title: Doc", new_fm)
        self.assertIn("collabmd_url: https://new.url", new_fm)
        self.assertNotIn("https://old.url", new_fm)
        self.assertIn("output_dir: .agents/docs/shared", new_fm)
        self.assertIn("status: draft", new_fm)

    def test_upsert_frontmatter_none(self):
        new_fm = upsert_frontmatter_fields(
            None,
            collabmd_url="https://new.url",
            output_dir=".agents/docs/shared"
        )
        expected = "---\ncollabmd_url: https://new.url\noutput_dir: .agents/docs/shared\n---\n"
        self.assertEqual(new_fm, expected)

    def test_process_artifact_end_to_end(self):
        sample_file = os.path.join(self.src_dir, "plan-sample.md")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("---\ntitle: Sample Plan\n---\n# Plan Content\nDetailed steps")

        res = process_artifact(sample_file, self.dest_dir)
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["fm_updated"], "Yes")
        self.assertEqual(res["copied"], "Yes")
        self.assertEqual(res["verified"], "PASS")

        dest_file = os.path.join(self.dest_dir, "plan-sample.md")
        self.assertTrue(os.path.exists(dest_file))
        self.assertTrue(filecmp.cmp(sample_file, dest_file, shallow=False))

        # 멱등성 검증 (2회차 실행)
        res2 = process_artifact(sample_file, self.dest_dir)
        self.assertEqual(res2["status"], "OK")
        self.assertEqual(res2["fm_updated"], "Already Up-to-date")
        self.assertEqual(res2["verified"], "PASS")

    def test_process_artifact_dry_run(self):
        sample_file = os.path.join(self.src_dir, "plan-dry.md")
        initial_content = "---\ntitle: Dry Run Plan\n---\n# Content"
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        res = process_artifact(sample_file, self.dest_dir, dry_run=True)
        self.assertEqual(res["copied"], "DRY-RUN")

        # 파일이 변경되지 않고 복사본도 생기지 않아야 함
        dest_file = os.path.join(self.dest_dir, "plan-dry.md")
        self.assertFalse(os.path.exists(dest_file))
        with open(sample_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), initial_content)


if __name__ == "__main__":
    unittest.main()

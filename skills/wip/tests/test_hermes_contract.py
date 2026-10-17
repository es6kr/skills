"""Offline regression checks for the WIP Hermes documentation contract."""
import json
from pathlib import Path
import re
import unittest

WIP = Path(__file__).resolve().parents[1]


class HermesContract(unittest.TestCase):
    def text(self, name):
        return (WIP / name).read_text(encoding="utf-8")

    def test_entry_routes_hermes_before_claude(self):
        text = self.text("SKILL.md")
        self.assertIn("[hermes.md](./hermes.md)", text)
        self.assertIn("todo_list", text)
        self.assertLess(text.index("Hermes runtime:"), text.index("## Topics"))

    def test_resume_detects_hermes_first(self):
        text = self.text("resume.md")
        detection = text.split("Environment detection:", 1)[1].split("## Precondition", 1)[0]
        self.assertLess(detection.index("Hermes"), detection.index("TaskList"))
        self.assertIn("[hermes.md](./hermes.md)", text)

    def test_native_mapping_and_valid_payloads(self):
        text = self.text("hermes.md")
        for term in ("todo_list", "merge", "parent", "clarify", "pending", "cancelled"):
            self.assertIn(term, text)
        payloads = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", text, re.S)]
        self.assertGreaterEqual(len(payloads), 2)
        self.assertIn({}, payloads)
        update = next(p for p in payloads if p.get("merge") is True)
        for task in update["todos"]:
            self.assertEqual(set(task) - {"id", "content", "status", "parent"}, set())
            self.assertIn(task["status"], {"pending", "in_progress", "completed", "cancelled"})

    def test_fallback_is_gated_and_session_scoped(self):
        text = self.text("hermes.md")
        for term in ("tool_search", "tool_describe", "tool_call", "actual unavailability", "current session ID", "no default/shared ledger", "Policy denial"):
            self.assertIn(term, text)
        self.assertLess(text.index("## Native operations"), text.index("## Fallback"))

    def test_replacement_preserves_unrelated_tasks(self):
        text = self.text("hermes.md")
        for term in ("merge:false", "full list", "unrelated", "read back", "not a valid status", "compaction alone"):
            self.assertIn(term, text)

    def test_resume_maps_all_operations(self):
        text = self.text("resume.md")
        for heading in ("### Per-environment commands", "### Per-environment ask method", "### Per-environment execution"):
            section = text.split(heading, 1)[1].split("\n##", 1)[0]
            self.assertIn("Hermes", section)
        self.assertIn("Hermes override", text)


if __name__ == "__main__":
    unittest.main()

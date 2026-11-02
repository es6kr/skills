#!/usr/bin/env python3
"""
Unit tests for Antigravity Session Cleanup Runner (agy-cleanup.py)
Verifies:
1. RAG endpoint resolution (ws-config, env, default fallback)
2. SSL context creation for private IP
3. Multi-repository git status inspection
4. Walkthrough & plan artifact detection
5. Meaningful session rename suggestions (length <= 38 chars)
6. Graph-driven procedure loading via cleanup_query.py (SSOT)
7. Fail-closed behavior on unverified or missing procedure graph
"""

import os
import sys
import unittest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("agy_cleanup", SCRIPTS_DIR / "agy-cleanup.py")
agy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agy)


class TestAgyCleanup(unittest.TestCase):

    def test_resolve_rag_endpoint_prefers_env(self):
        with patch.dict(os.environ, {"WSCFG_RAG_ENDPOINT": "https://custom.rag:30333"}):
            self.assertEqual(agy.resolve_rag_endpoint(), "https://custom.rag:30333")

    def test_resolve_rag_endpoint_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                endpoint = agy.resolve_rag_endpoint()
                self.assertTrue(endpoint.startswith("https://"))
                self.assertIn(":30333", endpoint)

    def test_ssl_context_for_private_ip(self):
        ctx = agy.ssl_context_for_url("https://192.168.6.176:30333/healthz")
        self.assertFalse(ctx.check_hostname)
        import ssl
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)

    def test_ssl_context_for_public_host(self):
        ctx = agy.ssl_context_for_url("https://example.com/healthz")
        self.assertTrue(ctx.check_hostname)

    def test_multi_repo_git_status(self):
        def fake_run_cmd(cmd, cwd=None, timeout=30):
            if cwd and "claude-plugins" in str(cwd):
                return 0, " M test.py", ""
            return 0, "", ""

        with patch.object(agy, "run_cmd", side_effect=fake_run_cmd):
            results = agy.check_git_status(verbose=False)
            self.assertIsInstance(results, dict)

    def test_detect_session_walkthroughs(self):
        sess_id = "6f3c26ab-1a46-4878-a820-00d6afafb0fe"
        found = agy.detect_session_artifacts(sess_id)
        self.assertIsInstance(found, list)

    def test_rename_suggestions_length_and_format(self):
        suggestions = agy.generate_rename_suggestions("6f3c26ab-1a46-4878-a820-00d6afafb0fe", "dgraph-qdrant-mem0")
        self.assertTrue(len(suggestions) >= 2)
        for cmd in suggestions:
            self.assertTrue(cmd.startswith("/rename "))
            self.assertLessEqual(len(cmd), 38)

    def test_load_procedure_graph_success(self):
        fake_graph = {
            "topic": "run",
            "stages": [
                {"properties": {"order": 0}, "label": "Stage 0"},
                {"properties": {"order": 1}, "label": "Stage 1"}
            ],
            "guards": [{"text": "Guard 1"}],
            "validation": {"verified": True, "node_count": 207, "edge_count": 494}
        }
        with patch.object(agy, "run_cmd", return_value=(0, json.dumps(fake_graph), "")), \
             patch("pathlib.Path.exists", return_value=True):
            graph = agy.load_procedure_graph()
            self.assertTrue(graph["validation"]["verified"])
            self.assertEqual(len(graph["stages"]), 2)

    def test_load_procedure_graph_fail_closed_on_error(self):
        with patch.object(agy, "run_cmd", return_value=(1, "", "Dgraph unreachable")):
            with self.assertRaises(RuntimeError):
                agy.load_procedure_graph()

    def test_load_procedure_graph_fail_closed_on_unverified(self):
        fake_unverified = {
            "topic": "run",
            "validation": {"verified": False}
        }
        with patch.object(agy, "run_cmd", return_value=(0, json.dumps(fake_unverified), "")):
            with self.assertRaises(RuntimeError):
                agy.load_procedure_graph()

    def test_query_cleanup_topology_references(self):
        """Verify querying Dgraph es6kr:topology for skill:cleanup dependencies and callers."""
        mock_fn = MagicMock(return_value={
            "skill_id": "skill:cleanup",
            "dependencies": [{"target": "skill:fa", "relation": "CALLS_SKILL"}],
            "callers": [{"source": "skill:next", "relation": "DEPENDS_ON"}],
        })
        res = agy.query_cleanup_topology_references(topology_query_fn=mock_fn)
        self.assertEqual(res["skill_id"], "skill:cleanup")
        self.assertEqual(len(res["dependencies"]), 1)
        self.assertEqual(res["dependencies"][0]["target"], "skill:fa")


if __name__ == "__main__":
    unittest.main()

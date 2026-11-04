#!/usr/bin/env python3
"""Synthetic-only regressions for Plane token-cache parsing and diagnostics."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("workspace_profile.py")
SPEC = importlib.util.spec_from_file_location("fixture_workspace_profile", SOURCE)
profile_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile_module)
DIAGNOSTIC_SENTINEL = "SYNTHETIC_DIAGNOSTIC_MUST_NOT_APPEAR"


class TestPlaneTokenCache(unittest.TestCase):
    def load_cache(self, content, env=None, read_error=None):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "fixture-token.txt"
            cache.write_bytes(content)
            original = cache.read_bytes()
            config = {"profiles": {"fixture": {
                "workspace_name": "fixture",
                "plane_host": "https://plane.example.invalid",
                "plane_token_env": "FIXTURE_PLANE_TOKEN",
                "token_file": str(cache),
            }}}
            output = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(profile_module, "load_user_config", return_value=config))
                stack.enter_context(patch.dict(os.environ, env or {}, clear=True))
                stack.enter_context(contextlib.redirect_stdout(output))
                stack.enter_context(contextlib.redirect_stderr(output))
                if read_error is not None:
                    stack.enter_context(patch.object(Path, "read_text", side_effect=read_error))
                try:
                    result = profile_module.get_profile("fixture", directory)
                except Exception as error:
                    self.fail("cache input escaped the resolver as " + type(error).__name__)
            self.assertEqual(cache.read_bytes(), original, "credential-cache bytes must not be rewritten")
            return result, output.getvalue()

    def test_comment_prefixed_cache_selects_one_bare_value(self):
        result, output = self.load_cache(b"# synthetic cache provenance\r\n\r\n  fixture-key-123  \r\n# trailing note\r\n")
        self.assertTrue(result["plane_token"] == "fixture-key-123", "comments must not become header contents")
        self.assertEqual(output, "")

    def test_plain_single_value_remains_compatible(self):
        result, _ = self.load_cache(b"fixture-key-123\n")
        self.assertEqual(result["plane_token"], "fixture-key-123")

    def test_named_environment_value_still_outranks_cache(self):
        result, _ = self.load_cache(b"# note\ncache-key\n", {"FIXTURE_PLANE_TOKEN": "env-fixture-key"})
        self.assertEqual(result["plane_token"], "env-fixture-key")

    def test_comments_only_cache_is_not_an_authentication_value(self):
        result, _ = self.load_cache(b"# synthetic note only\n\n")
        self.assertFalse(bool(result["plane_token"]), "comment-only input must fail closed")

    def test_multiple_bare_values_are_rejected_not_joined_or_guessed(self):
        result, _ = self.load_cache(b"# synthetic cache\nfirst-fixture-key\nsecond-fixture-key\n")
        self.assertFalse(bool(result["plane_token"]), "ambiguous cache values must not be selected")

    def test_internal_whitespace_in_bare_value_is_rejected(self):
        result, _ = self.load_cache(b"fixture key with spaces\n")
        self.assertFalse(bool(result["plane_token"]), "invalid value must not be silently repaired")

    def test_invalid_utf8_cache_fails_closed_without_traceback(self):
        result, _ = self.load_cache(b"# synthetic cache\n\xfffixture\n")
        self.assertFalse(bool(result["plane_token"]))

    def test_cache_read_error_does_not_echo_exception_contents(self):
        result, output = self.load_cache(b"fixture-key\n", read_error=OSError(DIAGNOSTIC_SENTINEL))
        self.assertFalse(bool(result["plane_token"]))
        self.assertFalse(DIAGNOSTIC_SENTINEL in output, "diagnostics must not print exception input")


if __name__ == "__main__":
    unittest.main()

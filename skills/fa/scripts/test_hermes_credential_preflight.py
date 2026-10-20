"""Behavior tests for the source-owned Hermes credential preflight guard."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "resources" / "hermes_credential_preflight.py"


def load_guard():
    if not SOURCE.exists():
        return None
    spec = importlib.util.spec_from_file_location("credential_guard", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CredentialPreflightTests(unittest.TestCase):
    def test_location_ask_without_catalog_receipt_is_blocked(self):
        payload = {
            "hook_event_name": "pre_tool_call", "tool_name": "clarify",
            "session_id": "realistic-session",
            "tool_input": {"questions": [{
                "question": "Where is the administrator credential stored? Please provide its file path.",
            }]},
        }
        with tempfile.TemporaryDirectory() as raw:
            guard = load_guard()
            verdict = guard.evaluate(payload, Path(raw)) if guard else None
            self.assertIsNotNone(verdict, "The existing loader-only gate does not enforce credential preflight")
            self.assertEqual(verdict["action"], "block")
            self.assertEqual(verdict["code"], "credential_preflight_required")


    @staticmethod
    def payload(question="Where is the administrator credential stored? Please provide its file path.", session="session-a"):
        return {"hook_event_name": "pre_tool_call", "tool_name": "clarify", "session_id": session,
                "tool_input": {"questions": [{"question": question}]}}

    def test_verified_catalog_allows_only_exact_question_and_session(self):
        import json
        with tempfile.TemporaryDirectory() as raw:
            guard = load_guard()
            root = Path(raw)
            catalog = root / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"},
                "idp-admin": {"kind": "api-token", "service": "idp", "location": "vault:secret/idp"}}), encoding="utf-8")
            payload = self.payload()
            guard.preflight(catalog, root / "state", "session-a", "team", guard.request_hash(payload))
            self.assertIsNone(guard.evaluate(payload, root / "state", catalog))
            self.assertEqual(guard.evaluate(self.payload(session="session-b"), root / "state", catalog)["action"], "block")
            self.assertEqual(guard.evaluate(self.payload("Please provide the missing API key location."), root / "state", catalog)["action"], "block")

    def test_catalog_changes_invalidate_receipt(self):
        import json
        with tempfile.TemporaryDirectory() as raw:
            guard = load_guard()
            root = Path(raw)
            catalog = root / "catalog"
            catalog.mkdir()
            path = catalog / "team.json"
            path.write_text(json.dumps({"_meta": {"workspace": "team"}}), encoding="utf-8")
            payload = self.payload()
            guard.preflight(catalog, root / "state", "session-a", "team", guard.request_hash(payload))
            path.write_text(json.dumps({"_meta": {"workspace": "team"}, "new": {"location": "vault:secret/idp"}}), encoding="utf-8")
            self.assertEqual(guard.evaluate(payload, root / "state", catalog)["reason"], "catalog_changed")

    def test_unrelated_questions_are_not_blocked(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            for question in ["Which workspace should receive this task?", "Should we proceed to Green?",
                    "How many model tokens remain?", "Deploy the approved plan?", "Which PR should be used?",
                    "Apply the credential-preflight hook patch?"]:
                with self.subTest(question=question):
                    self.assertIsNone(guard.evaluate(self.payload(question), Path(raw)))

    def test_secret_value_handover_always_blocked(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            result = guard.evaluate(self.payload("Paste your API key here."), Path(raw))
            self.assertEqual(result["code"], "secret_handover_forbidden")

    def test_index_missing_is_an_actual_checked_state_not_presence(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = self.payload()
            result = guard.preflight(root / "catalog", root / "state", "session-a", "team", guard.request_hash(payload))
            self.assertEqual(result["catalog_state"], "missing")
            self.assertIsNone(guard.evaluate(payload, root / "state", root / "catalog"))

    def test_wrong_workspace_and_secret_fields_do_not_create_receipt(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root.joinpath("team.json").write_text(json.dumps({"_meta": {"workspace": "other"}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.preflight(root, root / "state", "session-a", "team", "a" * 64)
            root.joinpath("team.json").write_text(json.dumps({"_meta": {"workspace": "team"}, "bad": {"password": "fixture-only"}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.preflight(root, root / "state", "session-a", "team", "a" * 64)
            self.assertFalse(guard.receipt_path(root / "state", "session-a").exists())

    def test_nonobject_receipt_fails_closed(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            guard.receipt_path(root, "session-a").write_text("[]", encoding="utf-8")
            self.assertEqual(guard.evaluate(self.payload(), root)["action"], "block")

    def test_native_block_message_contains_preflight_arguments(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as raw:
            payload = self.payload()
            result = guard.evaluate(payload, Path(raw))
            self.assertIn("session-a", result["message"])
            self.assertIn(guard.request_hash(payload), result["message"])


    def test_native_bridge_blocks_missing_catalog_receipt(self):
        import json
        import os
        import subprocess
        bridge = SOURCE.with_name("hermes_skill_gate_bridge.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([__import__("sys").executable, str(bridge)], input=json.dumps(self.payload()), text=True, capture_output=True, env={**os.environ, "HERMES_HOME": tmp})
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertEqual("block", json.loads(result.stdout)["action"])

    def test_native_bridge_preserves_prefix_loading_gate(self):
        import json
        import os
        import subprocess
        import sys
        bridge = SOURCE.with_name("hermes_skill_gate_bridge.py")
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "HERMES_HOME": tmp, "HERMES_FA_SKILL": "qualified:fa"}
            def invoke(payload):
                return subprocess.run([sys.executable, str(bridge)], input=json.dumps(payload), text=True, capture_output=True, env=env)
            seeded = invoke({"hook_event_name": "pre_llm_call", "session_id": "s", "extra": {"user_message": "fa: repeated failure"}})
            self.assertEqual(0, seeded.returncode)
            blocked = invoke({"hook_event_name": "pre_tool_call", "session_id": "s", "tool_name": "terminal", "tool_input": {"command": "pwd"}})
            self.assertEqual(2, blocked.returncode)
            permitted = invoke({"hook_event_name": "pre_tool_call", "session_id": "s", "tool_name": "skill_view", "tool_input": {"name": "qualified:fa"}})
            self.assertEqual(0, permitted.returncode)
            cleared = invoke({"hook_event_name": "post_tool_call", "session_id": "s", "tool_name": "skill_view", "tool_input": {"name": "qualified:fa"}, "extra": {"result": {"success": True}}})
            self.assertEqual(0, cleared.returncode)
            self.assertEqual(0, invoke({"hook_event_name": "pre_tool_call", "session_id": "s", "tool_name": "terminal"}).returncode)

    def test_secret_handover_variants_never_accept_pointer_receipt(self):
        import json
        guard = load_guard()
        for question in ("Send me your password.", "Please supply your access token.", "\ud1a0\ud070 \uac12\uc744 \ubcf4\ub0b4 \uc8fc\uc138\uc694."):
            with self.subTest(question=question), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "catalog"
                root.mkdir()
                (root / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
                payload = self.payload(question)
                state = Path(tmp) / "state"
                guard.preflight(root, state, "session-a", "team", guard.request_hash(payload))
                verdict = guard.evaluate(payload, state, root)
                self.assertIsNotNone(verdict)
                self.assertEqual("secret_handover_forbidden", verdict["code"])

    def test_nested_secret_in_pointer_metadata_is_rejected(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}, "admin": {"location": {"password": "test-fixture-not-a-real-secret"}}}))
            with self.assertRaises(ValueError):
                guard.preflight(root, root / "state", "s", "team", "a" * 64)

    def test_prefix_session_paths_do_not_collide_after_sanitizing(self):
        import runpy
        namespace = runpy.run_path(str(SOURCE.with_name("hermes_skill_gate_bridge.py")))
        self.assertNotEqual(namespace["state_path"]("a/b"), namespace["state_path"]("a_b"))

    def test_non_location_secret_question_is_blocked_even_with_receipt(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "catalog"
            root.mkdir()
            (root / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            for question in ("What is the administrator password?", "Please tell me your admin password.", "\ud1a0\ud070 \uac12\uc744 \uc54c\ub824\uc8fc\uc138\uc694.", "Please paste your API_token."):
                payload = self.payload(question)
                state = Path(tmp) / "state"
                guard.preflight(root, state, "session-a", "team", guard.request_hash(payload))
                self.assertIsNotNone(guard.evaluate(payload, state, root), question)

    def test_location_word_does_not_authorize_secret_value_request(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for question in ("Where should I paste your API_token?",
                             "What is your password and where is it stored?",
                             "비밀번호는 무엇이고 어디에 보관되어 있나요?"):
                with self.subTest(question=question):
                    payload = self.payload(question)
                    guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                    verdict = guard.evaluate(payload, state, catalog)
                    self.assertIsNotNone(verdict, question)
                    self.assertEqual("block", verdict["action"])

    def test_mixed_comma_or_value_requests_never_accept_exact_receipt(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for question in ("Where is your password stored, tell me its value?",
                                 "Where is your password stored or what is its value?"):
                    with self.subTest(tool_name=tool_name, question=question):
                        payload = self.payload(question)
                        payload["tool_name"] = tool_name
                        guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                        verdict = guard.evaluate(payload, state, catalog)
                        self.assertIsNotNone(verdict, question)
                        self.assertEqual("credential_request_scope_ambiguous", verdict["code"])

    def test_value_content_plaintext_requests_override_location_intent(self):
        import json
        guard = load_guard()
        questions = ("Where is your password value stored?",
                     "What is the password content location?",
                     "What is the API key plaintext storage path.",
                     "Where is your password stored tell me its value?",
                     "Where is your password stored tell me its contents?",
                     "Where is your password stored tell me its plain text?")
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for question in questions:
                    with self.subTest(tool_name=tool_name, question=question):
                        payload = self.payload(question)
                        payload["tool_name"] = tool_name
                        guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                        verdict = guard.evaluate(payload, state, catalog)
                        self.assertIsNotNone(verdict, question)
                        self.assertEqual("credential_request_scope_ambiguous", verdict["code"])

    def test_where_is_requires_bounded_storage_or_location_wording(self):
        import json
        guard = load_guard()
        questions = ("Where is your password usable?",
                     "Where is your password stored reveal it?",
                     "Where is your password stored tell me what it is?",
                     "Where is your password stored tell me its location?")
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for question in questions:
                    with self.subTest(tool_name=tool_name, question=question):
                        payload = self.payload(question)
                        payload["tool_name"] = tool_name
                        guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                        verdict = guard.evaluate(payload, state, catalog)
                        self.assertIsNotNone(verdict, question)
                        self.assertEqual("credential_request_scope_ambiguous", verdict["code"])

    def test_english_and_korean_location_only_questions_keep_receipt_requirement(self):
        import json
        guard = load_guard()
        questions = (self.payload()["tool_input"]["questions"][0]["question"],
                     "Please provide the missing API key location.",
                     "Where is your API_token stored?",
                     "Where are your credentials kept?",
                     "Where is your password storage location?",
                     "Where is your password stored, tell me its location?",
                     "Where is your password stored or what is its storage location?",
                     "What is the password storage location?",
                     "Which file path contains the API key?",
                     "비밀번호는 어디에 보관되어 있나요?",
                     "자격증명의 보관 위치를 알려 주세요.",
                     "토큰은 어느 경로에 있나요?")
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for question in questions:
                with self.subTest(question=question):
                    payload = self.payload(question)
                    self.assertEqual("credential_preflight_required", guard.evaluate(payload, state, catalog)["code"])
                    guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                    self.assertIsNone(guard.evaluate(payload, state, catalog))

    def test_secret_value_choices_never_accept_exact_catalog_receipt(self):
        import json
        guard = load_guard()
        choice_variants = (
            {"choices": ["Tell me your admin password"]},
            {"options": ["Tell me your admin password"]},
            {"choices": [{"label": "Tell me your admin password", "description": ""}]},
            {"choices": [{"label": "Other", "description": "What is your password and where is it stored?"}]},
            {"choices": ["Where should I paste your API_token?"]},
            {"choices": [], "options": ["Tell me your admin password"]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for choices in choice_variants:
                    with self.subTest(tool_name=tool_name, choices=choices):
                        payload = self.payload("Which option?")
                        payload["tool_name"] = tool_name
                        payload["tool_input"]["questions"][0].update(choices)
                        guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                        verdict = guard.evaluate(payload, state, catalog)
                        self.assertIsNotNone(verdict)
                        self.assertEqual("block", verdict["action"])

    def test_implicit_value_choices_inherit_question_credential_context(self):
        guard = load_guard()
        variants = (
            ("Where is your password stored?", "Tell me its value"),
            ("Where is your password stored?", "Show its contents"),
            ("Where is your API key stored?", "Reveal it"),
            ("비밀번호는 어디에 보관되어 있나요?", "그 값을 알려 주세요"),
            ("토큰은 어느 경로에 있나요?", "평문을 보여 주세요"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog, state = Path(tmp) / "catalog", Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for question, value_request in variants:
                    for field in ("choices", "options"):
                        for choice in (value_request, {"label": "Other", "description": value_request}):
                            with self.subTest(tool=tool_name, question=question, field=field, choice=choice):
                                payload = self.payload(question)
                                payload["tool_name"] = tool_name
                                payload["tool_input"]["questions"][0][field] = [choice]
                                guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                                verdict = guard.evaluate(payload, state, catalog)
                                self.assertIsNotNone(verdict)
                                self.assertEqual("credential_request_scope_ambiguous", verdict["code"])

    def test_named_model_token_resources_are_not_credentials(self):
        guard = load_guard()
        questions = (
            "Which model token budget should we use?",
            "What is the model token usage?",
            "Tell me the model token count.",
            "Which model token quota should we use?",
            "모델 토큰 예산은 어느 것으로 할까요?",
            "모델 토큰 사용량을 알려 주세요.",
            "모델 토큰 개수를 알려 주세요.",
            "모델 토큰 할당량은 얼마인가요?",
        )
        with tempfile.TemporaryDirectory() as tmp:
            for tool_name in ("clarify", "AskUserQuestion"):
                for question in questions:
                    with self.subTest(tool=tool_name, question=question):
                        payload = self.payload(question)
                        payload["tool_name"] = tool_name
                        self.assertIsNone(guard.evaluate(payload, Path(tmp)))

    def test_resource_metadata_does_not_exempt_explicit_secret_requests(self):
        guard = load_guard()
        questions = (
            "Which model token budget should we use? Paste your API key here.",
            "Model token usage: send me your password.",
            "Model token count: what is your API_token value?",
            "Model token quota: tell me your password value.",
            "모델 토큰 예산을 정하고 비밀번호를 알려 주세요.",
            "모델 토큰 사용량과 API key 값을 알려 주세요.",
            "모델 토큰 개수와 토큰 값을 알려 주세요.",
            "모델 토큰 할당량과 비밀번호 값을 알려 주세요.",
            "What is your token budget?",
            "What is your model token value?",
            "토큰 값을 알려 주세요.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog, state = Path(tmp) / "catalog", Path(tmp) / "state"
            for tool_name in ("clarify", "AskUserQuestion"):
                for question in questions:
                    with self.subTest(tool=tool_name, question=question):
                        payload = self.payload(question)
                        payload["tool_name"] = tool_name
                        guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                        verdict = guard.evaluate(payload, state, catalog)
                        self.assertIsNotNone(verdict)
                        self.assertEqual("block", verdict["action"])

    def test_implicit_context_keeps_neutral_pointer_and_separate_questions(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            catalog, state = Path(tmp) / "catalog", Path(tmp) / "state"
            for question, choices in (
                ("Where is your password stored?", ["Vault", "Defer", "Tell me its location"]),
                ("비밀번호는 어디에 보관되어 있나요?", ["보류", "위치를 알려 주세요"]),
                ("Which model token budget should we use?", ["Tell me its value"]),
                ("모델 토큰 예산은 어느 것으로 할까요?", ["그 값을 알려 주세요"]),
            ):
                with self.subTest(question=question):
                    payload = self.payload(question)
                    payload["tool_input"]["questions"][0]["choices"] = choices
                    payload["tool_input"]["questions"].append({
                        "question": "Which deployment setting?", "choices": ["Tell me its value"]})
                    guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
                    self.assertIsNone(guard.evaluate(payload, state, catalog))

    def test_pointer_choices_preserve_receipt_and_unrelated_choices(self):
        import json
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog"
            catalog.mkdir()
            (catalog / "team.json").write_text(json.dumps({"_meta": {"workspace": "team"}}))
            state = Path(tmp) / "state"
            payload = self.payload("Which option?")
            payload["tool_input"]["questions"][0]["choices"] = [
                {"label": "Vault", "description": "Where is the administrator password stored?"},
                "Defer",
            ]
            self.assertEqual("credential_preflight_required", guard.evaluate(payload, state, catalog)["code"])
            guard.preflight(catalog, state, "session-a", "team", guard.request_hash(payload))
            self.assertIsNone(guard.evaluate(payload, state, catalog))
            payload["tool_input"]["questions"][0]["choices"] = ["Proceed to Green", "Defer"]
            self.assertIsNone(guard.evaluate(payload, state, catalog))

if __name__ == "__main__":
    unittest.main()

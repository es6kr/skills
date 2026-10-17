"""Bounded PR623 text-guard regressions; all fixtures are local."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLEANUP = ROOT / 'skills/cleanup/resources/block-cleanup-without-rag.sh'
FA = ROOT / 'skills/fa/resources/force-fa-on-correction-signal.sh'
LANGUAGE = ROOT / 'skills/hook-kit/resources/block-skill-language-mismatch.sh'


def run_guard(script, payload, *args, environment=None):
    env = os.environ.copy()
    env.update(RALPH_LOOP='0', AGENT_HEADLESS='0', LC_ALL='C')
    env.update(environment or {})
    return subprocess.run(['bash', str(script), *args], input=payload,
                          text=True, capture_output=True, env=env)


class CleanupTests(unittest.TestCase):
    def report(self, text):
        return run_guard(CLEANUP, json.dumps({'response': text}))

    def test_incomplete_is_not_complete(self):
        result = self.report('cleanup wrap-up: incomplete\n| Step | Result |\n| Commit | done |')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_zero_failed_tests_do_not_exempt_success(self):
        result = self.report('cleanup complete\n| Tests | 20 passed, 0 failed |')
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_declared_cleanup_failure_is_exempt(self):
        result = self.report('cleanup FAILED\n| Tests | 20 passed |')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_declared_rag_failure_is_exempt(self):
        result = self.report('cleanup wrap-up\nRAG ingest failed; queued for retry task\n| Tests | passed |')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_unrelated_failed_test_does_not_exempt_success(self):
        result = self.report('cleanup complete\n| Tests | 1 failed |')
        self.assertEqual(result.returncode, 2, result.stdout)


class FATests(unittest.TestCase):
    def submit(self, text):
        return run_guard(FA, json.dumps({'hook_event_name': 'UserPromptSubmit', 'prompt': text}))

    def test_third_party_why_question_is_neutral(self):
        self.assertEqual(self.submit('why does the build report missing deps?').stdout, '')

    def test_polite_user_request_is_neutral(self):
        self.assertEqual(self.submit('sorry, also add a test').stdout, '')

    def test_agent_directed_correction_still_triggers(self):
        self.assertIn('FA_CORRECTION_GATE', self.submit('why did you omit the tests?').stdout)

    def stop(self, user, assistant):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            transcript = Path(directory) / 'transcript.jsonl'
            transcript.write_text('\n'.join(json.dumps(row) for row in [
                {'type': 'user', 'message': {'content': user}},
                {'type': 'assistant', 'message': {'content': assistant}},
            ]))
            return run_guard(FA, json.dumps({'hook_event_name': 'Stop',
                                            'transcript_path': str(transcript)}))

    def test_assistant_apology_stop_requires_fa(self):
        result = self.stop('add a test', [{'type': 'text', 'text': 'Sorry, I missed the tests.'}])
        self.assertEqual(json.loads(result.stdout)['decision'], 'block')

    def test_neutral_user_and_assistant_stop_is_silent(self):
        self.assertEqual(self.stop('sorry, also add a test', [{'type': 'text', 'text': 'Test added.'}]).stdout, '')

    def test_assistant_apology_with_fa_passes(self):
        result = self.stop('add a test', [
            {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'fa'}},
            {'type': 'text', 'text': 'Sorry, I missed the tests.'},
        ])
        self.assertEqual(result.stdout, '')


class LanguageTests(unittest.TestCase):
    def check_language(self, frontmatter, content, expected):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory) / 'skills' / 'fixture'
            root.mkdir(parents=True)
            (root / 'SKILL.md').write_text('---\n' + frontmatter + '\n---\n')
            result = run_guard(LANGUAGE, json.dumps({'tool_name': 'Write', 'tool_input': {
                'file_path': str(root / 'notes.md'), 'content': content}}))
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 2:
                self.assertIn('1:', result.stderr)

    def test_english_description_denies_unicode(self):
        self.check_language('description: English skill', '\uac00\ud7a3', 2)

    def test_english_override_denies_unicode(self):
        self.check_language('language: en\ndescription: \uac00', '\uac00', 2)

    def test_korean_description_allows_unicode(self):
        self.check_language('description: \uac00', '\uac00', 0)

    def test_english_override_trailing_spaces_stays_strict(self):
        self.check_language('language: en  \ndescription: \uac00', '\uac00', 2)

    def test_korean_override_trailing_spaces_stays_permissive(self):
        self.check_language('language: ko  \ndescription: English skill', '\uac00', 0)

    def test_english_override_trailing_comment_stays_strict(self):
        self.check_language('language: en  # authoritative\ndescription: \uac00', '\uac00', 2)

    def test_unicode_detector_failure_denies(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory) / 'skills' / 'fixture'
            root.mkdir(parents=True)
            (root / 'SKILL.md').write_text('---\nlanguage: en\ndescription: English\n---\n')
            detector = Path(directory) / 'python3'
            detector.write_text('#!/bin/sh\nexit 1\n')
            detector.chmod(0o755)
            result = run_guard(LANGUAGE, json.dumps({'tool_name': 'Write', 'tool_input': {
                'file_path': str(root / 'notes.md'), 'content': '\uac00'}}),
                environment={'PATH': directory + os.pathsep + os.environ['PATH']})
            self.assertEqual(result.returncode, 2)

    def test_english_text_is_allowed(self):
        self.check_language('description: English skill', 'plain English', 0)


if __name__ == '__main__':
    unittest.main()

"""Regression for the real stat invocation used by edit-guard on Linux."""
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD = ROOT / 'skills/hook-kit/resources/edit-guard.sh'

class EditGuardSizeTest(unittest.TestCase):
    def test_file_size_is_numeric_on_gnu_stat(self):
        line = next(line.strip() for line in GUARD.read_text().splitlines()
                    if line.strip().startswith('file_size=$(stat '))
        with tempfile.TemporaryDirectory() as td:
            for size in (3, 6000):
                with self.subTest(size=size):
                    file = pathlib.Path(td) / 'payload with spaces.json'
                    file.write_bytes(b'x' * size)
                    code = 'set -eu; FILE_PATH="$1"; ' + line + '; [[ "$file_size" -gt 5120 ]] && result=large || result=small; printf "%s:%s" "$file_size" "$result"'
                    result = subprocess.run(['bash', '-c', code, 'test', str(file)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, f'{size}:{"large" if size > 5120 else "small"}')

if __name__ == '__main__':
    unittest.main()

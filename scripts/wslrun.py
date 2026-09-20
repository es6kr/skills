#!/usr/bin/env python3
"""
wslrun.py - Run repository Python scripts under WSL without temporary shell files.

Translates Windows paths and arguments to WSL format, preserves arguments (quotes,
brackets, spaces) without shell interpretation, and executes under WSL python3.

Usage:
  python scripts/wslrun.py [--uv] [--python <bin>] <script_path> [args...]

Examples:
  python scripts/wslrun.py skills/fix-plan/scripts/update_item.py --file .agents/fix_plan.md --match "[x]"
  python scripts/wslrun.py --uv pytest tests/test_deploy.py
"""

import sys
import os
import re
import subprocess
import shutil

# Ensure UTF-8 output on Windows consoles
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def win_to_wsl_path(path: str) -> str:
    """Convert a Windows path (C:\\foo\\bar or C:/foo/bar) to WSL path (/mnt/c/foo/bar)."""
    if not path:
        return path
    # Normalize slashes
    norm = path.replace("\\", "/")
    # Match drive letter: e.g. C:/... or c:/...
    m = re.match(r"^([a-zA-Z]):/(.*)$", norm)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2)
        return f"/mnt/{drive}/{rest}"
    # Match bare drive: e.g. C:
    m = re.match(r"^([a-zA-Z]):$", norm)
    if m:
        drive = m.group(1).lower()
        return f"/mnt/{drive}"
    return norm

def translate_arg(arg: str) -> str:
    """
    Intelligently translate path-like arguments from Windows to WSL format.
    Preserves non-path arguments (regexes, flags, bracket expressions) intact.
    """
    if not arg:
        return arg

    # Check for --key=value format
    if arg.startswith("--") and "=" in arg:
        key, val = arg.split("=", 1)
        translated_val = translate_arg(val)
        return f"{key}={translated_val}"

    # Check for direct Windows drive path: C:\... or C:/...
    if re.match(r"^[a-zA-Z]:[/\\]", arg):
        return win_to_wsl_path(arg)

    # If running on Windows, check if the argument exists as a file or dir on host
    if sys.platform == "win32":
        try:
            if os.path.exists(arg):
                abs_path = os.path.abspath(arg)
                return win_to_wsl_path(abs_path)
        except Exception:
            pass

    return arg

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 1

    if argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    use_uv = False
    py_bin = "python3"
    args = list(argv)

    # Parse options for wslrun itself
    while args:
        if args[0] == "--uv":
            use_uv = True
            args.pop(0)
        elif args[0] == "--python" and len(args) > 1:
            py_bin = args[1]
            args = args[2:]
        elif args[0].startswith("--python="):
            py_bin = args[0].split("=", 1)[1]
            args.pop(0)
        else:
            break

    if not args:
        print("Error: No script or command specified.", file=sys.stderr)
        return 1

    if args[0] in ("-c", "-m"):
        wsl_script = args[0]
        script_args = args[1:]
        if sys.platform == "win32":
            wsl_cwd = win_to_wsl_path(os.path.abspath(os.getcwd()))
        else:
            wsl_cwd = os.getcwd()
    else:
        target_script = args[0]
        script_args = args[1:]

        # Resolve target script path to WSL format
        if sys.platform == "win32":
            abs_target = os.path.abspath(target_script)
            wsl_script = win_to_wsl_path(abs_target)
            wsl_cwd = win_to_wsl_path(os.path.abspath(os.getcwd()))
        else:
            wsl_script = target_script
            wsl_cwd = os.getcwd()

    # Translate script arguments
    translated_args = [translate_arg(a) for a in script_args]

    # Build command to execute inside WSL
    if use_uv:
        inner_cmd = ["uv", "run", py_bin, wsl_script] + translated_args
    else:
        inner_cmd = [py_bin, wsl_script] + translated_args

    if sys.platform == "win32":
        wsl_exe = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl_exe:
            print("Error: 'wsl' command not found on Windows host.", file=sys.stderr)
            return 127
        full_cmd = [wsl_exe, "--cd", wsl_cwd, "--"] + inner_cmd
    else:
        # Already running under Linux / WSL
        full_cmd = inner_cmd

    try:
        res = subprocess.run(full_cmd)
        return res.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error executing under WSL: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())

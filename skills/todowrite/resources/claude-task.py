#!/usr/bin/env python3
"""Compatibility entrypoint; implementation and import globals stay shared."""
from pathlib import Path

_source = Path(__file__).resolve().with_name("agent-task.py")
exec(compile(_source.read_text(encoding="utf-8"), str(_source), "exec"), globals())

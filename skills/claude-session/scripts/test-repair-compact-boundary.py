#!/usr/bin/env python3
"""Regression test: session repair must NOT bridge the chain across a compact boundary.

Invariant (documented in repair.md §"Repair Broken Chain"):
    `parentUuid: null` is normal — do not touch. It marks a chain ROOT, which
    occurs at the file start AND at every compact/resume boundary (Claude Code
    re-roots the chain there; the isCompactSummary node's parent is a `system`
    node written with parentUuid: null).

`dedup-session.py` Pass 6 ("rebuild chain / sequential linking") used to force
every non-first message's parentUuid to the previous line's uuid, overwriting a
mid-file null and splicing pre-compact history onto post-compact history. This
test fails against that old behavior and passes once the null is preserved.

Run:
    uv run python test-repair-compact-boundary.py
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_scripts_dir = Path(__file__).parent
_spec = importlib.util.spec_from_file_location("dedup_session", _scripts_dir / "dedup-session.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
dedup_session = _mod.dedup_session


def _msg(uuid, parent, *, mtype="assistant", msg_id=None, text="x", extra=None):
    d = {"type": mtype, "uuid": uuid, "parentUuid": parent, "isSidechain": False}
    if mtype in ("assistant", "user"):
        m = {"role": "assistant" if mtype == "assistant" else "user",
             "content": [{"type": "text", "text": text}]}
        if msg_id is not None:
            m["id"] = msg_id
        d["message"] = m
    if extra:
        d.update(extra)
    return d


def build_session():
    """A session with a file-start root, one compact boundary, a dangling parent,
    and a duplicate — the shapes Pass 6 must each handle correctly."""
    return [
        _msg("u0", None, mtype="user", msg_id="m0", text="hello"),                 # file-start root
        _msg("u1", "u0", msg_id="m1", text="reply-1 (rich, kept over dup)"),        # normal
        # --- compact boundary: system re-root with parentUuid:null, then summary ---
        _msg("u2", None, mtype="system", text="compact re-root"),                   # MUST stay null
        _msg("u3", "u2", mtype="user", text="<compact summary>",
             extra={"isCompactSummary": True}),                                     # summary -> re-root
        _msg("u4", "u3", msg_id="m4", text="post-compact reply"),                   # normal
        _msg("u5", "GHOST-UUID", msg_id="m5", text="dangling parent"),             # dangling -> repair
        _msg("u1dup", "u5", msg_id="m1", text="dup of m1"),                         # duplicate of m1 -> removed
    ]


def run_dedup(messages):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "session.jsonl"
        with src.open("w", encoding="utf-8") as f:
            for m in messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        result = dedup_session(src, dry_run=False)
        out = Path(result["output_file"])
        final = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return final, result


def main():
    final, result = run_dedup(build_session())
    by_uuid = {d.get("uuid"): d for d in final}
    failures = []

    # 1. THE FIX: mid-file compact-boundary re-root keeps parentUuid == null
    u2 = by_uuid.get("u2")
    if u2 is None:
        failures.append("compact re-root u2 was dropped")
    elif u2.get("parentUuid") is not None:
        failures.append(f"compact boundary bridged: u2.parentUuid={u2.get('parentUuid')!r} (want null)")

    # 2. file-start root stays null
    u0 = by_uuid.get("u0")
    if not u0 or u0.get("parentUuid") is not None:
        failures.append(f"file-start root not null: u0.parentUuid={u0 and u0.get('parentUuid')!r}")

    # 3. compact summary still points at its re-root (chain intact across the boundary node)
    u3 = by_uuid.get("u3")
    if not u3 or u3.get("parentUuid") != "u2":
        failures.append(f"compact summary detached: u3.parentUuid={u3 and u3.get('parentUuid')!r} (want u2)")

    # 4. NO REGRESSION: a genuinely dangling parent is still repaired to the previous line
    u5 = by_uuid.get("u5")
    if not u5 or u5.get("parentUuid") != "u4":
        failures.append(f"dangling parent not repaired: u5.parentUuid={u5 and u5.get('parentUuid')!r} (want u4)")

    # 5. dedup still works: the duplicate of m1 is removed
    if "u1dup" in by_uuid:
        failures.append("duplicate message (u1dup) was not removed")
    if len(final) != 6:
        failures.append(f"unexpected final line count: {len(final)} (want 6)")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"PASS (final lines={len(final)}, chains repaired={result.get('fixed_chains')})")


if __name__ == "__main__":
    main()

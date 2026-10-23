#!/usr/bin/env python3
"""Source-owned, secret-free Hermes clarification preflight.

This verifies a pointer catalog, not credentials, permissions or secret-store
availability. It never loads a secret, performs a network request or issues a
credential. The profile-local bridge only delegates to this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

TTL = 300
CONTEXT = re.compile(r"\bcredentials?\b(?![-_])|API[ _-]?key|\b(?:(?:API|access|auth|bearer|refresh)[ _-]?)?token\b|password|\uC790\uACA9\uC99D\uBA85|\uBE44\uBC00\uBC88\uD638|\uD1A0\uD070", re.I)
REQUEST = re.compile(r"where|provide|supply|paste|reissue|generate|missing|unavailable|stored|\uC5B4\uB290|\uBCF4\uAD00|\uC54C\uB824\s*\uC8FC|\uBC1C\uAE09|\uCC3E\uC9C0\s*\uBABB|\uBD80\uC7AC", re.I)
VALUE_HANDOVER = re.compile(r"(?:paste|send|provide|supply|share|enter|give)\s+(?:(?:me|your|the|a|an|admin|administrator|actual|full)\s+)*(?:API\s*key|password|(?:(?:access|auth|bearer|refresh)\s*)?token|secret\s*value)|\uD1A0\uD070\s*(?:\uAC12\uC744\s*)?\uBCF4\uB0B4\s*\uC8FC|\uBE44\uBC00\uBC88\uD638\uB97C\s*\uC54C\uB824\s*\uC8FC", re.I)
FORBIDDEN_FIELDS = {"password", "token", "client_secret", "api_key", "private_key", "secret_value"}
POINTER_FIELDS = {"kind", "service", "purpose", "location", "issued_via"}


def request_hash(payload):
    raw = json.dumps(payload.get("tool_input", {}), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def receipt_path(state_root, session):
    return Path(state_root) / (hashlib.sha256(session.encode()).hexdigest() + ".json")


def texts_of(payload):
    questions = payload.get("tool_input", {}).get("questions", [])
    if not isinstance(questions, list):
        return []
    parts = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        parts.append(str(q.get("question", "")))
        for field in ("choices", "options"):
            for item in q.get(field, []):
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(item.get(k, "")) for k in ("label", "description"))
    return parts


def text_of(payload):
    return " ".join(texts_of(payload))


def catalog_snapshot(root, workspace):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", workspace):
        raise ValueError("invalid workspace identifier")
    root = Path(root).resolve()
    path = (root / (workspace + ".json")).resolve()
    if path.parent != root:
        raise ValueError("catalog escapes configured root")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"catalog_path": str(path), "catalog_state": "missing", "catalog_digest": None, "workspace": workspace, "entries": {}}
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("_meta"), dict) or data["_meta"].get("workspace") != workspace:
        raise ValueError("catalog workspace metadata mismatch")
    pending = [data]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if any(str(k).casefold().replace("-", "_") in FORBIDDEN_FIELDS for k in value):
                raise ValueError("catalog must contain pointer-only records")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    entries = {}
    for key, entry in data.items():
        if key == "_meta":
            continue
        if not isinstance(entry, dict) or FORBIDDEN_FIELDS.intersection(entry):
            raise ValueError("catalog must contain pointer-only records")
        if any(k in POINTER_FIELDS and not isinstance(v, str) for k, v in entry.items()):
            raise ValueError("public pointer metadata must be strings, not structured values")
        entries[key] = {k: v for k, v in entry.items() if k in POINTER_FIELDS}
    return {"catalog_path": str(path), "catalog_state": "read", "catalog_digest": hashlib.sha256(raw).hexdigest(), "workspace": workspace, "entries": entries}


def preflight(catalog_root, state_root, session, workspace, fingerprint):
    if not session or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise ValueError("nonempty native session and exact request hash required")
    snapshot = catalog_snapshot(catalog_root, workspace)
    receipt = {k: v for k, v in snapshot.items() if k != "entries"}
    receipt.update({"version": 1, "session": session, "request_hash": fingerprint, "checked_at": time.time()})
    target = receipt_path(state_root, session)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"success": True, **snapshot, "receipt": str(target), "request_hash": fingerprint, "boundary": "Pointer lookup only; still verify the declared custody route and account identity. Never request secret values in chat."}


def location_only(text):
    """Require a location request in every clause, not a location keyword."""
    location = r"(?:location|path|pointer|custody)"
    subject = (
        r"(?:(?:the|your|our|my|its|administrator|admin|missing|API|access|auth|bearer|refresh)\s+)*"
        r"(?:credentials?|password|API[ _-]?key|(?:API|access|auth|bearer|refresh)[ _-]?token|token|it|they)"
    )
    intent = re.compile(
        r"(?:where\s+(?:is|are)\s+" + subject
        + r"\s+(?:(?:stored|kept|saved|held|located)|(?:storage\s+)?" + location + r")"
        r"|(?:what|which)\s+(?:is|are)\s+[^?!.;]*\b" + location + r"\b"
        r"|which\s+(?:file\s+)?" + location + r"\b.+"
        r"|(?:please\s+)?(?:provide|tell\s+me|show\s+me)\s+[^?!.;]*\b" + location + r"\b"
        r"|[^?!.;]*(?:비밀번호|토큰|자격증명)(?:은|는|이|가|의)?\s*"
        r"(?:(?:어디|어느\s*(?:경로|위치|저장소))[^?!.;]*(?:보관|저장|있|찾)[^?!.;]*"
        r"|(?:보관|저장)?\s*(?:위치|경로)(?:를|는|가)?\s*(?:알려|어디|무엇)[^?!.;]*))",
        re.I,
    )
    # A custody question may not double as a request to transfer a value.
    if re.search(r"\b(?:paste|send|supply|share|enter|give|values?|contents?|plain[\s_-]*text)\b|값|내용|평문|보내|붙여", text, re.I):
        return False
    clauses = [part.strip() for part in re.split(r"[?!.;,]+|\b(?:and|or)\b", text, flags=re.I) if part.strip()]
    return bool(clauses) and all(intent.fullmatch(part) for part in clauses)


def credential_context(text):
    """Exclude only explicitly named model resource metrics, not other secrets."""
    resource = r"\bmodel\s+tokens?\s+(?:budget|usage|count|quota)\b|모델\s+토큰\s+(?:예산|사용량|개수|할당량)(?=$|\s|[은는이가을를?!.;,])"
    return CONTEXT.search(re.sub(resource, "", text, flags=re.I))


def evaluate(payload, state_root, catalog_root=None):
    if payload.get("hook_event_name") != "pre_tool_call" or payload.get("tool_name") not in {"clarify", "AskUserQuestion"}:
        return None
    text = text_of(payload)
    if VALUE_HANDOVER.search(text):
        return {"action": "block", "code": "secret_handover_forbidden", "message": "Do not request secret values in chat. Use only approved pointer locations and user-owned login."}
    if not any(credential_context(part) for part in texts_of(payload)):
        return None
    # Resolve implicit value references only within their own question/options.
    # Neutral labels and unrelated questions do not inherit credential intent.
    implicit_value = re.compile(
        r"\b(?:values?|contents?|plain[\s_-]*text)\b|"
        r"\b(?:reveal|paste|send|share|give|show)\s+(?:me\s+)?(?:it|them)\b|"
        r"\btell\s+me\s+what\s+(?:it|they)\s+(?:is|are)\b|값|내용|평문|보내|붙여",
        re.I,
    )
    ambiguous = any(credential_context(part) and not location_only(part) for part in texts_of(payload))
    for question in payload.get("tool_input", {}).get("questions", []):
        parts = texts_of({"tool_input": {"questions": [question]}})
        if any(credential_context(part) for part in parts):
            ambiguous = ambiguous or any(implicit_value.search(part) for part in parts)
    if ambiguous:
        return {"action": "block", "code": "credential_request_scope_ambiguous", "message": "This bridge permits only pointer-location questions, never secret-value questions. Use a separate scope/profile decision instead of requesting a credential value."}
    session = str(payload.get("session_id") or "")
    fingerprint = request_hash(payload)
    reason = "no_verified_catalog_receipt"
    try:
        receipt = json.loads(receipt_path(state_root, session).read_text(encoding="utf-8"))
        age = time.time() - receipt["checked_at"]
        if (receipt.get("version") == 1 and session and receipt.get("session") == session
                and receipt.get("request_hash") == fingerprint and 0 <= age <= TTL):
            root = Path(catalog_root) if catalog_root is not None else Path(receipt["catalog_path"]).parent
            current = catalog_snapshot(root, receipt["workspace"])
            if all(receipt.get(k) == current.get(k) for k in ("catalog_path", "catalog_state", "catalog_digest")):
                return None
            reason = "catalog_changed"
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return {"action": "block", "code": "credential_preflight_required", "message": "Credential pointer-catalog preflight is required before this clarification. Run this source helper with --preflight, a resolved --workspace, --session=" + session + " and --request-hash=" + fingerprint + "; inspect its pointer-only result, verify declared custody, then retry only the same question. This is not permission to reset or issue credentials.", "session_id": session, "request_hash": fingerprint, "reason": reason}


def handle_payload(payload):
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return evaluate(payload, home / "hooks" / "credential-preflight-state", Path(os.environ.get("AGENT_POINTER_CATALOG_ROOT", str(Path.home() / ".agents" / "credentials-index"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--session")
    parser.add_argument("--workspace")
    parser.add_argument("--request-hash")
    parser.add_argument("--catalog-root", default=str(Path.home() / ".agents" / "credentials-index"))
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    parser.add_argument("--state-root", default=str(home / "hooks" / "credential-preflight-state"))
    args = parser.parse_args()
    try:
        if args.preflight:
            result = preflight(args.catalog_root, args.state_root, args.session, args.workspace, args.request_hash)
        else:
            result = evaluate(json.load(sys.stdin), args.state_root, args.catalog_root)
        if result is not None:
            print(json.dumps(result, ensure_ascii=True))
        return 2 if isinstance(result, dict) and result.get("action") == "block" else 0
    except (ValueError, TypeError, OSError) as exc:
        print(json.dumps({"action": "block", "code": "credential_preflight_invalid", "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

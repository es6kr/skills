"""Explicit native Hermes probe; synthetic admitted event, real isolated store.

No Gateway, ticker, AGY inference, installed plugin, or live credentials are used.
The plugin registration/observer routing is an isolated in-process collaborator;
the admission producer, lifecycle dispatch, PluginContext and cron store are real.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--protected-cron", type=Path, required=True)
    args = parser.parse_args()
    protected_before = fingerprint(args.protected_cron)
    sys.path.insert(0, str(args.hermes_source.resolve()))
    bootstrap = {key: value for key, value in os.environ.items()
                 if key.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "HOME",
                                    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"}}
    result = {"kind": "isolated native producer/dispatch/store; not serving Gateway acceptance"}
    with tempfile.TemporaryDirectory(prefix="quota-native-") as directory:
        home = Path(directory).resolve()
        os.environ.clear()
        os.environ.update(bootstrap, HERMES_HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
        from cron import jobs
        from cron.scheduler_script import _resolve_script_path, _run_job_script
        from gateway.config import Platform
        from gateway.session import SessionSource
        from gateway.run_inbound_consumer import run_post_admission_hook
        from hermes_cli import lifecycle, plugins
        state = home / "quota-reservation"
        state.mkdir()
        runner = home / "scripts" / "quota-reservation" / "first_use.py"
        runner.parent.mkdir(parents=True)
        shutil.copyfile(PACKAGE / "scripts" / "first_use.py", runner)
        cli = home / "antigravity-cli.EXE"
        cli.write_bytes(b"Not an executable: this native booking probe must never call AGY.\n")
        source = SessionSource(
            platform=Platform.DISCORD, chat_id="100000000000000002", chat_type="thread",
            user_id="100000000000000001", thread_id="100000000000000002",
            scope_id="100000000000000003", profile="fixture")
        policy = {
            "enabled": True, "profile": "fixture", "approval_ref": "offline-native-probe-only",
            "allowed_user_ids": [source.user_id], "allow_existing_default": True,
            "allowed_origins": [{"platform": "discord", "chat_id": source.chat_id,
                                 "thread_id": source.thread_id, "scope_id": source.scope_id}],
            "agy_executable": str(cli),
        }
        (state / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
        adapter_dir = PACKAGE / "adapters" / "hermes"
        manifest = plugins.parse_manifest_file(adapter_dir / "plugin.yaml", adapter_dir, "user", "")
        if manifest is None:
            raise RuntimeError("Native manifest did not parse")
        manager = plugins.PluginManager(scope_key=str(home))
        manager._discovered = True  # Deliberately do not discover/load any installed/bundled plugins.
        manager._plugins[manifest.name] = plugins.LoadedPlugin(manifest=manifest, enabled=True)
        ctx = plugins.PluginContext(manifest, manager)
        spec = importlib.util.spec_from_file_location("native_quota_fixture", adapter_dir / "__init__.py")
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        adapter.register(ctx)
        message_id = str((int(datetime.now(timezone.utc).timestamp() * 1000) - 1420070400000) << 22)
        event = SimpleNamespace(message_id=message_id, text="agy Refreshes in 1h")
        host = SimpleNamespace(config=SimpleNamespace(multiplex_profiles=False))
        with jobs.use_cron_store(home):
            untouched = jobs.create_job(prompt="Unrelated isolated control", schedule="2099-01-01T00:00:00+00:00",
                                        paused=True, repeat=1, deliver="local", pinned=False)
            before = jobs.get_job(untouched["id"])
            import subprocess
            with asyncio.Runner() as loop, \
                    patch.object(plugins, "_delivery_manager", return_value=manager), \
                    patch.object(lifecycle, "_observe", return_value=None), \
                    patch.object(subprocess, "Popen", side_effect=AssertionError("No provider process permitted")):
                first = loop.run(run_post_admission_hook(host, event, source, "native-fixture"))
                repeat = loop.run(run_post_admission_hook(host, event, source, "native-fixture"))
            population = jobs.list_jobs(include_disabled=True)
            owned = [job for job in population if job["name"].startswith("quota-first-use:")]
            if len(owned) != 1 or first[0] is not True or repeat[0] is not True:
                raise AssertionError("Native admission did not create exactly one handled reservation")
            job = jobs.get_job(owned[0]["id"])
            if job["id"] not in first[1] or job["id"] not in repeat[1]:
                raise AssertionError("Admission reply did not contain the readback reservation ID")
            if job["enabled"] is not True or job["state"] != "scheduled" or job["no_agent"] is not True:
                raise AssertionError("Native record not active/no-agent")
            if jobs.get_job(untouched["id"]) != before:
                raise AssertionError("Unrelated native control changed")
            accepted, error = _resolve_script_path(str(runner))
            rejected, blocked = _resolve_script_path(str(PACKAGE / "scripts" / "first_use.py"))
            if accepted != runner or error is not None or rejected is not None or not blocked:
                raise AssertionError("Native script containment did not enforce both sides")
            # Execute the REAL Python script via the REAL native child runner. It is
            # not due and must refuse BEFORE the intentionally nonexecutable CLI.
            success, output = _run_job_script(str(runner), workdir=job["workdir"], interpreter=sys.executable)
            if (success or '"state": "not_verified"' not in output
                    or '"reason": "not_due_or_expired"' not in output):
                raise AssertionError("Future request was not safely refused in the real child")
            result.update(native_manifest_parsed=True, native_hook_registered=True,
                          admitted_handled=first[0], duplicate_handled=repeat[0],
                          owned_native_jobs=len(owned), total_native_jobs=len(population),
                          native_record_active=True, unrelated_control_unchanged=True,
                          native_script_containment=True, real_child_not_due_refusal=True,
                          agy_inference_performed=False,
                          cron_store=str(home / "cron" / "jobs.json"))
        producers = ["gateway/run_inbound_consumer.py", "hermes_cli/lifecycle.py", "hermes_cli/plugins.py",
                     "hermes_cli/plugins_dispatch.py", "cron/jobs.py", "cron/scheduler_script.py"]
        result["native_source_sha256"] = {name: fingerprint(args.hermes_source / name) for name in producers}
    result["temporary_profile_removed"] = not home.exists()
    result["protected_cron_sha256_before"] = protected_before
    result["protected_cron_sha256_after"] = fingerprint(args.protected_cron)
    if result["protected_cron_sha256_after"] != protected_before:
        raise AssertionError("Protected cron changed during the isolated probe")
    args.evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

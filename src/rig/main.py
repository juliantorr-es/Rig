from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import commands_window, commands_bias, commands_action, commands_affected, commands_agent, commands_anigma, commands_atlas, commands_audit, commands_bench, commands_board, commands_bootstrap, commands_brief, commands_bundle, commands_context, commands_db, commands_diff, commands_docs, commands_doctor, commands_embeddings, commands_git, commands_graph, commands_intent, commands_llm, commands_loop_engine as commands_loop, commands_models, commands_monitor, commands_notify, commands_patch, commands_pipeline, commands_policy, commands_product, commands_project, commands_prompt, commands_queue, commands_release, commands_schema, commands_structural, commands_swarm, commands_swift, commands_textual, commands_tui, commands_vault, commands_workspace
from .paths import repo_root
from rig_tools.notifications import choose_backend, send_notification, should_notify


@dataclass
class RigHelpers:
    repo_root: Path
    output_mode: str = "human"
    notify_trigger: str = "never"
    notify_backend: str | None = None
    _current_events: list[dict] | None = None
    _current_run_id: str | None = None

    def command_text(self, args: list[str]) -> str:
        return " ".join(args)

    def _result_path(self) -> Path:
        out_dir = self.repo_root / ".build" / "rig" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / "latest.json"

    def _run_result_path(self, run_id: str) -> Path:
        out_dir = self.repo_root / ".build" / "rig" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{run_id}.json"

    def _events_path(self, run_id: str) -> Path:
        out_dir = self.repo_root / ".build" / "rig" / "events"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{run_id}.jsonl"

    def _write_result_bundle(self, payload: dict, *, run_id: str | None = None) -> Path:
        payload = self._apply_notification(payload)
        latest = self._result_path()
        latest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if run_id:
            self._run_result_path(run_id).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return latest

    def _apply_notification(self, payload: dict) -> dict:
        payload = dict(payload)
        status = payload.get("status")
        requested = should_notify(self.notify_trigger, status)
        backend = choose_backend(self.notify_backend) if requested else None
        if not requested:
            payload.update({"notification_requested": False, "notification_backend": None, "notification_status": "skipped", "notification_error": None})
            return payload
        result = send_notification(
            title=f"Rig {status}",
            subtitle=payload.get("task") or payload.get("command"),
            message=(payload.get("summary") or {}).get("command_summary") or payload.get("command") or status or "Rig finished",
            backend=backend,
        )
        payload.update(result.to_dict())
        return payload

    def _begin_stream(self, run_id: str) -> None:
        self._current_run_id = run_id
        self._current_events = []

    def _append_event(self, event: dict) -> None:
        if self._current_events is not None:
            self._current_events.append(event)

    def _finish_stream(self, run_id: str) -> Path | None:
        if self._current_events is None:
            return None
        from rig_tools.events import write_event_stream

        path = self._events_path(run_id)
        write_event_stream(path, self._current_events)
        latest = self.repo_root / ".build" / "rig" / "events" / "latest.jsonl"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        self._current_events = None
        self._current_run_id = None
        return path

    def _emit(self, payload: dict, *, stream: str = "stdout") -> None:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._append_event(payload)
        if stream == "stderr":
            print(text, file=sys.stderr)
        else:
            print(text)

    def _write_result(self, payload: dict) -> Path:
        return self._write_result_bundle(payload, run_id=payload.get("run_id"))

    def _record_cache_sidecar(self, script_name: str, command: list[str], duration_seconds: float | None = None) -> None:
        from rig_tools.cache_metadata import record_metadata

        mapping = {
            "anigma_build_repo_atlas.py": (
                "atlas-build",
                "anigma_build_repo_atlas",
                [self.repo_root / "scripts" / "anigma_build_repo_atlas.py"],
                [self.repo_root / "Docs" / "atlas" / "repo-map.json", self.repo_root / "Docs" / "atlas" / "targets.json", self.repo_root / "Docs" / "atlas" / "risk-index.json"],
            ),
            "anigma_state_flow_audit.py": (
                "state-flow-audit",
                "anigma_state_flow_audit",
                [self.repo_root / "scripts" / "anigma_state_flow_audit.py"],
                [self.repo_root / ".build" / "anigma-state-flow-audit.json", self.repo_root / "Docs" / "atlas" / "state-map.json"],
            ),
            "anigma_pipeline.py": (
                "pipeline",
                "anigma_pipeline",
                [self.repo_root / "scripts" / "anigma_pipeline.py"],
                [self.repo_root / ".build" / "anigma-pipeline" / "runs"],
            ),
        }
        if script_name not in mapping:
            return
        artifact_id, producer, inputs, outputs = mapping[script_name]
        try:
            record_metadata(self.repo_root, artifact_id=artifact_id, producer=producer, command=self.command_text(command), input_paths=inputs, output_paths=outputs, duration_seconds=duration_seconds)
        except Exception:
            return

    def delegate(self, script_name: str, args: list[str], quiet: bool) -> int:
        script = self.repo_root / "scripts" / script_name
        if not script.exists():
            print(f"missing script: {script_name}", file=sys.stderr)
            return 2
        cmd = [sys.executable, str(script), *args]
        if self.output_mode in {"json", "jsonl", "agent"}:
            return self._delegate_streaming(script_name, cmd, quiet)
        if not quiet:
            print("+ " + " ".join(cmd))
        started = time.time()
        proc = subprocess.run(cmd, cwd=self.repo_root, check=False)
        self._record_cache_sidecar(script_name, cmd, time.time() - started)
        return proc.returncode

    def _delegate_streaming(self, script_name: str, cmd: list[str], quiet: bool) -> int:
        import uuid
        run_id = uuid.uuid4().hex[:12]
        command_text = " ".join(cmd)
        group = Path(script_name).stem
        started = time.time()
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
        emit_events = self.output_mode in {"jsonl", "agent"}
        self._begin_stream(run_id)
        if emit_events:
            self._emit({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": started_at, "run_id": run_id, "command_group": group, "command": command_text, "task": None, "attributes": {}})
        proc = subprocess.Popen(cmd, cwd=self.repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        assert proc.stdout is not None and proc.stderr is not None
        while True:
            out = proc.stdout.readline()
            err = proc.stderr.readline()
            if out:
                stdout_lines.append(out)
                if emit_events:
                    self._emit({"schema_version": "rig.event.v1", "event_type": "step_output", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run_id, "command_group": group, "command": command_text, "task": None, "attributes": {"stream": "stdout", "text": out.rstrip("\n")}})
                elif self.output_mode == "human" and not quiet:
                    print(out, end="")
            if err:
                stderr_lines.append(err)
                if emit_events:
                    self._emit({"schema_version": "rig.event.v1", "event_type": "step_output", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run_id, "command_group": group, "command": command_text, "task": None, "attributes": {"stream": "stderr", "text": err.rstrip("\n")}}, stream="stderr")
                elif self.output_mode == "human" and not quiet:
                    print(err, end="", file=sys.stderr)
            if out == "" and err == "" and proc.poll() is not None:
                break
        exit_code = proc.wait()
        finished = time.time()
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
        artifacts = []
        if exit_code == 0:
            status = "passed"
        elif exit_code == 127:
            status = "skipped"
        else:
            status = "failed"
        stderr_tail = "".join(stderr_lines)[-2000:] if stderr_lines else None
        result = {
            "schema_version": "rig.result.v1",
            "run_id": run_id,
            "command_group": group,
            "command": command_text,
            "task": None,
            "status": status,
            "exit_code": exit_code,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(finished - started, 3),
            "artifacts": artifacts,
            "warnings": [],
            "errors": ([] if exit_code == 0 else [{"message": stderr_tail or "command failed", "exit_code": exit_code}]),
            "summary": {"stdout_lines": len(stdout_lines), "stderr_lines": len(stderr_lines)},
            "next_actions": [],
            "stderr_tail": stderr_tail,
        }
        result = self._apply_notification(result)
        result_path = self._write_result_bundle(result, run_id=run_id)
        if emit_events:
            self._emit({"schema_version": "rig.event.v1", "event_type": "artifact", "timestamp_utc": finished_at, "run_id": run_id, "command_group": group, "command": command_text, "task": None, "attributes": {"path": str(result_path.relative_to(self.repo_root)), "artifact_type": "result"}})
            self._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": finished_at, "run_id": run_id, "command_group": group, "command": command_text, "task": None, "attributes": {"status": status, "exit_code": exit_code, "result_path": str(result_path.relative_to(self.repo_root))}})
            print(json.dumps(result, sort_keys=True))
        elif self.output_mode == "human" and not quiet:
            print(str(result_path.relative_to(self.repo_root)))
        if self.output_mode == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        if emit_events:
            self._finish_stream(run_id)
        self._record_cache_sidecar(Path(cmd[1]).name if len(cmd) > 1 else "", cmd, finished - started)
        return exit_code

    def run(self, cmd: list[str], quiet: bool, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        if not quiet:
            print("+ " + " ".join(cmd))
        try:
            return subprocess.run(cmd, cwd=cwd or self.repo_root, text=True, capture_output=True, check=False)
        except FileNotFoundError:
            missing = cmd[0] if cmd else "unknown"
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=f"missing tool: {missing}\n")

    def zero_copy(self, args) -> int:
        script = self.repo_root / "scripts" / "anigma_zero_copy_flow_audit.py"
        if not script.exists():
            print("zero-copy audit not implemented yet", file=sys.stderr)
            return 2
        cmd = [sys.executable, str(script)]
        if not args.quiet:
            print("+ " + " ".join(cmd))
        proc = subprocess.run(cmd, cwd=self.repo_root, check=False)
        return proc.returncode

    def swift_diagnostics_dir(self) -> Path:
        out_dir = self.repo_root / ".build" / "rig" / "swift-diagnostics"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def known_blockers_path(self) -> Path:
        return self.repo_root / "Docs" / "build" / "known-blockers.yaml"

    def load_known_blockers(self) -> list[dict]:
        from rig_tools.swift_log_parser import load_known_blockers

        path = self.known_blockers_path()
        if not path.exists():
            return []
        return load_known_blockers(path)

    def write_swift_diagnostics(
        self,
        *,
        run_label: str,
        command: list[str],
        stdout: str,
        stderr: str,
        exit_code: int,
        target: str | None = None,
        raw_input_path: Path | None = None,
        status: str | None = None,
        tool_missing: str | None = None,
        recommendation: str | None = None,
    ) -> Path:
        from rig_tools.swift_log_parser import parse_swift_log_text, render_markdown_report, summarize_diagnostics

        out_dir = self.swift_diagnostics_dir()
        blockers = self.load_known_blockers()
        combined_text = stdout + ("\n" + stderr if stderr else "")
        if raw_input_path is not None and raw_input_path.exists():
            combined_text = raw_input_path.read_text(encoding="utf-8", errors="replace")
        diagnostics = parse_swift_log_text(
            combined_text,
            command=self.command_text(command),
            target=target,
            known_blockers=blockers,
        )
        summary = summarize_diagnostics(diagnostics)
        payload = {
            "tool": "rig-swift-diagnostics",
            "run_label": run_label,
            "command": command,
            "target": target,
            "exit_code": exit_code,
            "status": status or ("passed" if exit_code == 0 else "failed"),
            "tool_missing": tool_missing,
            "recommendation": recommendation,
            "stdout_log": str((out_dir / "latest.stdout.log").relative_to(self.repo_root)),
            "stderr_log": str((out_dir / "latest.stderr.log").relative_to(self.repo_root)),
            "raw_input_log": str((out_dir / "latest.input.log").relative_to(self.repo_root)) if raw_input_path else None,
            "summary": summary,
            "diagnostics": diagnostics,
        }
        (out_dir / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out_dir / "latest.md").write_text(render_markdown_report(payload), encoding="utf-8")
        if raw_input_path is not None and raw_input_path.exists():
            raw_text = raw_input_path.read_text(encoding="utf-8", errors="replace")
            (out_dir / "latest.input.log").write_text(raw_text, encoding="utf-8")
            (out_dir / "latest.stdout.log").write_text(raw_text, encoding="utf-8")
            (out_dir / "latest.stderr.log").write_text("", encoding="utf-8")
        else:
            (out_dir / "latest.stdout.log").write_text(stdout, encoding="utf-8")
            (out_dir / "latest.stderr.log").write_text(stderr, encoding="utf-8")
        return out_dir / "latest.json"

    def latest_run(self, args) -> int:
        runs_root = self.repo_root / ".build" / "anigma-pipeline" / "runs" / args.task
        if not runs_root.exists():
            print("missing pipeline run", file=sys.stderr)
            return 2
        candidates = [p for p in runs_root.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
        if not candidates:
            print("missing pipeline run", file=sys.stderr)
            return 2
        preferred = []
        if args.profile:
            for p in candidates:
                try:
                    manifest = __import__("json").loads((p / "manifest.json").read_text(encoding="utf-8"))
                except Exception:
                    continue
                if manifest.get("profile") == args.profile:
                    preferred.append(p)
        chosen = max(preferred or candidates, key=lambda p: p.stat().st_mtime)
        value = str(chosen.relative_to(self.repo_root))
        if self.output_mode in {"json", "jsonl", "agent"}:
            from rig_tools.result import write_latest_result, RigResult
            payload = RigResult(
                command_group="pipeline",
                command=f"rig pipeline latest-run --task {args.task}" + (f" --profile {args.profile}" if args.profile else ""),
                status="passed",
                exit_code=0,
                run_id=chosen.name,
                task=args.task,
                summary={"result": value},
                artifacts=[{"path": value, "type": "run_directory"}],
            ).to_dict()
            write_latest_result(self.repo_root, payload)
            if self.output_mode == "json":
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print(json.dumps(payload, sort_keys=True))
        else:
            print(value)
        return 0


def build_parser(helpers: RigHelpers) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rig.py", description="Repo-local Anigma development harness.")
    parser.add_argument("--quiet", action="store_true", help="Suppress delegated command echo.")
    parser.add_argument("--json", action="store_true", help="Print only the final JSON result.")
    parser.add_argument("--jsonl", action="store_true", help="Stream JSON Lines events.")
    parser.add_argument("--agent", action="store_true", help="Agent mode: JSONL plus stable artifacts.")
    parser.add_argument("--notify", action="store_true", help="Enable finish notifications.")
    parser.add_argument("--notify-on", default="never", choices=["finish", "failure", "known-blocked", "blocked", "ready", "never"], help="Notify on selected final result states.")
    parser.add_argument("--notify-backend", choices=["osascript", "terminal-notifier", "none"], help="Notification backend.")
    subparsers = parser.add_subparsers(dest="group", required=True)
    commands_atlas.register(subparsers, helpers)
    commands_affected.register(subparsers, helpers)
    commands_audit.register(subparsers, helpers)
    commands_bench.register(subparsers, helpers)
    commands_brief.register(subparsers, helpers)
    commands_board.register(subparsers, helpers)
    commands_bootstrap.register(subparsers, helpers)
    commands_diff.register(subparsers, helpers)
    commands_graph.register(subparsers, helpers)
    commands_intent.register(subparsers, helpers)
    commands_docs.register(subparsers, helpers)
    from . import commands_os, commands_state, commands_projections, commands_anigma, commands_settings, commands_gc, commands_scheduler
    commands_os.register(subparsers, helpers)
    commands_state.register(subparsers, helpers)
    commands_projections.register(subparsers, helpers)
    commands_anigma.register(subparsers, helpers)
    commands_settings.register(subparsers, helpers)
    commands_gc.register(subparsers, helpers)
    commands_scheduler.register(subparsers, helpers)
    commands_monitor.register(subparsers, helpers)
    commands_product.register(subparsers, helpers)
    commands_vault.register(subparsers, helpers)
    commands_textual.setup(subparsers, helpers)
    commands_bundle.register(subparsers, helpers)
    commands_context.register(subparsers, helpers)
    commands_action.register(subparsers, helpers)
    commands_policy.register(subparsers, helpers)
    commands_prompt.register(subparsers, helpers)
    commands_db.register(subparsers, helpers)
    commands_queue.register(subparsers, helpers)
    commands_workspace.register(subparsers, helpers)
    commands_patch.register(subparsers, helpers)
    commands_llm.register(subparsers, helpers)
    commands_embeddings.register(subparsers, helpers)
    commands_agent.register(subparsers, helpers)
    commands_models.register(subparsers, helpers)
    commands_loop.register(subparsers, helpers)
    commands_tui.register(subparsers, helpers)
    commands_notify.register(subparsers, helpers)
    commands_project.register(subparsers, helpers)
    commands_schema.register(subparsers, helpers)
    commands_structural.register(subparsers, helpers)
    commands_pipeline.register(subparsers, helpers)
    commands_swarm.register(subparsers, helpers)
    commands_swift.register(subparsers, helpers)
    commands_git.register(subparsers, helpers)
    commands_doctor.register(subparsers, helpers)
    commands_release.register(subparsers, helpers)
    commands_window.register(subparsers, helpers)
    commands_bias.register(subparsers, helpers)
    return parser


def main(argv: list[str] | None = None) -> int:
    helpers = RigHelpers(repo_root=repo_root())
    parser = build_parser(helpers)
    args = parser.parse_args(argv)
    if args.json and args.jsonl:
        parser.error("--json and --jsonl are mutually exclusive")
    if args.agent:
        helpers.output_mode = "agent"
    elif args.jsonl:
        helpers.output_mode = "jsonl"
    elif args.json:
        helpers.output_mode = "json"
    if args.notify:
        helpers.notify_trigger = "finish" if args.notify_on == "never" else args.notify_on
    elif args.notify_on != "never":
        helpers.notify_trigger = args.notify_on
    if args.notify_backend:
        helpers.notify_backend = args.notify_backend
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

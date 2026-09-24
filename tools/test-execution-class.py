#!/usr/bin/env python3
"""Детерминированные проверки запускателя классов исполнения."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# Русские сообщения не должны падать на консоли с однобайтовой кодировкой.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".apm/skills/ai-setup-subagents/scripts/run-execution-class"
MODEL_EVALUATOR = ROOT / ".apm/skills/ai-setup-subagents/scripts/evaluate-model-selection.py"
MODEL_EVALUATOR_SAMPLE = ROOT / ".apm/skills/ai-setup-subagents/assets/model-selection-input.sample.json"
CLAUDE_ROLE = ROOT / ".apm/skills/ai-setup-subagents/scripts/adapters/claude-role"
CLAUDE_INSTALLER = ROOT / ".apm/skills/ai-setup-subagents/scripts/install-claude-tools"
LOADER = importlib.machinery.SourceFileLoader("claude_role", str(CLAUDE_ROLE))
SPEC = importlib.util.spec_from_loader("claude_role", LOADER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Не удалось загрузить адаптер Claude")
CLAUDE_ROLE_MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(CLAUDE_ROLE_MODULE)


def write_fixture(directory: Path, actual_model: str, *, evidence=True, journal=True,
                  wrong_reference=False, returncode=0, response=None, turn_completed=True,
                  sleep_seconds=0) -> Path:
    if response is None:
        response = {"status": "ready", "evidence": ["fixture"]}
    adapter = directory / "adapter.py"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import sys\n"
        "import os\n"
        "import time\n"
        "from pathlib import Path\n"
        "request = json.loads(input())\n"
        "assert request['contract']['writes'] is False\n"
        "assert request['inputs']\n"
        + (f"Path(os.environ['CODEX_ROLE_LOG']).write_text(json.dumps({{'message': {{'model': '{actual_model}'}}}}) + '\\n')\n" if journal else "")
        + f"header = {{'model': '{actual_model}', 'usage': {{'input_tokens': 1}}, 'turn_completed': {turn_completed!r}}}\n"
        + (f"header['model_evidence'] = {{'source': 'journal', 'line': {2 if wrong_reference else 1}, 'field': ['message', 'model']}}\n" if evidence else "")
        + f"time.sleep({sleep_seconds!r})\n"
        + "print(json.dumps(header), flush=True)\n"
        + ("print('', flush=True)\n" if response == "" else f"print(json.dumps({response!r}), flush=True)\n"),
        encoding="utf-8",
    )
    if returncode:
        adapter.write_text(adapter.read_text(encoding="utf-8") + f"raise SystemExit({returncode})\n", encoding="utf-8")
    adapter.chmod(0o755)
    return adapter


def write_config(directory: Path, adapter: Path, prefix: str = "") -> Path:
    config = directory / "subagents.local.toml"
    prefix_line = f'actual_model_prefix = "{prefix}"\n' if prefix else ""
    config.write_text(
        textwrap.dedent(
            f"""
            [execution_classes.cheap_readonly_research]
            writes = false
            result = "status, evidence"

            [targets.claude.execution_classes.cheap_readonly_research]
            model = "haiku"
            effort = "low"
            sandbox = "read-only"
            adapter = ["{sys.executable}", "{adapter}"]
            {prefix_line}

            [roles.reviewer]
            model = "claude-haiku-4-5"
            effort = "low"
            sandbox = "read-only"
            adapter = "{adapter}"
            [roles.reviewer.contract]
            writes = false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config


def run(
    config: Path, out: Path, input_file: Path, obligation: str | None = None
) -> subprocess.CompletedProcess[str]:
    arguments = [
        str(RUNNER),
        "cheap_readonly_research",
        "--target",
        "claude",
        "--config",
        str(config),
        "--out",
        str(out),
        "--input",
        str(input_file),
    ]
    if obligation is not None:
        arguments.extend(["--obligation", obligation])
    return subprocess.run(
        arguments,
        input="Найди один факт.",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        input_file = directory / "input.md"
        input_file.write_text("факт\n", encoding="utf-8")

        matching = write_fixture(directory, "claude-haiku-4-5")
        config = write_config(directory, matching, "claude-haiku-")
        success = run(config, directory / "success", input_file, "security-review")
        assert success.returncode == 0, success.stderr
        record = json.loads(success.stdout)
        assert record["assigned_model"] == "haiku"
        assert record["actual_model"] == "claude-haiku-4-5"
        assert record["model_matches"]
        assert record["client_model_matches"]
        assert record["model_status"] == "confirmed"
        assert record["model_evidence"]["line"] == 1
        assert len(record["model_evidence"]["sha256"]) == 64
        assert record["obligation_id"] == "security-review"
        assert record["run_id"]
        assert record["command"]["adapter_executable"] == Path(sys.executable).name
        assert record["command"]["adapter_argument_count"] == 2
        assert record["environment"].keys() == {
            "codex_home_configured", "nested_codex_context"
        }
        assert record["result_available"]
        assert record["returncode"] == 0
        assert record["result_path"] == record["final"]
        assert record["result_nonempty"] and record["result_usable"]
        assert json.loads(Path(record["result_path"]).read_text(encoding="utf-8")) == {
            "status": "ready", "evidence": ["fixture"]
        }
        assert json.loads(Path(record["transport_header_path"]).read_text(encoding="utf-8"))["model"] == "claude-haiku-4-5"
        for key in ("final", "stderr", "journal", "transport_path", "transport_header_path"):
            assert Path(record[key]).is_file()

        empty = write_fixture(directory, "claude-haiku-4-5", response="")
        empty_config = write_config(directory, empty, "claude-haiku-")
        empty_result = run(empty_config, directory / "empty", input_file, "security-review")
        assert empty_result.returncode == 4
        empty_record = json.loads(empty_result.stderr)
        assert not empty_record["result_nonempty"]
        assert not empty_record["result_usable"]
        assert empty_record["stop_reason"] == "empty_model_result"

        interrupted = write_fixture(directory, "claude-haiku-4-5", turn_completed=False)
        interrupted_config = write_config(directory, interrupted, "claude-haiku-")
        interrupted_result = run(interrupted_config, directory / "interrupted", input_file, "security-review")
        assert interrupted_result.returncode == 4
        assert json.loads(interrupted_result.stderr)["stop_reason"] == "model_turn_not_completed"

        blank = subprocess.run(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude", "--config", str(config), "--out", str(directory / "blank")],
            input=" \n\t", text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
        )
        assert blank.returncode == 2 and "задание для класса исполнения пусто" in blank.stderr
        assert not (directory / "blank").exists()

        mismatched = write_fixture(directory, "claude-opus-4-8")
        failed_config = write_config(directory, mismatched, "claude-haiku-")
        failed = run(failed_config, directory / "failed", input_file, "security-review")
        assert failed.returncode == 3
        failed_record = json.loads(failed.stderr)
        assert failed_record["obligation_id"] == "security-review"
        assert not failed_record["model_matches"]

        matching = write_fixture(directory, "claude-haiku-4-5")
        config = write_config(directory, matching, "claude-haiku-")
        legacy = run(config, directory / "legacy", input_file)
        assert legacy.returncode == 0, legacy.stderr
        assert "obligation_id" not in json.loads(legacy.stdout)

        for name, options in (
            ("missing-evidence", {"evidence": False}),
            ("missing-journal", {"journal": False}),
            ("bad-reference", {"wrong_reference": True}),
        ):
            adapter = write_fixture(directory, "claude-haiku-4-5", **options)
            config = write_config(directory, adapter, "claude-haiku-")
            unknown = run(config, directory / name, input_file, "security-review")
            assert unknown.returncode == 3, unknown.stdout
            unknown_record = json.loads(unknown.stderr)
            assert unknown_record["model_status"] == "unconfirmed"
            assert unknown_record["actual_model"] is None
            assert unknown_record["model_matches"] is None
            assert unknown_record["result_available"]

        execution_failed = write_fixture(directory, "claude-haiku-4-5", returncode=7)
        failed_config = write_config(directory, execution_failed, "claude-haiku-")
        failed_process = run(failed_config, directory / "execution-failed", input_file, "security-review")
        assert failed_process.returncode == 2
        assert json.loads(failed_process.stderr)["returncode"] == 7

        slow = write_fixture(directory, "claude-haiku-4-5", sleep_seconds=3)
        slow_config = write_config(directory, slow, "claude-haiku-")
        timeout = subprocess.run(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude",
             "--config", str(slow_config), "--out", str(directory / "timeout"),
             "--input", str(input_file), "--timeout-seconds", "0.1"],
            input="Найди один факт.", text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False,
        )
        assert timeout.returncode == 2
        timeout_record = json.loads(timeout.stderr)
        assert timeout_record["status"] == "timed_out"
        assert timeout_record["stop_reason"] == "timeout"
        assert timeout_record["termination_confirmed"]
        assert Path(timeout_record["journal"]).read_text(encoding="utf-8")
        assert Path(timeout_record["transport_path"]).is_file()
        assert Path(timeout_record["stderr"]).is_file()

        interrupted_out = directory / "interrupted-signal"
        interrupted_process = subprocess.Popen(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude",
             "--config", str(slow_config), "--out", str(interrupted_out),
             "--input", str(input_file)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        assert interrupted_process.stdin is not None
        interrupted_process.stdin.write("Найди один факт.")
        interrupted_process.stdin.close()
        record_paths: list[Path] = []
        for _ in range(30):
            record_paths = list(interrupted_out.glob("*.json"))
            if record_paths:
                break
            time.sleep(0.02)
        assert len(record_paths) == 1
        started_record = json.loads(record_paths[0].read_text(encoding="utf-8"))
        assert started_record["status"] == "started"
        assert not started_record["termination_confirmed"]
        interrupted_process.send_signal(signal.SIGTERM)
        interrupted_process.wait(timeout=5)
        signal_record = json.loads(record_paths[0].read_text(encoding="utf-8"))
        assert signal_record["status"] == "interrupted"
        assert signal_record["signal"] == "SIGTERM"
        assert not signal_record["termination_confirmed"]

        killed = write_fixture(directory, "claude-haiku-4-5", sleep_seconds=0.5)
        killed_config = write_config(directory, killed, "claude-haiku-")
        killed_out = directory / "killed"
        killed_process = subprocess.Popen(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude",
             "--config", str(killed_config), "--out", str(killed_out),
             "--input", str(input_file)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        assert killed_process.stdin is not None
        killed_process.stdin.write("Найди один факт.")
        killed_process.stdin.close()
        for _ in range(30):
            if list(killed_out.glob("*.json")):
                break
            time.sleep(0.02)
        killed_records = list(killed_out.glob("*.json"))
        assert len(killed_records) == 1
        killed_process.kill()
        killed_process.wait(timeout=5)
        killed_record = json.loads(killed_records[0].read_text(encoding="utf-8"))
        assert killed_record["status"] == "started"
        assert not killed_record["termination_confirmed"]
        time.sleep(0.6)

        for evidence in (False, True):
            adapter = write_fixture(directory, "claude-haiku-4-5", evidence=evidence)
            config = write_config(directory, adapter)
            role = subprocess.run(
                [str(RUNNER.with_name("run-subagent-role")), "reviewer",
                 "--config", str(config), "--input", str(input_file),
                 "--out", str(directory / f"role-{evidence}")],
                input="Проверь факт.", text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            assert role.returncode == (0 if evidence else 1), role.stderr
            role_record = json.loads(role.stdout if evidence else role.stderr)
            assert role_record["model_status"] == ("confirmed" if evidence else "unconfirmed")

        installed_root = directory / "installed-project"
        installed = subprocess.run(
            [str(CLAUDE_INSTALLER), str(installed_root)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert installed.returncode == 0, installed.stderr
        assert "installed=" in installed.stdout
        installed_runner = installed_root / "tools/run-execution-class"
        installed_evaluator = installed_root / "tools/evaluate-model-selection.py"
        installed_sample = installed_root / "tools/model-selection-input.sample.json"
        installed_adapter = installed_root / "tools/adapters/claude-role"
        assert installed_runner.read_bytes() == RUNNER.read_bytes()
        assert (installed_root / "tools/run-subagent-role").read_bytes() == (
            ROOT / ".apm/skills/ai-setup-subagents/scripts/run-subagent-role"
        ).read_bytes()
        assert installed_evaluator.read_bytes() == MODEL_EVALUATOR.read_bytes()
        assert installed_sample.read_bytes() == MODEL_EVALUATOR_SAMPLE.read_bytes()
        assert installed_adapter.read_bytes() == CLAUDE_ROLE.read_bytes()
        assert (installed_root / "tools/lib/model_evidence.py").read_bytes() == (
            RUNNER.parent / "lib/model_evidence.py"
        ).read_bytes()

    stream = "\n".join(
        [
            json.dumps({"type": "system", "model": "claude-haiku-4-5"}),
            json.dumps(
                {
                    "type": "system",
                    "subtype": "informational",
                    "content": "Model \"haiku\" is restricted.",
                }
            ),
            json.dumps(
                {"type": "assistant", "message": {"model": "claude-opus-4-8"}}
            ),
            json.dumps(
                {
                    "type": "result",
                    "result": "готово",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ),
        ]
    )
    model, usage, result, notice = CLAUDE_ROLE_MODULE.response_details(stream)
    assert model == "claude-opus-4-8"
    assert usage == {"input_tokens": 1, "output_tokens": 1}
    assert result == "готово"
    assert notice == "Model \"haiku\" is restricted."

    actual, reference = CLAUDE_ROLE_MODULE.model_evidence(stream)
    assert actual == model and reference["line"] == 3
    assert CLAUDE_ROLE_MODULE.model_evidence('{"type":"system","model":"assigned"}') == (None, None)
    conflict = stream + '\n' + json.dumps({"type": "assistant", "message": {"model": "other"}})
    assert CLAUDE_ROLE_MODULE.model_evidence(conflict) == (None, None)

    # Адаптер сохраняет события и stderr Codex до завершения процесса.
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        bin_directory = directory / "bin"
        bin_directory.mkdir()
        fake_codex = bin_directory / "codex"
        fake_codex.write_text(
            f"#!{sys.executable}\n"
            "import json, sys, time\n"
            "from pathlib import Path\n"
            "arguments = sys.argv\n"
            "final = Path(arguments[arguments.index('--output-last-message') + 1])\n"
            "print(json.dumps({'type': 'thread.started', 'thread_id': 'fixture'}), flush=True)\n"
            "print('fixture stderr', file=sys.stderr, flush=True)\n"
            "time.sleep(0.5)\n"
            "final.write_text('готово', encoding='utf-8')\n"
            "print(json.dumps({'type': 'turn.completed', 'usage': {}}), flush=True)\n",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        journal = directory / "events.jsonl"
        codex_stderr = directory / "codex.stderr.txt"
        environment = {
            **os.environ,
            "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}",
            "CODEX_ROLE_LOG": str(journal),
            "CODEX_ROLE_STDERR": str(codex_stderr),
        }
        adapter = subprocess.Popen(
            [str(RUNNER.parent / "adapters/codex-role"), "requested-model", "low", "read-only"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=environment,
        )
        assert adapter.stdin is not None
        adapter.stdin.write("{}")
        adapter.stdin.close()
        for _ in range(30):
            if journal.is_file() and "thread.started" in journal.read_text(encoding="utf-8"):
                break
            time.sleep(0.02)
        assert "thread.started" in journal.read_text(encoding="utf-8")
        assert "fixture stderr" in codex_stderr.read_text(encoding="utf-8")
        assert adapter.wait(timeout=5) == 0

    print("Проверка классов исполнения пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

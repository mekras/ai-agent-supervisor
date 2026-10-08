#!/usr/bin/env python3
"""Детерминированные проверки запускателя классов исполнения."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import errno
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
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
RUNNER_LOADER = importlib.machinery.SourceFileLoader("execution_runner", str(RUNNER))
RUNNER_SPEC = importlib.util.spec_from_loader("execution_runner", RUNNER_LOADER)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("Не удалось загрузить запускатель классов исполнения")
RUNNER_MODULE = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_LOADER.exec_module(RUNNER_MODULE)


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


def write_process_group_fixture(
    directory: Path, mode: str
) -> tuple[Path, Path, Path]:
    child = directory / f"{mode}-child.py"
    child_pid = directory / f"{mode}-child.pid"
    adapter_pid = directory / f"{mode}-adapter.pid"
    child.write_text(
        f"#!{sys.executable}\n"
        "import os\n"
        "import signal\n"
        "import time\n"
        "from pathlib import Path\n"
        f"pid_path = Path({str(child_pid)!r})\n"
        + (
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            if mode != "success"
            else ""
        )
        + "temporary_pid = pid_path.with_suffix('.tmp')\n"
        + "temporary_pid.write_text(str(os.getpid()), encoding='utf-8')\n"
        + "temporary_pid.replace(pid_path)\n"
        + "while True:\n"
        + (
            "    time.sleep(0.05)\n"
            if mode != "success"
            else "    time.sleep(0.05)\n    break\n"
        ),
        encoding="utf-8",
    )
    child.chmod(0o755)

    adapter = directory / f"{mode}-adapter.py"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import os\n"
        "import signal\n"
        "import subprocess\n"
        "import time\n"
        "from pathlib import Path\n"
        f"adapter_pid_path = Path({str(adapter_pid)!r})\n"
        "def exit_on_term(_signum, _frame):\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGTERM, exit_on_term)\n"
        "temporary_adapter_pid = adapter_pid_path.with_suffix('.tmp')\n"
        "temporary_adapter_pid.write_text(str(os.getpid()), encoding='utf-8')\n"
        "temporary_adapter_pid.replace(adapter_pid_path)\n"
        + (
            "while True:\n    time.sleep(0.05)\n"
            if mode == "no-stdin"
            else "request = json.loads(__import__('sys').stdin.read())\n"
        )
        + "Path(os.environ['CODEX_ROLE_LOG']).write_text(\n"
        "    json.dumps({'message': {'model': 'claude-haiku-4-5'}}) + '\\n',\n"
        "    encoding='utf-8',\n"
        ")\n"
        + (
            f"child = subprocess.Popen([{sys.executable!r}, {str(child)!r}], start_new_session=True)\n"
            if mode == "external-holder"
            else f"child = subprocess.Popen([{sys.executable!r}, {str(child)!r}])\n"
            if mode != "no-stdin"
            else ""
        )
        + (
            f"ready_path = Path({str(child_pid)!r})\n"
            "ready_deadline = time.monotonic() + 3\n"
            "while not ready_path.is_file() and time.monotonic() < ready_deadline:\n"
            "    time.sleep(0.01)\n"
            "assert ready_path.is_file(), 'child did not become ready'\n"
            if mode == "leader-exits"
            else ""
        )
        + (
            "child.wait(timeout=5)\n"
            "print(json.dumps({'model': 'claude-haiku-4-5', 'turn_completed': True, "
            "'model_evidence': {'source': 'journal', 'line': 1, "
            "'field': ['message', 'model']}}), flush=True)\n"
            "print(json.dumps({'status': 'ready'}), flush=True)\n"
            if mode == "success"
            else (
                "print(json.dumps({'model': 'claude-haiku-4-5', 'turn_completed': True, "
                "'model_evidence': {'source': 'journal', 'line': 1, "
                "'field': ['message', 'model']}}), flush=True)\n"
                "print(json.dumps({'status': 'ready'}), flush=True)\n"
                if mode == "leader-exits"
                else "while True:\n    time.sleep(0.05)\n"
            )
        ),
        encoding="utf-8",
    )
    adapter.chmod(0o755)
    return adapter, child_pid, adapter_pid


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        fields = stat.read_text(encoding="utf-8").rsplit(")", 1)
        if len(fields) == 2 and fields[1].lstrip().startswith("Z"):
            return False
    return True


def wait_for_process_stop(pid: int, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while process_is_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not process_is_alive(pid), f"потомок {pid} продолжает работать"


def read_ready_pid(path: Path, timeout: float = 3.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
        time.sleep(0.01)
    raise AssertionError(f"не получен готовый PID: {path}")


def cleanup_pid(pid: int | None) -> None:
    if pid is None or not process_is_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    wait_for_process_stop(pid)


def run_process_group_case(
    directory: Path,
    mode: str,
    *,
    signal_to_runner: signal.Signals | None = None,
    timeout: str | None = None,
    repeat_signal: int = 1,
    expect_child_stop: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object], int, float]:
    adapter, child_pid_path, adapter_pid_path = write_process_group_fixture(directory, mode)
    config = write_config(directory, adapter, "claude-haiku-")
    output = directory / f"group-{mode}"
    arguments = [
        str(RUNNER),
        "cheap_readonly_research",
        "--target",
        "claude",
        "--config",
        str(config),
        "--out",
        str(output),
        "--input",
        str(directory / "input.md"),
    ]
    if timeout is not None:
        arguments.extend(["--timeout-seconds", timeout])
    process = subprocess.Popen(
        arguments,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    child_pid: int | None = None
    adapter_pid: int | None = None
    started = time.monotonic()
    try:
        assert process.stdin is not None
        process.stdin.write("Проверь группу процессов.")
        process.stdin.close()
        # communicate в Python 3.12 иначе пытается сбросить закрытый поток.
        process.stdin = None
        adapter_pid = read_ready_pid(adapter_pid_path)
        child_pid = read_ready_pid(child_pid_path)
        if signal_to_runner is not None:
            for _ in range(repeat_signal):
                process.send_signal(signal_to_runner)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait(timeout=3)
            raise AssertionError("сценарий запускателя превысил аварийный предел") from error
        completed = subprocess.CompletedProcess(
            arguments, process.returncode, stdout, stderr
        )
        elapsed = time.monotonic() - started
        records = [
            path
            for path in output.glob("*.json")
            if not path.name.endswith(".transport-header.json")
        ]
        assert len(records) == 1, (
            completed.returncode,
            completed.stdout,
            completed.stderr,
            list(output.glob("*")),
        )
        record = json.loads(records[0].read_text(encoding="utf-8"))
        assert child_pid is not None
        if expect_child_stop:
            wait_for_process_stop(child_pid)
        else:
            assert process_is_alive(child_pid), "внешний процесс исчез до проверки очистки"
        return completed, record, child_pid, elapsed
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        cleanup_pid(adapter_pid)
        cleanup_pid(child_pid)


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


def write_hermes_codex_route_fixture(directory: Path) -> Path:
    """Создать фиктивный исполнитель, сохраняющий фактические аргументы."""

    adapter = directory / "codex-route-adapter.py"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "model, effort, sandbox = sys.argv[1:4]\n"
        "request = json.loads(sys.stdin.read())\n"
        "assert request['contract']['writes'] is False\n"
        "assert request['role_assignment'] == {\n"
        "    'role': 'child_executor',\n"
        "    'route_decided_by': 'parent',\n"
        "    'task_scope': 'provided_subtask_only',\n"
        "    'delegation_permission': 'none',\n"
        "}\n"
        "Path(os.environ['CODEX_ROLE_LOG']).write_text(\n"
        "    json.dumps({'message': {'model': model, 'effort': effort, 'sandbox': sandbox}}) + '\\n',\n"
        "    encoding='utf-8',\n"
        ")\n"
        "header = {\n"
        "    'model': model,\n"
        "    'effort': effort,\n"
        "    'turn_completed': True,\n"
        "    'model_evidence': {'source': 'journal', 'line': 1, 'field': ['message', 'model']},\n"
        "    'effort_evidence': {'source': 'journal', 'line': 1, 'field': ['message', 'effort']},\n"
        "}\n"
        "print(json.dumps(header), flush=True)\n"
        "print(json.dumps({'status': 'accepted', 'adapter_arguments': {\n"
        "    'model': model, 'effort': effort, 'sandbox': sandbox\n"
        "}}), flush=True)\n",
        encoding="utf-8",
    )
    adapter.chmod(0o755)
    return adapter


def write_hermes_codex_route_config(directory: Path, adapter: Path) -> Path:
    """Записать схему с target исполнителя Codex и двумя классами."""

    config = directory / "hermes-codex-subagents.local.toml"
    adapter_command = f'["{sys.executable}", "{adapter}"]'
    config.write_text(
        textwrap.dedent(
            f"""
            [policy_runtime]
            launcher = "tools/run-execution-class"
            target = "codex"
            result_acceptance = "родитель принимает результат"

            [execution_classes.cheap_readonly_research]
            writes = false
            result = "status, adapter_arguments"

            [execution_classes.bounded_readonly_review]
            writes = false
            result = "status, adapter_arguments"

            [targets.codex.execution_classes.cheap_readonly_research]
            model = "executor-model-a"
            effort = "low"
            sandbox = "read-only"
            adapter = {adapter_command}

            [targets.codex.execution_classes.bounded_readonly_review]
            model = "executor-model-b"
            effort = "high"
            sandbox = "read-only"
            adapter = {adapter_command}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config


def run_hermes_codex_route_case(directory: Path, input_file: Path) -> None:
    """Проверить два назначения Codex-классов в контексте родителя Hermes.

    Схема хранит target исполнителя и не хранит родителя. Транспортный пакет
    отдельно назначает роль дочернего исполнителя и проверяет её по реальным
    данным фиктивного адаптера и принятому результату.
    """

    adapter = write_hermes_codex_route_fixture(directory)
    config = write_hermes_codex_route_config(directory, adapter)
    expected = {
        "cheap_readonly_research": ("executor-model-a", "low", "read-only"),
        "bounded_readonly_review": ("executor-model-b", "high", "read-only"),
    }
    for execution_class, parameters in expected.items():
        output = directory / f"hermes-codex-{execution_class}"
        result = subprocess.run(
            [
                str(RUNNER),
                execution_class,
                "--target",
                "codex",
                "--config",
                str(config),
                "--out",
                str(output),
                "--input",
                str(input_file),
            ],
            input=f"Проверь класс {execution_class}.",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)
        model, effort, sandbox = parameters
        assert record["target"] == "codex"
        assert record["assigned_model"] == model
        assert record["assigned_effort"] == effort
        assert record["actual_model"] == model
        assert record["actual_effort"] == effort
        assert record["model_matches"] is True
        assert record["effort_matches"] is True
        assert record["client_route_status"] == "confirmed"
        accepted = json.loads(Path(record["result_path"]).read_text(encoding="utf-8"))
        assert accepted == {
            "status": "accepted",
            "adapter_arguments": {
                "model": model,
                "effort": effort,
                "sandbox": sandbox,
            },
        }


def test_codex_role_receives_child_assignment(directory: Path) -> None:
    """Проверить инструктивную границу роли адаптера Codex."""

    bin_directory = directory / "codex-role-bin"
    bin_directory.mkdir()
    prompt_path = directory / "codex-role-prompt.txt"
    fake_codex = bin_directory / "codex"
    fake_codex.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        f"prompt = sys.stdin.read()\nPath({str(prompt_path)!r}).write_text(prompt, encoding='utf-8')\n"
        "arguments = sys.argv\n"
        "final = Path(arguments[arguments.index('--output-last-message') + 1])\n"
        "final.write_text('готово', encoding='utf-8')\n"
        "print(json.dumps({'type': 'thread.started', 'thread_id': 'fixture'}), flush=True)\n"
        "print(json.dumps({'type': 'turn.completed', 'usage': {}}), flush=True)\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}",
        "CODEX_ROLE_LOG": str(directory / "codex-role-events.jsonl"),
        "CODEX_ROLE_STDERR": str(directory / "codex-role.stderr.txt"),
    }
    payload = {
        "task": "Найди один факт.",
        "role_assignment": {
            "role": "child_executor",
            "route_decided_by": "parent",
            "task_scope": "provided_subtask_only",
            "delegation_permission": "none",
        },
    }
    result = subprocess.run(
        [str(RUNNER.parent / "adapters/codex-role"), "requested-model", "low", "read-only"],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "ROLE_ASSIGNMENT: child_executor" in prompt
    assert "REDELEGATION: forbidden_without_explicit_permission" in prompt
    assert "не запускайте этот класс повторно" in prompt
    assert '"delegation_permission": "none"' in prompt


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


def test_parent_acceptance() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        final = root / "result.txt"
        final.write_text("Проверенный результат", encoding="utf-8")
        path = root / "run.json"
        original = {"run_id": "current-run", "status": "completed", "returncode": 0,
                    "stop_reason": None, "result_usable": True,
                    "result_path": str(final), "client_route_status": "confirmed",
                    "model_matches": True, "effort_matches": True}
        def reset(**values):
            path.write_text(json.dumps({**original, **values}), encoding="utf-8")
        def invoke(mode, *extra, expected=0, run_id="current-run"):
            result = subprocess.run([sys.executable, "-B", str(RUNNER), mode,
                str(path), "--run-id", run_id, *extra], capture_output=True, text=True)
            assert result.returncode == expected, (result.stdout, result.stderr)
            return result
        fields = ["--status", "accepted", "--criterion", "Все значения сверены",
                  "--evidence", "source.md:1-5", "--quality", "passed",
                  "--summary", "Расхождений нет", "--scope", "Предметная сверка"]
        reset()
        before = path.read_bytes()
        invoke("--check-acceptance", expected=2)
        invoke("--record-acceptance", *fields, run_id="previous-run", expected=2)
        invoke("--record-acceptance", *fields[:-2], expected=2)
        invoke("--record-acceptance", *fields, "--criterion", " ", expected=2)
        assert path.read_bytes() == before
        invoke("--record-acceptance", *fields)
        record = json.loads(path.read_text())
        assert record["acceptance"]["run_id"] == "current-run"
        assert record["quality_assessment"]["status"] == "passed"
        assert {k: v for k, v in record.items() if k not in
                {"acceptance", "quality_assessment"}} == original
        invoke("--check-acceptance")
        accepted = path.read_bytes()
        invoke("--record-acceptance", *fields, expected=2)
        assert path.read_bytes() == accepted
        final.write_text("Подменённый результат", encoding="utf-8")
        invoke("--check-acceptance", expected=2)
        final.write_text("Проверенный результат", encoding="utf-8")
        record["returncode"] = 9
        path.write_text(json.dumps(record))
        invoke("--check-acceptance", expected=2)
        for values in ({"status": "started"}, {"status": "failed", "returncode": 1},
                       {"result_usable": False}, {"client_route_status": "mismatch"},
                       {"effort_matches": False}, {"client_route_status": "conflict"},
                       {"client_route_status": "unconfirmed"}):
            reset(**values)
            before = path.read_bytes()
            invoke("--record-acceptance", *fields, expected=2)
            assert path.read_bytes() == before
        reset(client_route_status="unconfirmed")
        invoke("--record-acceptance", *fields, "--unconfirmed-reason",
               "Локальная политика разрешает содержательную приёмку")
        invoke("--check-acceptance")
        reset(status="failed", returncode=1)
        rejected = fields.copy()
        rejected[1], rejected[7] = "rejected", "failed"
        invoke("--record-acceptance", *rejected)
        invoke("--check-acceptance", expected=1)
        reset()
        lock = path.with_name(path.name + ".acceptance.lock")
        lock.write_text("другой проверяющий")
        invoke("--record-acceptance", *fields, expected=2)
        assert lock.read_text() == "другой проверяющий"
        lock.unlink()
        assert not list(root.glob("*.tmp"))
        assert not list(root.glob("*.lock"))
        path.write_text("[]")
        invoke("--check-acceptance", expected=2)


def main() -> int:
    test_parent_acceptance()
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        input_file = directory / "input.md"
        input_file.write_text("факт\n", encoding="utf-8")

        run_hermes_codex_route_case(directory, input_file)
        test_codex_role_receives_child_assignment(directory)

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
        assert json.loads(Path(record["record_path"]).read_text(encoding="utf-8"))["run_id"] == record["run_id"]
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

        # Политика задаёт каталог, явный --out переопределяет его.
        configured_out = directory / "configured-records"
        configured_text = config.read_text() + '\n[policy_runtime]\nrun_records_dir = ' + json.dumps(str(configured_out)) + '\n'
        config.write_text(configured_text)
        via_policy = subprocess.run(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude", "--config", str(config), "--input", str(input_file)],
            input="Проверь факт.", text=True, capture_output=True,
        )
        assert via_policy.returncode == 0, via_policy.stderr
        assert Path(json.loads(via_policy.stdout)["record_path"]).parent == configured_out
        explicit = run(config, directory / "explicit-records", input_file, "review")
        assert explicit.returncode == 0, explicit.stderr
        assert Path(json.loads(explicit.stdout)["record_path"]).parent == directory / "explicit-records"
        blocked_out = directory / "not-a-directory"
        blocked_out.write_text("Существующий файл, не каталог")
        config.write_text(configured_text.replace(str(configured_out), str(blocked_out)))
        blocked = subprocess.run(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude", "--config", str(config), "--input", str(input_file)],
            input="Проверь факт.", text=True, capture_output=True,
        )
        assert blocked.returncode == 2 and "Модель не запускалась" in blocked.stderr
        config.write_text(configured_text)

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
        assert timeout_record["returncode"] is not None
        # Тайм-аут может наступить до первого сообщения адаптера.
        assert Path(timeout_record["journal"]).is_file()
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
        assert signal_record["termination_confirmed"]

        no_stdin_adapter, _no_stdin_child, no_stdin_adapter_pid = (
            write_process_group_fixture(directory, "no-stdin")
        )
        no_stdin_config = write_config(directory, no_stdin_adapter, "claude-haiku-")
        no_stdin_out = directory / "no-stdin"
        no_stdin_process = subprocess.Popen(
            [str(RUNNER), "cheap_readonly_research", "--target", "claude",
             "--config", str(no_stdin_config), "--out", str(no_stdin_out),
             "--input", str(input_file), "--timeout-seconds", "0.2"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        try:
            no_stdin_stdout, no_stdin_stderr = no_stdin_process.communicate(
                input="x" * 2_000_000, timeout=4
            )
        except subprocess.TimeoutExpired as error:
            no_stdin_process.kill()
            no_stdin_process.wait(timeout=3)
            raise AssertionError("большое задание заблокировало запускатель") from error
        finally:
            cleanup_pid(
                int(no_stdin_adapter_pid.read_text(encoding="utf-8"))
                if no_stdin_adapter_pid.is_file()
                else None
            )
        assert no_stdin_process.returncode == 2, no_stdin_stderr
        no_stdin_records = list(no_stdin_out.glob("*.json"))
        assert len(no_stdin_records) == 1
        no_stdin_record = json.loads(no_stdin_records[0].read_text(encoding="utf-8"))
        assert no_stdin_record["status"] == "timed_out"

        if os.name == "posix":
            read_fd, write_fd = os.pipe()
            reader_stream = os.fdopen(read_fd, "r", encoding="utf-8")
            blocked_reader = threading.Thread(
                target=reader_stream.readline, daemon=True
            )
            blocked_reader.start()
            drain_started = time.monotonic()
            assert not RUNNER_MODULE.drain_readers(None, [blocked_reader])
            assert time.monotonic() - drain_started < 1.5
            os.close(write_fd)
            blocked_reader.join(timeout=1)
            reader_stream.close()

            group_success, group_success_record, success_pid, success_elapsed = (
                run_process_group_case(directory, "success")
            )
            assert group_success.returncode == 0, group_success.stderr
            assert group_success_record["status"] == "completed"
            assert group_success_record["termination_confirmed"]
            assert success_elapsed < 4.0

            leader_exit, leader_record, _leader_pid, leader_elapsed = (
                run_process_group_case(directory, "leader-exits")
            )
            assert leader_exit.returncode == 4, leader_exit.stderr
            assert leader_record["stop_reason"] == "process_group_lingering"
            assert leader_record["termination_confirmed"]
            assert json.loads(Path(leader_record["result_path"]).read_text(encoding="utf-8")) == {
                "status": "ready"
            }
            assert leader_elapsed < 4.0

            # Дать двум интерпретаторам время создать потомка до проверки его остановки.
            group_timeout_seconds = 1.0
            # Прежний предел 4 с включал 0,1 с работы. Сохраняем запас очистки 3,9 с.
            group_cleanup_allowance = 3.9
            group_timeout, timeout_record, timeout_pid, timeout_elapsed = (
                run_process_group_case(directory, "timeout", timeout=str(group_timeout_seconds))
            )
            assert group_timeout.returncode == 2, group_timeout.stderr
            assert timeout_record["status"] == "timed_out"
            assert timeout_record["stop_reason"] == "timeout"
            assert timeout_record["termination_confirmed"]
            assert timeout_record["returncode"] is not None
            assert timeout_elapsed < group_timeout_seconds + group_cleanup_allowance, timeout_elapsed

            group_sigint, sigint_record, sigint_pid, sigint_elapsed = (
                run_process_group_case(
                    directory, "sigint", signal_to_runner=signal.SIGINT
                )
            )
            assert group_sigint.returncode == 130, group_sigint.stderr
            assert sigint_record["status"] == "interrupted"
            assert sigint_record["signal"] == "SIGINT"
            assert sigint_record["termination_confirmed"]
            assert sigint_elapsed < 4.0

            group_sigterm, sigterm_record, sigterm_pid, sigterm_elapsed = (
                run_process_group_case(
                    directory,
                    "adapter-exits-on-term",
                    signal_to_runner=signal.SIGTERM,
                    repeat_signal=3,
                )
            )
            assert group_sigterm.returncode == 130, group_sigterm.stderr
            assert sigterm_record["status"] == "interrupted"
            assert sigterm_record["signal"] == "SIGTERM"
            assert sigterm_record["termination_confirmed"]
            assert sigterm_elapsed < 4.0

            external, external_record, _external_pid, external_elapsed = (
                run_process_group_case(
                    directory,
                    "external-holder",
                    timeout=str(group_timeout_seconds),
                    expect_child_stop=False,
                )
            )
            assert external.returncode == 2, external.stderr
            assert external_record["status"] == "timed_out"
            assert external_record["termination_confirmed"]
            assert external_elapsed < group_timeout_seconds + group_cleanup_allowance, external_elapsed

            original_killpg = RUNNER_MODULE.os.killpg
            try:
                RUNNER_MODULE.os.killpg = lambda _pgid, _signal: (_ for _ in ()).throw(
                    OSError(errno.EINVAL, "недопустимая группа")
                )
                errors: list[str] = []
                assert RUNNER_MODULE.process_group_exists(123, errors) is None
                assert errors
            finally:
                RUNNER_MODULE.os.killpg = original_killpg

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

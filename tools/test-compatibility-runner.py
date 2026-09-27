#!/usr/bin/env python3
"""Проверить внутренний запускатель совместимости без Docker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools/compatibility/run.py"
FIXTURE = ROOT / "evals/compatibility/edit-agents/fixture"
SCENARIO = ROOT / "evals/compatibility/edit-agents/scenario.json"
CHECK = ROOT / "evals/compatibility/edit-agents/check.py"
SCENARIO_DATA = json.loads(SCENARIO.read_text(encoding="utf-8"))
PROMPT = SCENARIO_DATA["prompt"]


def load_runner():
    spec = importlib.util.spec_from_file_location("compatibility_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить внутренний запускатель")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def workspace_from_command(arguments: list[str]) -> Path:
    mount = arguments[arguments.index("--mount") + 1]
    source = next(part.split("=", 1)[1] for part in mount.split(",") if part.startswith("source="))
    return Path(source)


class FakeProcess:
    def __init__(self, docker: "FakeDocker", arguments: list[str]) -> None:
        self.docker = docker
        self.arguments = arguments
        self.returncode: int | None = None
        self.killed = False
        self.mutated = False

    def communicate(self, input=None, timeout=None):
        self.docker.stdin_values.append(input)
        if self.killed:
            self.returncode = -9
            return "после остановки", ""
        if not self.mutated:
            self.mutated = True
            self.docker.mutator(workspace_from_command(self.arguments), input)
        if self.docker.behavior == "timeout":
            raise subprocess.TimeoutExpired(self.arguments, timeout, output="частичный вывод", stderr="ошибка")
        if self.docker.behavior == "interrupt":
            raise KeyboardInterrupt
        if self.docker.behavior == "communication-error":
            raise OSError("ошибка чтения Docker")
        self.returncode = self.docker.exit_code
        return self.docker.stdout, self.docker.stderr

    def kill(self) -> None:
        self.killed = True


class FakeDocker:
    def __init__(
        self,
        behavior: str = "success",
        mutator: Callable[[Path, str], None] | None = None,
        exit_code: int = 0,
    ) -> None:
        self.behavior = behavior
        self.mutator = mutator or (lambda workspace, task: None)
        self.exit_code = exit_code
        self.stdout = "заглушка stdout"
        self.stderr = "заглушка stderr"
        self.popen_arguments: list[str] | None = None
        self.popen_kwargs: dict[str, object] = {}
        self.cleanup_calls: list[tuple[list[str], dict[str, object]]] = []
        self.stdin_values: list[str] = []

    def popen(self, arguments, **kwargs):
        self.popen_arguments = list(arguments)
        self.popen_kwargs = kwargs
        return FakeProcess(self, list(arguments))

    def run(self, arguments, **kwargs):
        self.cleanup_calls.append((list(arguments), kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def edit_agents(workspace: Path, task: str) -> None:
    assert task == PROMPT
    path = workspace / "AGENTS.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "В итоговом ответе перечисляй изменённые файлы.",
            "В итоговом ответе кратко описывай результат и выполненные проверки.",
        ),
        encoding="utf-8",
    )


def add_unexpected_file(workspace: Path, task: str) -> None:
    edit_agents(workspace, task)
    (workspace / "notes.txt").write_text("лишний файл\n", encoding="utf-8")


def remove_agents(workspace: Path, task: str) -> None:
    (workspace / "AGENTS.md").unlink()


def replace_agents_with_symlink(target: Path) -> Callable[[Path, str], None]:
    def mutate(workspace: Path, task: str) -> None:
        (workspace / "AGENTS.md").unlink()
        (workspace / "AGENTS.md").symlink_to(target)

    return mutate


def run_case(fake: FakeDocker, results: Path):
    return runner.run_case(
        FIXTURE,
        "compatibility-test:image",
        ["compatibility-stub"],
        results,
        1,
        docker_executable="docker",
        popen_factory=fake.popen,
        run_factory=fake.run,
        scenario_path=SCENARIO,
        check_path=CHECK,
    )


def assert_safe_command(fake: FakeDocker, results: Path) -> None:
    assert fake.popen_arguments is not None
    arguments = fake.popen_arguments
    joined = " ".join(arguments)
    owner = FIXTURE.stat()
    assert arguments[:2] == ["docker", "run"]
    assert "--interactive" in arguments
    assert "--pull=never" in arguments
    assert arguments[arguments.index("--network") + 1] == "none"
    assert "--read-only" in arguments
    assert arguments[arguments.index("--user") + 1] == f"{owner.st_uid}:{owner.st_gid}"
    assert arguments[arguments.index("--workdir") + 1] == "/workspace"
    assert "--memory=512m" in arguments
    assert "--cpus=1.0" in arguments
    assert "--pids-limit=64" in arguments
    assert "compatibility-test:image" in arguments
    assert arguments.count("--mount") == 1
    mount = arguments[arguments.index("--mount") + 1]
    assert "type=bind" in mount
    assert "destination=/workspace" in mount
    assert ",rw" not in mount
    assert "--volume" not in arguments
    assert "/var/run/docker.sock" not in joined
    assert str(FIXTURE.resolve()) not in joined
    assert str(results.resolve()) not in joined
    assert str(SCENARIO) not in joined
    assert str(CHECK) not in joined
    assert PROMPT not in arguments
    assert fake.popen_kwargs["env"] == {}
    assert fake.popen_kwargs["stdin"] is subprocess.PIPE
    assert fake.stdin_values == [PROMPT]


def test_cli_parsing() -> None:
    args = runner.parse_args(
        [
            "--project",
            str(FIXTURE),
            "--image",
            "example:image",
            "--results-dir",
            "results",
            "--timeout",
            "12",
            "--command",
            "stub",
            "--flag",
            "value",
        ]
    )
    assert args.command == ["stub", "--flag", "value"]
    assert args.timeout == 12


def test_success_and_isolation() -> None:
    source_before = (FIXTURE / "AGENTS.md").read_bytes()
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        results = Path(temporary) / "results"
        fake = FakeDocker(mutator=edit_agents)
        report, report_path = run_case(fake, results)
        assert report["status"] == "passed"
        assert report["scenario_id"] == "compatibility-edit-agents"
        assert report["changed_paths"] == ["AGENTS.md"]
        assert report["unexpected_changes"] == []
        assert report["source_unchanged"]
        assert report["execution"]["exit_code"] == 0
        assert report["execution"]["duration_seconds"] >= 0
        assert report["execution"]["stdout"] == "заглушка stdout"
        assert report["file_check"]["status"] == "passed"
        assert report["skill_application"]["verified"] is False
        assert report_path.is_file()
        assert (report_path.parent / "source-snapshot.json").is_file()
        assert report["agents_artifacts"]["status"] == "available"
        assert report["artifacts"]["source_agents"] == "source-agents.md"
        assert report["artifacts"]["result_agents"] == "result-agents.md"
        assert report["artifacts"]["agents_diff"] == "agents.diff"
        assert (report_path.parent / "source-agents.md").read_bytes() == source_before
        assert "В итоговом ответе кратко описывай" in (
            report_path.parent / "result-agents.md"
        ).read_text(encoding="utf-8")
        assert "--- AGENTS.md (исходный)" in (
            report_path.parent / "agents.diff"
        ).read_text(encoding="utf-8")
        assert (report_path.parent / "stdout.txt").read_text(encoding="utf-8") == "заглушка stdout"
        assert (FIXTURE / "AGENTS.md").read_bytes() == source_before
        assert len(fake.cleanup_calls) == 1
        assert_safe_command(fake, results)


def test_unexpected_file_is_reported() -> None:
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        fake = FakeDocker(mutator=add_unexpected_file)
        report, _ = run_case(fake, Path(temporary) / "results")
        assert report["status"] == "failed"
        assert report["changed_paths"] == ["AGENTS.md", "notes.txt"]
        assert report["unexpected_changes"] == ["notes.txt"]
        assert report["file_check"]["status"] == "passed"


def test_command_failure_is_saved() -> None:
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        fake = FakeDocker(behavior="failure", mutator=edit_agents, exit_code=7)
        report, report_path = run_case(fake, Path(temporary) / "results")
        assert report["status"] == "failed"
        assert report["execution"]["status"] == "failed"
        assert report["execution"]["exit_code"] == 7
        assert report["execution"]["stdout"] == "заглушка stdout"
        assert report["execution"]["stderr"] == "заглушка stderr"
        assert report["agents_artifacts"]["status"] == "available"
        assert report_path.parent.joinpath("result-agents.md").is_file()
        assert report_path.parent.joinpath("agents.diff").is_file()


def test_missing_agents_keeps_report() -> None:
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        fake = FakeDocker(mutator=remove_agents)
        report, report_path = run_case(fake, Path(temporary) / "results")
        assert report["status"] == "failed"
        assert report_path.is_file()
        assert report["agents_artifacts"]["status"] == "missing"
        assert report["agents_artifacts"]["violations"][0]["code"] == "result-agents-missing"
        assert report["file_check"]["status"] == "not_run"


def test_symlink_agents_keeps_report_without_reading_target() -> None:
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        external = Path(temporary) / "external-agents.md"
        external.write_text("Внешнее содержимое\n", encoding="utf-8")
        fake = FakeDocker(mutator=replace_agents_with_symlink(external))
        report, report_path = run_case(fake, Path(temporary) / "results")
        assert report["status"] == "failed"
        assert report_path.is_file()
        assert report["agents_artifacts"]["status"] == "symlink"
        assert report["agents_artifacts"]["violations"][0]["code"] == "result-agents-symlink"
        assert report["file_check"]["status"] == "not_run"
        assert not report_path.parent.joinpath("result-agents.md").exists()
        assert "Внешнее содержимое" not in report_path.read_text(encoding="utf-8")


def assert_forced_cleanup(behavior: str, expected_status: str) -> None:
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        fake = FakeDocker(behavior=behavior, mutator=edit_agents)
        report, report_path = run_case(fake, Path(temporary) / "results")
        assert report["status"] == expected_status
        assert report["execution"]["status"] == expected_status
        actions = report["execution"]["cleanup"]["actions"]
        assert [action["operation"] for action in actions] == ["stop", "remove"]
        container_name = report["container"]["name"]
        assert all(container_name in arguments for arguments, _ in fake.cleanup_calls)
        assert all(kwargs["env"] == {} for _, kwargs in fake.cleanup_calls)
        assert all(kwargs["stdout"] is subprocess.PIPE for _, kwargs in fake.cleanup_calls)
        assert all(kwargs["stderr"] is subprocess.PIPE for _, kwargs in fake.cleanup_calls)
        assert report["agents_artifacts"]["status"] == "available"
        assert report_path.parent.joinpath("agents.diff").is_file()


def main() -> int:
    test_cli_parsing()
    test_success_and_isolation()
    test_unexpected_file_is_reported()
    test_command_failure_is_saved()
    test_missing_agents_keeps_report()
    test_symlink_agents_keeps_report_without_reading_target()
    assert_forced_cleanup("timeout", "timed_out")
    assert_forced_cleanup("interrupt", "interrupted")
    with tempfile.TemporaryDirectory(prefix="compatibility-runner-test-") as temporary:
        fake = FakeDocker(behavior="communication-error")
        report, report_path = run_case(fake, Path(temporary) / "results")
        assert report["status"] == "failed"
        assert report["execution"]["reason"] == "communication_error"
        assert "ошибка чтения Docker" in report["execution"]["stderr"]
        assert report_path.is_file()
    print("Проверки внутреннего запускателя совместимости пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

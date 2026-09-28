#!/usr/bin/env python3
"""Проверить команду установки опубликованной коллекции без Docker и сети."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/compatibility/install_published.py"


def load_module():
    spec = importlib.util.spec_from_file_location("install_published", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить команду установки")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class FakeProcess:
    def __init__(self, arguments: list[str]) -> None:
        self.arguments = arguments
        self.returncode = 0

    def communicate(self, timeout=None):
        run_dir = Path(
            next(
                item.split("source=", 1)[1].rsplit(",destination=", 1)[0]
                for item in self.arguments
                if item.startswith("type=bind,source=") and item.endswith(",destination=/results")
            )
        )
        project = run_dir / "prepared-project"
        commands = run_dir / "commands"
        for name, code, stdout in (
            ("apm_version", 0, "APM version 0.31.0\n"),
            ("marketplace_add", 0, "marketplace added\n"),
            ("install", 0, "installed\n"),
        ):
            (commands / f"{name}.stdout").write_text(stdout, encoding="utf-8")
            (commands / f"{name}.stderr").write_text("", encoding="utf-8")
            (commands / f"{name}.exit_code").write_text(f"{code}\n", encoding="utf-8")

        skill = project / ".agents/skills/ai-agents-md-maintenance"
        (skill / "references").mkdir(parents=True)
        files = {
            "SKILL.md": "skill\n",
            "README.md": "readme\n",
            "references/check.md": "check\n",
        }
        hashes = {}
        for relative, content in files.items():
            path = skill / relative
            path.write_text(content, encoding="utf-8")
            hashes[f".agents/skills/ai-agents-md-maintenance/{relative}"] = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        lock_lines = [
            "apm_version: 0.31.0",
            "dependencies:",
            "- name: ai-agent-supervisor",
            "  repo_url: mekras/apm-marketplace",
            "  version: 2.6.12",
            "  resolved_ref: ai-agent-supervisor--v2.6.12",
            "  resolved_commit: commit",
            "  deployed_file_hashes:",
        ]
        lock_lines.extend(f"    {key}: {value}" for key, value in hashes.items())
        (project / "apm.lock.yaml").write_text("\n".join(lock_lines) + "\n", encoding="utf-8")
        return "", ""

    def kill(self) -> None:
        self.returncode = -9


class FakeDocker:
    def __init__(self, cleanup_result=None, cleanup_error=None) -> None:
        self.popen_arguments: list[str] | None = None
        self.popen_kwargs: dict[str, object] = {}
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.cleanup_result = cleanup_result
        self.cleanup_error = cleanup_error

    def run(self, arguments, **kwargs):
        self.calls.append((list(arguments), kwargs))
        if arguments[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:local\n", stderr="")
        if arguments[1:3] == ["rm", "-f"]:
            if self.cleanup_error is not None:
                raise self.cleanup_error
            if self.cleanup_result is not None:
                return self.cleanup_result
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def popen(self, arguments, **kwargs):
        self.popen_arguments = list(arguments)
        self.popen_kwargs = kwargs
        return FakeProcess(list(arguments))


def test_success_and_safe_container() -> None:
    fake = FakeDocker()
    with tempfile.TemporaryDirectory(prefix="install-published-test-") as directory:
        report, report_path = MODULE.run_case(
            "sha256:local",
            Path(directory) / "results",
            30,
            docker_executable="docker",
            popen_factory=fake.popen,
            run_factory=fake.run,
        )
        assert report["status"] == "passed"
        assert report_path.is_file()
        assert report["validation"]["version_check"]["installed"] == "2.6.12"
        assert report["validation"]["target_skill"]["passed"]
        assert report["validation"]["projection"]["matches_lock_hashes"]
        assert report["validation"]["installed_skills"] == ["ai-agents-md-maintenance"]
        assert report["commands"]["marketplace_add"]["exit_code"] == 0
        assert report["commands"]["install"]["exit_code"] == 0
        arguments = fake.popen_arguments
        assert arguments is not None
        assert arguments[arguments.index("--pull=never")] == "--pull=never"
        assert arguments[arguments.index("--network") + 1] == "bridge"
        assert arguments[arguments.index("--user") + 1] != "0:0"
        assert "--volume" not in arguments
        assert "/var/run/docker.sock" not in " ".join(arguments)
        assert str(ROOT) not in " ".join(arguments)
        assert [arguments[index + 1] for index, value in enumerate(arguments[:-1]) if value == "--env"] == [
            "HOME=/home/sandbox"
        ]
        assert fake.popen_kwargs["env"] == {}
        assert fake.popen_kwargs["stdin"] is subprocess.DEVNULL
        assert not (Path(report["prepared_project"]) / ".git").exists()
        assert all(kwargs["env"] == {} for _, kwargs in fake.calls)


def test_missing_local_image_keeps_partial_project() -> None:
    fake = FakeDocker()

    def failed_image(arguments, **kwargs):
        fake.calls.append((list(arguments), kwargs))
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="No such image: sha256:missing\n",
        )

    with tempfile.TemporaryDirectory(prefix="install-published-test-") as directory:
        report, report_path = MODULE.run_case(
            "sha256:missing",
            Path(directory) / "results",
            30,
            docker_executable="docker",
            popen_factory=fake.popen,
            run_factory=failed_image,
        )
        assert report["status"] == "failed"
        assert report["image"]["status"] == "failed"
        assert report["execution"]["status"] == "not_run"
        assert report_path.is_file()
        assert Path(report["prepared_project"]).is_dir()
        assert not fake.popen_arguments


def test_cleanup_failure_does_not_hide_successful_installation() -> None:
    fake = FakeDocker(
        cleanup_result=SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="docker rm failed\n",
        )
    )
    with tempfile.TemporaryDirectory(prefix="install-published-test-") as directory:
        report, _ = MODULE.run_case(
            "sha256:local",
            Path(directory) / "results",
            30,
            docker_executable="docker",
            popen_factory=fake.popen,
            run_factory=fake.run,
        )
        assert report["status"] == "failed"
        assert report["validation"]["passed"] is True
        assert report["execution"]["status"] == "completed"
        assert report["execution"]["cleanup"]["status"] == "failed"
        assert report["execution"]["cleanup"]["stderr"] == "docker rm failed\n"


def test_cleanup_exception_does_not_hide_successful_installation() -> None:
    fake = FakeDocker(cleanup_error=RuntimeError("docker rm unavailable"))
    with tempfile.TemporaryDirectory(prefix="install-published-test-") as directory:
        report, _ = MODULE.run_case(
            "sha256:local",
            Path(directory) / "results",
            30,
            docker_executable="docker",
            popen_factory=fake.popen,
            run_factory=fake.run,
        )
        assert report["status"] == "failed"
        assert report["validation"]["passed"] is True
        assert report["execution"]["cleanup"]["status"] == "failed"
        assert report["execution"]["cleanup"]["stderr"] == "docker rm unavailable"


def test_cli_contract() -> None:
    args = MODULE.parse_args(["--image", "sha256:local", "--results-dir", "results", "--timeout", "45"])
    assert args.image == "sha256:local"
    assert args.timeout == 45
    assert args.target == "codex"
    assert MODULE.COMMANDS["marketplace_add"] == [
        "apm",
        "marketplace",
        "add",
        "mekras/apm-marketplace",
        "--ref",
        "master",
    ]
    assert MODULE.COMMANDS["install"] == [
        "apm",
        "install",
        "ai-agent-supervisor@mekras#2.6.12",
        "--target",
        "codex",
    ]
    hermes_args = MODULE.parse_args(
        [
            "--image",
            "sha256:local",
            "--results-dir",
            "results",
            "--timeout",
            "45",
            "--target",
            "hermes",
        ]
    )
    assert hermes_args.target == "hermes"
    assert MODULE.commands_for_target("hermes")["install"][-1] == "hermes"


def test_hermes_project_and_projection_validation() -> None:
    with tempfile.TemporaryDirectory(prefix="install-published-hermes-test-") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        setup = MODULE.prepare_hermes_project(project)
        assert setup["git_initialized"] is True
        assert setup["commit_count"] == 0
        assert (project / "AGENTS.md").read_bytes() == (
            ROOT / "evals/compatibility/edit-agents/fixture/AGENTS.md"
        ).read_bytes()
        assert (project / ".git").is_dir()

        skill = project / ".agents/skills/ai-agents-md-maintenance"
        (skill / "references").mkdir(parents=True)
        files = {
            "SKILL.md": "skill\n",
            "README.md": "readme\n",
            "references/check.md": "check\n",
        }
        hashes = {}
        for relative, content in files.items():
            path = skill / relative
            path.write_text(content, encoding="utf-8")
            hashes[f".agents/skills/ai-agents-md-maintenance/{relative}"] = "sha256:" + hashlib.sha256(
                content.encode()
            ).hexdigest()
        (project / "apm.lock.yaml").write_text(
            "\n".join(
                [
                    "apm_version: 0.31.0",
                    "dependencies:",
                    "- name: ai-agent-supervisor",
                    "  repo_url: mekras/apm-marketplace",
                    "  version: 2.6.12",
                    "  resolved_ref: ai-agent-supervisor--v2.6.12",
                    "  resolved_commit: commit",
                    "  deployed_file_hashes:",
                    *[f"    {key}: {value}" for key, value in hashes.items()],
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        commands = root / "results/commands"
        commands.mkdir(parents=True)
        for name in ("apm_version", "marketplace_add", "install"):
            (commands / f"{name}.exit_code").write_text("0\n", encoding="utf-8")
            (commands / f"{name}.stdout").write_text("ok\n", encoding="utf-8")
            (commands / f"{name}.stderr").write_text("", encoding="utf-8")
        discovery = {
            "passed": True,
            "name": "ai-agents-md-maintenance",
            "path": str(skill),
        }
        validation = MODULE.validate_installation(project, root / "results", "hermes", discovery)
        assert validation["target"] == "hermes"
        assert validation["projection"]["root"].endswith(".agents/skills")
        assert validation["projection"]["expected_path"].endswith(".agents/skills")
        assert validation["projection"]["actual_path"].endswith(".agents/skills")
        assert validation["projection"]["lock_hashes_status"] == "present"
        assert validation["projection"]["matches_lock_hashes"] is True
        assert validation["target_skill"]["passed"] is True
        assert validation["installation_result"]["status"] == "passed"
        assert validation["passed"] is True


def test_hermes_detection_container_is_isolated() -> None:
    arguments = MODULE.docker_command(
        "docker",
        "hermes-detection",
        Path("/tmp/project"),
        Path("/tmp/results"),
        "sha256:local",
        1000,
        100,
        network="none",
        script=MODULE.HERMES_DETECTION_SCRIPT,
        hermes_home=Path("/tmp/hermes-home"),
    )
    assert arguments[arguments.index("--network") + 1] == "none"
    assert arguments[arguments.index("--user") + 1] == "1000:100"
    assert "--read-only" in arguments
    assert "HERMES_HOME=/tmp/hermes-home" in arguments
    assert "hermes skills trust /workspace" in arguments[-1]
    assert "hermes skills list --source local" in arguments[-1]


def test_zero_apm_codes_do_not_hide_missing_hermes_projection() -> None:
    with tempfile.TemporaryDirectory(prefix="install-published-hermes-failure-") as directory:
        root = Path(directory)
        project = root / "project"
        results = root / "results"
        commands = results / "commands"
        project.mkdir()
        commands.mkdir(parents=True)
        (project / "apm.lock.yaml").write_text(
            "\n".join(
                [
                    "apm_version: 0.31.0",
                    "dependencies:",
                    "- name: ai-agent-supervisor",
                    "  repo_url: mekras/apm-marketplace",
                    "  version: 2.6.12",
                    "  resolved_commit: commit",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        for name in ("apm_version", "marketplace_add", "install"):
            (commands / f"{name}.exit_code").write_text("0\n", encoding="utf-8")
            (commands / f"{name}.stdout").write_text("ok\n", encoding="utf-8")
            (commands / f"{name}.stderr").write_text("", encoding="utf-8")
        validation = MODULE.validate_installation(
            project,
            results,
            "hermes",
            {"passed": False, "name": None, "path": str(project / ".agents/skills")},
        )
        assert validation["projection"]["expected_path"].endswith(".agents/skills")
        assert validation["projection"]["actual_path"] is None
        assert validation["projection"]["actual_exists"] is False
        assert validation["projection"]["lock_hashes_status"] == "absent"
        assert validation["projection"]["matches_lock_hashes"] is False
        assert validation["installation_result"]["apm_commands_succeeded"] is True
        assert validation["installation_result"]["status"] == "failed"
        assert validation["passed"] is False


def main() -> int:
    test_success_and_safe_container()
    test_missing_local_image_keeps_partial_project()
    test_cleanup_failure_does_not_hide_successful_installation()
    test_cleanup_exception_does_not_hide_successful_installation()
    test_cli_contract()
    test_hermes_project_and_projection_validation()
    test_hermes_detection_container_is_isolated()
    test_zero_apm_codes_do_not_hide_missing_hermes_projection()
    print("Проверки команды установки опубликованной коллекции пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

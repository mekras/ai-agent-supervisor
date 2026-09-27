#!/usr/bin/env python3
"""Проверить установку опубликованной коллекции для цели Codex через Docker."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - окружение без зависимости проекта
    yaml = None


PACKAGE_NAME = "ai-agent-supervisor"
PACKAGE_REPOSITORY = "mekras/apm-marketplace"
PACKAGE_VERSION = "2.6.12"
# APM 0.31.0 projects the Codex target into the shared Agent Skills path.
SKILLS_ROOT = Path(".agents/skills")
TARGET_SKILL = "ai-agents-md-maintenance"
INSPECT_TIMEOUT_SECONDS = 15

COMMANDS = {
    "apm_version": ["apm", "--version"],
    "marketplace_add": [
        "apm",
        "marketplace",
        "add",
        PACKAGE_REPOSITORY,
        "--ref",
        "master",
    ],
    "install": [
        "apm",
        "install",
        f"{PACKAGE_NAME}@mekras#{PACKAGE_VERSION}",
        "--target",
        "codex",
    ],
}


CONTAINER_SCRIPT = r"""#!/bin/sh
set +e

run_step() {
    name="$1"
    shift
    "$@" >"/results/commands/${name}.stdout" 2>"/results/commands/${name}.stderr"
    code=$?
    printf '%s\n' "$code" >"/results/commands/${name}.exit_code"
    last_code=$code
    return 0
}

run_step apm_version apm --version
run_step marketplace_add apm marketplace add mekras/apm-marketplace --ref master
marketplace_code=$last_code
run_step install apm install ai-agent-supervisor@mekras#2.6.12 --target codex
install_code=$last_code

if [ "$marketplace_code" -eq 0 ] && [ "$install_code" -eq 0 ]; then
    exit 0
fi
exit 1
"""

RunFactory = Callable[..., Any]
PopenFactory = Callable[..., Any]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def docker_command(
    docker_executable: str,
    container_name: str,
    project: Path,
    run_dir: Path,
    image_id: str,
    uid: int,
    gid: int,
) -> list[str]:
    return [
        docker_executable,
        "run",
        "--interactive",
        "--name",
        container_name,
        "--pull=never",
        "--network",
        "bridge",
        "--read-only",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        f"{uid}:{gid}",
        "--workdir",
        "/workspace",
        "--memory=512m",
        "--cpus=1.0",
        "--pids-limit=64",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs",
        f"/home/sandbox:rw,noexec,nosuid,size=64m,uid={uid},gid={gid},mode=700",
        "--env",
        "HOME=/home/sandbox",
        "--mount",
        f"type=bind,source={project},destination=/workspace",
        "--mount",
        f"type=bind,source={run_dir},destination=/results",
        image_id,
        "sh",
        "-c",
        CONTAINER_SCRIPT,
    ]


def inspect_image(
    docker_executable: str, image_id: str, run_factory: RunFactory
) -> dict[str, Any]:
    try:
        result = run_factory(
            [
                docker_executable,
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                image_id,
            ],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={},
            timeout=INSPECT_TIMEOUT_SECONDS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout = normalize_output(getattr(result, "stdout", ""))
        stderr = normalize_output(getattr(result, "stderr", ""))
        resolved_id = stdout.strip().splitlines()[0] if stdout.strip() else None
        return {
            "status": "passed" if result.returncode == 0 and resolved_id else "failed",
            "exit_code": result.returncode,
            "requested_id": image_id,
            "resolved_id": resolved_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timed_out",
            "exit_code": None,
            "requested_id": image_id,
            "resolved_id": None,
            "stdout": normalize_output(exc.stdout),
            "stderr": normalize_output(exc.stderr),
        }
    except Exception as exc:  # pragma: no cover - граница Docker CLI
        return {
            "status": "failed",
            "exit_code": None,
            "requested_id": image_id,
            "resolved_id": None,
            "stdout": "",
            "stderr": str(exc),
        }


def cleanup_container(
    docker_executable: str,
    container_name: str,
    run_factory: RunFactory,
) -> dict[str, Any]:
    try:
        result = run_factory(
            [docker_executable, "rm", "-f", container_name],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={},
            timeout=INSPECT_TIMEOUT_SECONDS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": normalize_output(getattr(result, "stdout", "")),
            "stderr": normalize_output(getattr(result, "stderr", "")),
        }
    except Exception as exc:  # pragma: no cover - защитная граница очистки
        return {"status": "failed", "exit_code": None, "stdout": "", "stderr": str(exc)}


def run_container(
    arguments: Sequence[str],
    timeout: float,
    docker_executable: str,
    popen_factory: PopenFactory,
    run_factory: RunFactory,
) -> dict[str, Any]:
    started_at = time.monotonic()
    process = None
    output = ""
    error = ""
    status = "failed"
    reason = "docker_error"
    exit_code: int | None = None
    container_name = arguments[arguments.index("--name") + 1]
    try:
        process = popen_factory(
            list(arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={},
        )
        try:
            output, error = process.communicate(timeout=timeout)
            output = normalize_output(output)
            error = normalize_output(error)
            exit_code = process.returncode
            status = "completed" if exit_code == 0 else "failed"
            reason = "completed" if status == "completed" else "command_failed"
        except subprocess.TimeoutExpired as exc:
            status = "timed_out"
            reason = "timeout"
            try:
                process.kill()
            except Exception:
                pass
            output, error = process.communicate()
            output = normalize_output(output)
            error = normalize_output(error)
            if exc.output:
                output = normalize_output(exc.output) + output
            if exc.stderr:
                error = normalize_output(exc.stderr) + error
        except KeyboardInterrupt:
            status = "interrupted"
            reason = "interrupted"
            try:
                process.kill()
            except Exception:
                pass
            output, error = process.communicate()
            output = normalize_output(output)
            error = normalize_output(error)
        except OSError as exc:
            status = "failed"
            reason = "communication_error"
            error = str(exc)
    except OSError as exc:
        error = str(exc)
    cleanup = (
        cleanup_container(docker_executable, container_name, run_factory)
        if process is not None
        else {"status": "not_run", "exit_code": None, "stdout": "", "stderr": ""}
    )
    return {
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - started_at, 6),
        "stdout": output,
        "stderr": error,
        "cleanup": cleanup,
    }


def command_record(run_dir: Path, name: str) -> dict[str, Any]:
    command_dir = run_dir / "commands"
    stdout_path = command_dir / f"{name}.stdout"
    stderr_path = command_dir / f"{name}.stderr"
    code_path = command_dir / f"{name}.exit_code"
    exit_code: int | None = None
    if code_path.is_file():
        try:
            exit_code = int(code_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            exit_code = None
    return {
        "argv": COMMANDS[name],
        "status": "passed" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        "stdout_path": str(stdout_path.relative_to(run_dir)),
        "stderr_path": str(stderr_path.relative_to(run_dir)),
        "stdout": stdout_path.read_text(encoding="utf-8") if stdout_path.is_file() else "",
        "stderr": stderr_path.read_text(encoding="utf-8") if stderr_path.is_file() else "",
    }


def load_lock(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if yaml is None:
        return None, "В окружении запуска отсутствует PyYAML."
    if not path.is_file():
        return None, f"Не найден файл блокировки: {path}"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return None, f"Не удалось прочитать lock-файл: {exc}"
    if not isinstance(data, dict):
        return None, "Lock-файл должен содержать объект."
    return data, None


def file_hashes(root: Path) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    unsafe: list[str] = []
    if not root.is_dir():
        return hashes, unsafe
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            unsafe.append(relative)
        elif path.is_file():
            hashes[relative] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes, unsafe


def validate_installation(project: Path, run_dir: Path) -> dict[str, Any]:
    lock, lock_error = load_lock(project / "apm.lock.yaml")
    raw_dependencies = lock.get("dependencies", []) if isinstance(lock, dict) else []
    dependencies = raw_dependencies if isinstance(raw_dependencies, list) else []
    if lock is not None and not isinstance(raw_dependencies, list):
        lock_error = "В lock-файле поле dependencies не является списком."
    package_entries = [
        item
        for item in dependencies
        if isinstance(item, dict)
        and item.get("name") == PACKAGE_NAME
        and item.get("repo_url") == PACKAGE_REPOSITORY
    ]
    installed_versions = [
        {
            "name": item.get("name"),
            "version": item.get("version"),
            "repo_url": item.get("repo_url"),
            "resolved_ref": item.get("resolved_ref"),
            "resolved_commit": item.get("resolved_commit"),
            "virtual_path": item.get("virtual_path"),
        }
        for item in dependencies
        if isinstance(item, dict)
    ]
    source_identifiers = [
        {
            "name": item.get("name"),
            "source_id": item.get("repo_url"),
            "resolved_ref": item.get("resolved_ref"),
            "resolved_commit": item.get("resolved_commit"),
            "version": item.get("version"),
        }
        for item in dependencies
        if isinstance(item, dict)
    ]
    package_entry = package_entries[0] if len(package_entries) == 1 else None
    installed_version = package_entry.get("version") if package_entry else None
    version_check = {
        "expected": PACKAGE_VERSION,
        "installed": installed_version,
        "passed": installed_version == PACKAGE_VERSION and len(package_entries) == 1,
    }
    skills_root = project / SKILLS_ROOT
    installed_skills = sorted(
        path.parent.name for path in skills_root.glob("*/SKILL.md") if path.is_file()
    )
    expected_hashes: dict[str, str] = {}
    if package_entry:
        raw_hashes = package_entry.get("deployed_file_hashes") or {}
        for path, digest in (raw_hashes if isinstance(raw_hashes, dict) else {}).items():
            if isinstance(path, str) and path.startswith(f"{SKILLS_ROOT.as_posix()}/"):
                expected_hashes[path[len(SKILLS_ROOT.as_posix()) + 1 :]] = str(digest)
    actual_hashes, unsafe_paths = file_hashes(skills_root)
    projection_matches = bool(expected_hashes) and expected_hashes == actual_hashes
    target_prefix = f"{TARGET_SKILL}/"
    expected_target = {
        path[len(target_prefix) :]: digest
        for path, digest in expected_hashes.items()
        if path.startswith(target_prefix)
    }
    actual_target = {
        path[len(target_prefix) :]: digest
        for path, digest in actual_hashes.items()
        if path.startswith(target_prefix)
    }
    target_path = skills_root / TARGET_SKILL
    target_check = {
        "path": str(target_path),
        "exists": target_path.is_dir(),
        "skill_md_exists": (target_path / "SKILL.md").is_file(),
        "expected_files": sorted(expected_target),
        "actual_files": sorted(actual_target),
        "passed": bool(expected_target)
        and expected_target == actual_target
        and not unsafe_paths
        and target_path.is_dir()
        and (target_path / "SKILL.md").is_file(),
    }
    lock_apm_version = lock.get("apm_version") if isinstance(lock, dict) else None
    command_results = {name: command_record(run_dir, name) for name in COMMANDS}
    return {
        "lockfile": str(project / "apm.lock.yaml"),
        "lock_error": lock_error,
        "apm_version": {
            "command_output": command_results["apm_version"]["stdout"],
            "lockfile": lock_apm_version,
        },
        "installed_versions": installed_versions,
        "source_identifiers": source_identifiers,
        "version_check": version_check,
        "installed_skills": installed_skills,
        "projection": {
            "root": str(skills_root),
            "expected_files_from_lock": sorted(expected_hashes),
            "actual_files": sorted(actual_hashes),
            "unsafe_paths": unsafe_paths,
            "matches_lock_hashes": projection_matches,
        },
        "target_skill": target_check,
        "passed": (
            lock_error is None
            and command_results["marketplace_add"]["exit_code"] == 0
            and command_results["install"]["exit_code"] == 0
            and version_check["passed"]
            and target_check["passed"]
            and projection_matches
        ),
    }


def run_case(
    image_id: str,
    results_dir: Path,
    timeout: float,
    *,
    docker_executable: str = "docker",
    popen_factory: PopenFactory = subprocess.Popen,
    run_factory: RunFactory = subprocess.run,
) -> tuple[dict[str, Any], Path]:
    if not image_id.strip() or image_id.startswith("-") or any(c.isspace() for c in image_id):
        raise ValueError("ID Docker-образа должен быть одним значением без пробелов и параметров")
    if timeout <= 0:
        raise ValueError("Тайм-аут должен быть положительным")
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    run_dir = results_dir / f"install-codex-{uuid.uuid4().hex}"
    project = run_dir / "prepared-project"
    commands_dir = run_dir / "commands"
    project.mkdir(parents=True)
    commands_dir.mkdir()
    owner = project.stat()
    image = inspect_image(docker_executable, image_id, run_factory)
    execution: dict[str, Any] = {
        "status": "not_run",
        "reason": "image_not_available",
        "exit_code": None,
        "duration_seconds": 0,
        "stdout": "",
        "stderr": "",
        "cleanup": {"status": "not_run", "exit_code": None, "stdout": "", "stderr": ""},
    }
    error: str | None = None
    if image["status"] == "passed":
        container_name = f"compatibility-install-{uuid.uuid4().hex}"
        arguments = docker_command(
            docker_executable,
            container_name,
            project,
            run_dir,
            image_id,
            owner.st_uid,
            owner.st_gid,
        )
        try:
            if owner.st_uid == 0:
                raise ValueError("Рабочий проект принадлежит UID 0, нужен непривилегированный UID")
            execution = run_container(
                arguments,
                timeout,
                docker_executable,
                popen_factory,
                run_factory,
            )
        except Exception as exc:
            error = str(exc)
    validation = validate_installation(project, run_dir)
    (run_dir / "container.stdout").write_text(execution["stdout"], encoding="utf-8")
    (run_dir / "container.stderr").write_text(execution["stderr"], encoding="utf-8")
    status = (
        "passed"
        if image["status"] == "passed"
        and execution["status"] == "completed"
        and execution["cleanup"]["status"] == "passed"
        and validation["passed"]
        else "failed"
    )
    report = {
        "status": status,
        "error": error,
        "image": image,
        "container": {
            "user": f"{owner.st_uid}:{owner.st_gid}",
            "network": "bridge",
            "memory": "512m",
            "cpus": "1.0",
            "pids_limit": 64,
            "home": "/home/sandbox",
            "project_mount": "/workspace",
            "results_mount": "/results",
            "repository_mount": False,
            "docker_socket": False,
            "pull": "never",
            "host_environment": {},
            "container_environment": {"HOME": "/home/sandbox"},
        },
        "execution": execution,
        "commands": {name: command_record(run_dir, name) for name in COMMANDS},
        "validation": validation,
        "initial_project_files": [],
        "prepared_project": str(project),
        "report": str(run_dir / "report.json"),
    }
    write_json(run_dir / "report.json", report)
    return report, run_dir / "report.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Локальный ID уже собранного базового образа")
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--timeout", required=True, type=float, help="Общий тайм-аут установки в секундах")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout должен быть положительным")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    docker = shutil.which("docker")
    if docker is None:
        print("Docker не найден. Образ не собирается и не скачивается автоматически.", file=sys.stderr)
        return 2
    try:
        report, report_path = run_case(
            args.image,
            args.results_dir,
            args.timeout,
            docker_executable=docker,
        )
    except (OSError, ValueError) as exc:
        print(f"Проверка установки не подготовлена: {exc}", file=sys.stderr)
        return 2
    print(f"Отчёт: {report_path}")
    print(f"Проект: {report['prepared_project']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

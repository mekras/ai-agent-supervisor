#!/usr/bin/env python3
"""Изолированно запустить внутренний сценарий совместимости через Docker."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_PATH = ROOT / "evals/compatibility/edit-agents/scenario.json"
CHECK_PATH = ROOT / "evals/compatibility/edit-agents/check.py"
ALLOWED_CHANGED_PATHS = {"AGENTS.md"}
CHECK_TIMEOUT_SECONDS = 30
AGENTS_PATH = Path("AGENTS.md")
SOURCE_AGENTS_ARTIFACT = "source-agents.md"
RESULT_AGENTS_ARTIFACT = "result-agents.md"
AGENTS_DIFF_ARTIFACT = "agents.diff"
CODEX_JSONL_ARTIFACT = "codex.jsonl"
CODEX_FINAL_ANSWER_ARTIFACT = "final-answer.txt"
CODEX_COMMAND_ARTIFACT = "codex-command.json"
CODEX_VERSION = "0.155.1"
COMMAND_MODE = "command"
CODEX_MODE = "codex"

PopenFactory = Callable[..., Any]
RunFactory = Callable[..., Any]


def normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def load_task(scenario_path: Path) -> tuple[str, str]:
    try:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось прочитать scenario.json: {exc}") from exc
    if not isinstance(scenario, dict):
        raise ValueError("scenario.json должен содержать JSON-объект")
    scenario_id = scenario.get("id")
    prompt = scenario.get("prompt")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("В scenario.json отсутствует непустой id")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("В scenario.json отсутствует непустой prompt")
    return scenario_id, prompt


def file_snapshot(
    root: Path, *, skip_unsafe: bool = False
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            if skip_unsafe:
                continue
            raise ValueError(f"Символьные ссылки в проекте не поддерживаются: {relative}")
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
            mode = path.stat().st_mode & 0o777
        except OSError:
            if skip_unsafe:
                continue
            raise
        snapshot[relative] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "mode": mode,
        }
    return snapshot


def changed_paths(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def paths_overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def docker_command(
    docker_executable: str,
    container_name: str,
    workspace: Path,
    image: str,
    command: Sequence[str],
    container_uid: int,
    container_gid: int,
    output_workspace: Path | None = None,
) -> list[str]:
    container_user = f"{container_uid}:{container_gid}"
    arguments = [
        docker_executable,
        "run",
        "--interactive",
        "--name",
        container_name,
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        container_user,
        "--workdir",
        "/workspace",
        "--memory=512m",
        "--cpus=1.0",
        "--pids-limit=64",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs",
        f"/home/sandbox:rw,noexec,nosuid,size=64m,uid={container_uid},gid={container_gid},mode=700",
        "--env",
        "HOME=/home/sandbox",
        "--mount",
        f"type=bind,source={workspace},destination=/workspace",
    ]
    if output_workspace is not None:
        arguments.extend(
            [
                "--mount",
                f"type=bind,source={output_workspace},destination=/run-output",
            ]
        )
    arguments.extend([image, *command])
    return arguments


def codex_command(model: str, effort: str) -> list[str]:
    return [
        "codex",
        "exec",
        "--json",
        "--color",
        "never",
        "--strict-config",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ephemeral",
        "--cd",
        "/workspace",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        model,
        "-c",
        f"model_reasoning_effort={json.dumps(effort)}",
        "--output-last-message",
        f"/run-output/{CODEX_FINAL_ANSWER_ARTIFACT}",
        "-",
    ]


def docker_call(
    docker_executable: str,
    arguments: Sequence[str],
    run_factory: RunFactory,
) -> Any:
    return run_factory(
        [docker_executable, *arguments],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={},
        timeout=5,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def cleanup_container(
    docker_executable: str,
    container_name: str,
    run_factory: RunFactory,
    stop_required: bool,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    errors: list[str] = []
    commands: list[tuple[str, list[str]]] = []
    if stop_required:
        commands.append(("stop", ["stop", "--time", "1", container_name]))
    commands.append(("remove", ["rm", "-f", container_name]))
    for operation, arguments in commands:
        try:
            result = docker_call(docker_executable, arguments, run_factory)
            actions.append(
                {
                    "operation": operation,
                    "returncode": getattr(result, "returncode", None),
                }
            )
            if getattr(result, "returncode", 1) != 0:
                errors.append(f"{operation}: код {result.returncode}")
        except Exception as exc:  # pragma: no cover - defensive cleanup boundary
            errors.append(f"{operation}: {exc}")
    return {"actions": actions, "errors": errors}


def terminate_process(process: Any) -> tuple[str, str]:
    try:
        process.kill()
    except Exception:
        pass
    try:
        output, error = process.communicate()
    except Exception as exc:  # pragma: no cover - defensive subprocess boundary
        return "", str(exc)
    return normalize_output(output), normalize_output(error)


def run_container(
    arguments: Sequence[str],
    task: str,
    timeout: float,
    popen_factory: PopenFactory,
    docker_executable: str,
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
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={},
        )
        try:
            output, error = process.communicate(input=task, timeout=timeout)
            output = normalize_output(output)
            error = normalize_output(error)
            exit_code = process.returncode
            status = "completed" if exit_code == 0 else "failed"
            reason = "completed" if status == "completed" else "command_failed"
        except subprocess.TimeoutExpired as exc:
            status = "timed_out"
            reason = "timeout"
            output, error = terminate_process(process)
            if exc.output:
                output = normalize_output(exc.output) + output
            if exc.stderr:
                error = normalize_output(exc.stderr) + error
        except KeyboardInterrupt:
            status = "interrupted"
            reason = "interrupted"
            output, error = terminate_process(process)
        except OSError as exc:
            status = "failed"
            reason = "communication_error"
            error = str(exc)
    except OSError as exc:
        error = str(exc)
    cleanup = cleanup_container(
        docker_executable,
        container_name,
        run_factory,
        stop_required=status in {"timed_out", "interrupted"},
    ) if process is not None else {"actions": [], "errors": []}
    duration = time.monotonic() - started_at
    return {
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 6),
        "stdout": output,
        "stderr": error,
        "cleanup": cleanup,
    }


def run_checker(workspace: Path, check_path: Path) -> dict[str, Any]:
    started_at = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, str(check_path), str(workspace)],
            cwd=ROOT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started_at, 6),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timed_out",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started_at, 6),
            "stdout": normalize_output(exc.stdout),
            "stderr": normalize_output(exc.stderr),
        }
    except OSError as exc:
        return {
            "status": "failed",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started_at, 6),
            "stdout": "",
            "stderr": str(exc),
        }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_codex_artifacts(
    run_dir: Path, output_workspace: Path, execution: dict[str, Any]
) -> dict[str, Any]:
    jsonl_path = run_dir / CODEX_JSONL_ARTIFACT
    jsonl_path.write_text(execution["stdout"], encoding="utf-8")
    source_final = output_workspace / CODEX_FINAL_ANSWER_ARTIFACT
    final_path = run_dir / CODEX_FINAL_ANSWER_ARTIFACT
    if source_final.is_file():
        shutil.copyfile(source_final, final_path)
    return {
        "jsonl": CODEX_JSONL_ARTIFACT,
        "final_answer": CODEX_FINAL_ANSWER_ARTIFACT if final_path.is_file() else None,
        "final_answer_status": "available" if final_path.is_file() else "missing",
    }


def prepared_execution() -> dict[str, Any]:
    return {
        "status": "not_run",
        "reason": "preparation_only",
        "exit_code": None,
        "duration_seconds": 0,
        "stdout": "",
        "stderr": "",
        "cleanup": {"actions": [], "errors": []},
    }


def save_agents_artifacts(
    run_dir: Path, workspace: Path, source_content: bytes
) -> dict[str, Any]:
    source_artifact = run_dir / SOURCE_AGENTS_ARTIFACT
    result_artifact = run_dir / RESULT_AGENTS_ARTIFACT
    diff_artifact = run_dir / AGENTS_DIFF_ARTIFACT
    source_artifact.write_bytes(source_content)
    result_path = workspace / AGENTS_PATH
    artifacts: dict[str, Any] = {
        "status": "unavailable",
        "source": SOURCE_AGENTS_ARTIFACT,
        "result": None,
        "diff": None,
        "violations": [],
    }
    if result_path.is_symlink():
        artifacts["status"] = "symlink"
        artifacts["violations"].append(
            {
                "code": "result-agents-symlink",
                "path": AGENTS_PATH.as_posix(),
                "message": "Итоговый AGENTS.md заменён символьной ссылкой и не прочитан.",
            }
        )
        return artifacts
    if not result_path.exists():
        artifacts["status"] = "missing"
        artifacts["violations"].append(
            {
                "code": "result-agents-missing",
                "path": AGENTS_PATH.as_posix(),
                "message": "Итоговый AGENTS.md отсутствует.",
            }
        )
        return artifacts
    if not result_path.is_file():
        artifacts["status"] = "not-regular-file"
        artifacts["violations"].append(
            {
                "code": "result-agents-not-regular-file",
                "path": AGENTS_PATH.as_posix(),
                "message": "Итоговый AGENTS.md не является обычным файлом.",
            }
        )
        return artifacts
    try:
        result_content = result_path.read_bytes()
    except OSError as exc:
        artifacts["status"] = "unreadable"
        artifacts["violations"].append(
            {
                "code": "result-agents-unreadable",
                "path": AGENTS_PATH.as_posix(),
                "message": f"Итоговый AGENTS.md не удалось прочитать: {exc}",
            }
        )
        return artifacts
    result_artifact.write_bytes(result_content)
    diff_artifact.write_text(
        "".join(
            difflib.unified_diff(
                source_content.decode("utf-8", errors="replace").splitlines(
                    keepends=True
                ),
                result_content.decode("utf-8", errors="replace").splitlines(
                    keepends=True
                ),
                fromfile="AGENTS.md (исходный)",
                tofile="AGENTS.md (итоговый)",
            )
        ),
        encoding="utf-8",
    )
    artifacts["status"] = "available"
    artifacts["result"] = RESULT_AGENTS_ARTIFACT
    artifacts["diff"] = AGENTS_DIFF_ARTIFACT
    return artifacts


def run_case(
    project: Path,
    image: str,
    command: Sequence[str] | None,
    results_dir: Path,
    timeout: float,
    *,
    docker_executable: str = "docker",
    popen_factory: PopenFactory = subprocess.Popen,
    run_factory: RunFactory = subprocess.run,
    scenario_path: Path = SCENARIO_PATH,
    check_path: Path = CHECK_PATH,
    mode: str = COMMAND_MODE,
    model: str | None = None,
    effort: str | None = None,
    prepare: bool = False,
) -> tuple[dict[str, Any], Path]:
    project = project.resolve()
    results_dir = results_dir.resolve()
    if not project.is_dir():
        raise ValueError(f"Тестовый проект не найден: {project}")
    if (
        not image.strip()
        or image.startswith("-")
        or any(character.isspace() for character in image)
    ):
        raise ValueError("Docker-образ должен быть одним именем без пробелов и ведущих параметров")
    if mode not in {COMMAND_MODE, CODEX_MODE}:
        raise ValueError(f"Неизвестный режим запуска: {mode}")
    if mode == COMMAND_MODE:
        if not command:
            raise ValueError("Команда контейнера не может быть пустой")
        if model is not None or effort is not None or prepare:
            raise ValueError("Параметры Codex доступны только в режиме codex")
    else:
        if command:
            raise ValueError("В режиме codex команда задаётся самим запускателем")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("В режиме codex требуется непустой --model")
        if not isinstance(effort, str) or not effort.strip():
            raise ValueError("В режиме codex требуется непустой --effort")
    if timeout <= 0:
        raise ValueError("Тайм-аут должен быть положительным")
    if paths_overlap(project, results_dir):
        raise ValueError("Каталог результатов не должен пересекаться с проектом")

    scenario_id, task = load_task(scenario_path)
    before = file_snapshot(project)
    source_content = (project / AGENTS_PATH).read_bytes()
    results_dir.mkdir(parents=True, exist_ok=True)
    run_dir = results_dir / f"run-{uuid.uuid4().hex}"
    run_dir.mkdir()
    write_json(run_dir / "source-snapshot.json", before)
    (run_dir / SOURCE_AGENTS_ARTIFACT).write_bytes(source_content)

    container_name = f"compatibility-{uuid.uuid4().hex}"
    codex_artifacts = {
        "jsonl": None,
        "final_answer": None,
        "final_answer_status": "not_applicable",
    }
    with tempfile.TemporaryDirectory(prefix="compatibility-work-") as temporary:
        workspace = Path(temporary) / "project"
        shutil.copytree(project, workspace, symlinks=False)
        output_workspace = None
        if mode == CODEX_MODE:
            output_workspace = Path(temporary) / "codex-output"
            output_workspace.mkdir()
        owner = workspace.stat()
        if owner.st_uid == 0:
            raise ValueError(
                "Рабочая копия принадлежит UID 0; запускатель не переходит к root автоматически"
            )
        container_command = (
            list(command)
            if mode == COMMAND_MODE
            else codex_command(model or "", effort or "")
        )
        docker_argv = docker_command(
            docker_executable,
            container_name,
            workspace,
            image,
            container_command,
            owner.st_uid,
            owner.st_gid,
            output_workspace=output_workspace,
        )
        if mode == CODEX_MODE:
            write_json(
                run_dir / CODEX_COMMAND_ARTIFACT,
                {
                    "docker_argv": docker_argv,
                    "codex_argv": container_command,
                    "task_source": f"{scenario_path}:prompt",
                    "task_via_stdin": True,
                    "task_runner_prefix": "",
                    "model": model,
                    "effort": effort,
                },
            )
        if prepare:
            execution = prepared_execution()
            after_snapshot_error = None
            after = before
            changed = []
            unexpected = []
            agents_artifacts = {
                "status": "not_run",
                "source": SOURCE_AGENTS_ARTIFACT,
                "result": None,
                "diff": None,
                "violations": [],
            }
            file_check = {
                "status": "not_run",
                "exit_code": None,
                "duration_seconds": 0,
                "stdout": "",
                "stderr": "Проверка пропущена: режим подготовки не выполняет задачу.",
            }
        else:
            execution = run_container(
                docker_argv,
                task,
                timeout,
                popen_factory,
                docker_executable,
                run_factory,
            )
            after_snapshot_error = None
            try:
                after = file_snapshot(workspace)
            except (OSError, ValueError) as exc:
                after_snapshot_error = str(exc)
                after = file_snapshot(workspace, skip_unsafe=True)
            changed = changed_paths(before, after)
            unexpected = sorted(set(changed) - ALLOWED_CHANGED_PATHS)
            agents_artifacts = save_agents_artifacts(run_dir, workspace, source_content)
            if agents_artifacts["status"] == "available":
                file_check = run_checker(workspace, check_path)
            else:
                file_check = {
                    "status": "not_run",
                    "exit_code": None,
                    "duration_seconds": 0,
                    "stdout": "",
                    "stderr": "Проверка пропущена: итоговый AGENTS.md недоступен.",
                }
            if mode == CODEX_MODE:
                codex_artifacts = save_codex_artifacts(
                    run_dir, output_workspace, execution  # type: ignore[arg-type]
                )
        source_after = file_snapshot(project)
        source_changed = changed_paths(before, source_after)

    (run_dir / "stdout.txt").write_text(execution["stdout"], encoding="utf-8")
    (run_dir / "stderr.txt").write_text(execution["stderr"], encoding="utf-8")
    status = "prepared" if prepare else "passed"
    if not prepare and execution["status"] in {"timed_out", "interrupted"}:
        status = execution["status"]
    elif not prepare and (execution["status"] != "completed" or execution["exit_code"] != 0):
        status = "failed"
    elif not prepare and (
        after_snapshot_error
        or agents_artifacts["violations"]
        or unexpected
        or source_changed
        or file_check["status"] != "passed"
        or execution["cleanup"]["errors"]
        or (mode == CODEX_MODE and codex_artifacts["final_answer_status"] != "available")
    ):
        status = "failed"

    report = {
        "scenario_id": scenario_id,
        "status": status,
        "mode": mode,
        "preparation": prepare,
        "execution": execution,
        "container": {
            "image": image,
            "command": container_command,
            "name": container_name,
            "user": f"{owner.st_uid}:{owner.st_gid}",
            "workdir": "/workspace",
            "network": "none",
            "rootfs": "read-only",
            "embedded_sandbox": (
                "disabled by --dangerously-bypass-approvals-and-sandbox"
                if mode == CODEX_MODE
                else None
            ),
            "external_isolation": "Docker",
        },
        "codex": (
            {
                "version": CODEX_VERSION,
                "requested_model": model,
                "requested_effort": effort,
                "model_confirmed": False,
                "effort_confirmed": False,
                "json_journal": CODEX_JSONL_ARTIFACT,
                "final_answer": codex_artifacts["final_answer"],
            }
            if mode == CODEX_MODE
            else None
        ),
        "task": {
            "source": f"{scenario_path}:prompt",
            "via_stdin": mode == CODEX_MODE,
            "runner_prefix": "",
            "sent": not prepare,
        },
        "changed_paths": changed,
        "unexpected_changes": unexpected,
        "source_unchanged": not source_changed,
        "source_changed_paths": source_changed,
        "workspace_snapshot_error": after_snapshot_error,
        "file_check": file_check,
        "agents_artifacts": agents_artifacts,
        "skill_application": {
            "verified": False,
            "note": (
                "Разбор свидетельств применения навыка пока не реализован."
                if mode == CODEX_MODE
                else "Запущена тестовая заглушка. Применение навыка не проверялось."
            ),
        },
        "artifacts": {
            "source_snapshot": "source-snapshot.json",
            "source_agents": SOURCE_AGENTS_ARTIFACT,
            "result_agents": agents_artifacts["result"],
            "agents_diff": agents_artifacts["diff"],
            "stdout": "stdout.txt",
            "stderr": "stderr.txt",
            "codex_jsonl": codex_artifacts["jsonl"],
            "codex_final_answer": codex_artifacts["final_answer"],
            "codex_command": CODEX_COMMAND_ARTIFACT if mode == CODEX_MODE else None,
            "report": "report.json",
        },
    }
    report_path = run_dir / "report.json"
    write_json(report_path, report)
    return report, report_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--timeout", required=True, type=float)
    parser.add_argument(
        "--mode",
        choices=(COMMAND_MODE, CODEX_MODE),
        default=COMMAND_MODE,
        help="Режим запуска: произвольная команда или Codex CLI",
    )
    parser.add_argument("--model", help="Обязательная модель в режиме codex")
    parser.add_argument("--effort", help="Обязательное усилие в режиме codex")
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Показать запуск Codex без создания контейнера и выполнения задачи",
    )
    parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="Команда и её аргументы после всех параметров запускателя",
    )
    args = parser.parse_args(argv)
    if args.mode == COMMAND_MODE:
        if not args.command:
            parser.error("в режиме command после --command нужен хотя бы один аргумент")
        if args.model or args.effort or args.prepare:
            parser.error("--model, --effort и --prepare доступны только в режиме codex")
    else:
        if args.command:
            parser.error("в режиме codex параметр --command не используется")
        if not args.model or not args.model.strip():
            parser.error("в режиме codex обязателен непустой --model")
        if not args.effort or not args.effort.strip():
            parser.error("в режиме codex обязателен непустой --effort")
    if args.timeout <= 0:
        parser.error("--timeout должен быть положительным")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    docker = shutil.which("docker")
    if docker is None:
        print("Docker не найден. Запускатель не выполняет автоматическую установку.", file=sys.stderr)
        return 2
    try:
        report, report_path = run_case(
            args.project,
            args.image,
            args.command if args.mode == COMMAND_MODE else None,
            args.results_dir,
            args.timeout,
            docker_executable=docker,
            mode=args.mode,
            model=args.model,
            effort=args.effort,
            prepare=args.prepare,
        )
    except (OSError, ValueError) as exc:
        print(f"Запуск сценария не подготовлен: {exc}", file=sys.stderr)
        return 2
    print(report_path)
    return 0 if report["status"] in {"passed", "prepared"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

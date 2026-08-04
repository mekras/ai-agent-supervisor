#!/usr/bin/env python3
"""Проверки валидатора границы проекций APM и индекса Git."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = (
    ROOT
    / ".apm"
    / "skills"
    / "ai-setup-apm"
    / "scripts"
    / "validate-apm-git-boundary.py"
)


def run_validator(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(project)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def create_project() -> Path:
    project = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    return project


def write_lock(project: Path, dependencies: list[dict[str, object]]) -> None:
    lines = [
        "lockfile_version: '2'",
        "generated_at: '2026-08-05T00:00:00+00:00'",
        "apm_version: 0.27.0",
        "dependencies:",
    ]
    for item in dependencies:
        lines.append(f"- repo_url: {item['name']}")
        lines.append(f"  name: {str(item['name']).split('/')[-1]}")
        lines.append("  host: example.invalid")
        lines.append("  resolved_commit: 0000000000000000000000000000000000000000")
        lines.append("  resolved_ref: 1.0.0")
        lines.append("  version: 1.0.0")
        lines.append("  package_type: apm_package")
        lines.append("  deployed_files:")
        lines.extend(f"  - {path}" for path in item["deployed_files"])
    (project / "apm.lock.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_file(project: Path, path: str) -> None:
    target = project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("fixture\n", encoding="utf-8")


def track(project: Path, *paths: str) -> None:
    subprocess.run(["git", "add", "--", *paths], cwd=project, check=True)


def dependency(name: str, *paths: str) -> dict[str, object]:
    return {"name": name, "deployed_files": list(paths)}


def test_tracked_dependency_file_fails() -> None:
    project = create_project()
    try:
        path = ".agents/skills/dependency/SKILL.md"
        write_file(project, path)
        write_lock(project, [dependency("example/dependency", path)])
        track(project, path)

        result = run_validator(project)
        assert result.returncode == 1
        assert path in result.stderr
        assert "example/dependency" in result.stderr
        assert "Удалите файл из индекса Git" in result.stderr
        assert ".gitignore" in result.stderr
    finally:
        shutil.rmtree(project)


def test_untracked_dependency_file_passes() -> None:
    project = create_project()
    try:
        path = ".agents/skills/dependency/SKILL.md"
        write_file(project, path)
        write_lock(project, [dependency("example/dependency", path)])

        result = run_validator(project)
        assert result.returncode == 0, result.stderr
        assert "не найдено" in result.stdout
    finally:
        shutil.rmtree(project)


def test_root_apm_file_and_project_client_file_pass() -> None:
    project = create_project()
    try:
        own_path = ".apm/skills/own/SKILL.md"
        project_path = ".claude/project instructions.md"
        dependency_path = ".agents/skills/dependency/SKILL.md"
        for path in (own_path, project_path, dependency_path):
            write_file(project, path)
        write_lock(project, [dependency("example/dependency", dependency_path)])
        track(project, own_path, project_path)

        result = run_validator(project)
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project)


def test_multiple_owners_and_unicode_paths_are_reported() -> None:
    project = create_project()
    try:
        first = ".claude/skills/пакет один/README.md"
        second = ".codex/skills/package two/SKILL.md"
        for path in (first, second):
            write_file(project, path)
        write_lock(
            project,
            [
                dependency("first-package", first),
                dependency("second-package", second),
            ],
        )
        track(project, first, second)

        result = run_validator(project)
        assert result.returncode == 1
        for value in (first, second, "first-package", "second-package"):
            assert value in result.stderr
    finally:
        shutil.rmtree(project)


def test_missing_lockfile_and_git_repository_report_diagnostics() -> None:
    project = Path(tempfile.mkdtemp())
    try:
        missing_lock = run_validator(project)
        assert missing_lock.returncode == 2
        assert "не найден файл блокировки APM" in missing_lock.stderr
        assert "Traceback" not in missing_lock.stderr

        write_lock(project, [])
        missing_git = run_validator(project)
        assert missing_git.returncode == 2
        assert "репозиторий Git недоступен" in missing_git.stderr
        assert "Traceback" not in missing_git.stderr
    finally:
        shutil.rmtree(project)


def main() -> int:
    test_tracked_dependency_file_fails()
    test_untracked_dependency_file_passes()
    test_root_apm_file_and_project_client_file_pass()
    test_multiple_owners_and_unicode_paths_are_reported()
    test_missing_lockfile_and_git_repository_report_diagnostics()
    print("Проверки границы проекций APM и Git пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

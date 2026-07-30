#!/usr/bin/env python3
"""Не допускает отслеживание Git проекций зависимостей APM."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - зависит от окружения проекта-потребителя
    yaml = None


def error(message: str) -> int:
    print(f"Ошибка проверки границы APM и Git: {message}", file=sys.stderr)
    return 2


def read_lockfile(project_root: Path) -> dict[str, list[str]] | None:
    lockfile = project_root / "apm.lock.yaml"
    if not lockfile.is_file():
        error(f"не найден файл блокировки APM: {lockfile}")
        return None

    if yaml is None:
        error("для чтения apm.lock.yaml нужен установленный пакет PyYAML")
        return None

    try:
        data = yaml.safe_load(lockfile.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        error(f"не удалось прочитать {lockfile}: {exc}")
        return None

    if not isinstance(data, dict):
        error(f"некорректный формат {lockfile}: ожидается YAML-объект")
        return None

    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list):
        error(f"некорректный формат {lockfile}: поле dependencies должно быть списком")
        return None

    owners_by_path: dict[str, list[str]] = defaultdict(list)
    for index, dependency in enumerate(dependencies, start=1):
        if not isinstance(dependency, dict):
            error(f"некорректный формат {lockfile}: зависимость №{index} должна быть объектом")
            return None
        name = dependency.get("name")
        deployed_files = dependency.get("deployed_files")
        if not isinstance(name, str) or not name:
            error(f"некорректный формат {lockfile}: у зависимости №{index} нет имени")
            return None
        if not isinstance(deployed_files, list) or not all(
            isinstance(path, str) and path for path in deployed_files
        ):
            error(
                f"некорректный формат {lockfile}: deployed_files зависимости {name!r} "
                "должен быть списком непустых путей"
            )
            return None
        for path in deployed_files:
            candidate = Path(path)
            if candidate.is_absolute() or ".." in candidate.parts:
                error(
                    f"некорректный путь развёртывания зависимости {name!r}: {path!r}"
                )
                return None
            owners_by_path[path].append(name)
    return owners_by_path


def tracked_paths(project_root: Path) -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=project_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        error(f"не удалось запустить Git в {project_root}: {exc}")
        return None

    if result.returncode != 0:
        details = result.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {details}" if details else ""
        error(f"репозиторий Git недоступен в {project_root}{suffix}")
        return None

    return {
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    }


def validate(project_root: Path) -> int:
    owners_by_path = read_lockfile(project_root)
    if owners_by_path is None:
        return 2
    tracked = tracked_paths(project_root)
    if tracked is None:
        return 2

    violations = [
        (path, owner)
        for path, owners in owners_by_path.items()
        if path in tracked
        for owner in owners
    ]
    if violations:
        print("Найдены отслеживаемые проекции зависимостей APM:", file=sys.stderr)
        for path, owner in sorted(violations):
            print(
                f"- {path} (пакет: {owner}). Удалите файл из индекса Git и "
                "добавьте подходящее правило в .gitignore.",
                file=sys.stderr,
            )
        return 1

    print("Отслеживаемых Git проекций зависимостей APM не найдено.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Проверяет, что Git не отслеживает файлы, развёрнутые зависимостями APM."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        type=Path,
        help="корень проверяемого проекта, по умолчанию текущий каталог",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        return error(f"не найден каталог проекта: {project_root}")
    return validate(project_root)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Запустить контрактные проверки публичных Python-скриптов навыков.

Каждый Python-скрипт первого уровня в ``scripts/`` должен иметь успешный
рабочий сценарий в ``evals/script-contract-tests.json``. Сценарий запускает
поставляемую команду в копии фикстуры и проверяет наблюдаемый результат.
Ожидаемые отказы могут дополнять, но не заменять успешный сценарий.
Если в контракте есть независимая ошибка полноты, запускатель всё равно
выполняет корректно описанные сценарии и сообщает все найденные ошибки за один
запуск.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


FIXTURE_PREFIX = Path("evals/script-fixtures")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запустить контрактные проверки Python-скриптов навыков.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".apm/skills")],
        help="Каталоги навыков или отдельные навыки.",
    )
    return parser.parse_args()


def skill_directories(paths: list[Path]) -> list[Path]:
    result: set[Path] = set()
    for path in paths:
        if (path / "SKILL.md").is_file():
            result.add(path)
        elif path.is_dir():
            result.update(file.parent for file in path.rglob("SKILL.md"))
    return sorted(result)


def public_python_scripts(skill: Path) -> list[Path]:
    scripts = skill / "scripts"
    if not scripts.is_dir():
        return []
    return sorted(path for path in scripts.glob("*.py") if path.is_file())


def safe_relative(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        return None
    return path


def string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        return None
    return value


def command_list(value: Any) -> list[list[str]] | None:
    if not isinstance(value, list):
        return None
    result: list[list[str]] = []
    for item in value:
        command = string_list(item)
        if command is None or not command:
            return None
        result.append(command)
    return result


def is_runnable_case(skill: Path, case: dict[str, Any]) -> bool:
    """Проверить, достаточно ли данных случая для безопасного запуска."""
    script = safe_relative(case.get("script"))
    fixture = safe_relative(case.get("fixture"))
    command = string_list(case.get("command"))
    return (
        script is not None
        and script in {path.relative_to(skill) for path in public_python_scripts(skill)}
        and fixture is not None
        and fixture.is_relative_to(FIXTURE_PREFIX)
        and (skill / fixture).is_dir()
        and command is not None
        and command
        and command[0] == "{python}"
        and "{script}" in command
        and not any(item in {"--help", "-h"} for item in command)
        and command_list(case.get("prepare", [])) is not None
        and isinstance(case.get("expect"), dict)
    )


def load_cases(skill: Path, errors: list[str]) -> list[dict[str, Any]]:
    contract = skill / "evals" / "script-contract-tests.json"
    if not contract.is_file():
        if public_python_scripts(skill):
            errors.append(f"{skill}: нет {contract.relative_to(skill)}")
        return []
    try:
        data = json.loads(contract.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{contract}: JSON не разобран: {exc}")
        return []
    if not isinstance(data, dict) or data.get("version") != 1:
        errors.append(f"{contract}: нужен объект с version: 1")
        return []
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append(f"{contract}: нужен непустой массив cases")
        return []
    valid_cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    covered: set[Path] = set()
    successfully_covered: set[Path] = set()
    expected_scripts = {path.relative_to(skill) for path in public_python_scripts(skill)}
    for index, case in enumerate(cases):
        label = f"{contract}: cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: должен быть объект")
            continue
        identifier = case.get("id")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"{label}.id: нужна непустая строка")
        elif identifier in seen_ids:
            errors.append(f"{label}.id: повтор {identifier!r}")
        else:
            seen_ids.add(identifier)
        script = safe_relative(case.get("script"))
        if script is None or script not in expected_scripts:
            errors.append(f"{label}.script: нужен Python-скрипт первого уровня scripts/")
        else:
            covered.add(script)
        fixture = safe_relative(case.get("fixture"))
        if fixture is None or not fixture.is_relative_to(FIXTURE_PREFIX):
            errors.append(
                f"{label}.fixture: нужен каталог внутри {FIXTURE_PREFIX.as_posix()}/",
            )
        elif not (skill / fixture).is_dir():
            errors.append(f"{label}.fixture: каталог не найден")
        command = string_list(case.get("command"))
        if command is None or not command:
            errors.append(f"{label}.command: нужен непустой массив строк")
        elif command[0] != "{python}" or "{script}" not in command:
            errors.append(
                f"{label}.command: команда должна запускать {{python}} и {{script}}",
            )
        elif any(item in {"--help", "-h"} for item in command):
            errors.append(f"{label}.command: --help не является контрактным сценарием")
        prepare = case.get("prepare", [])
        if command_list(prepare) is None:
            errors.append(
                f"{label}.prepare: нужен массив непустых массивов команд",
            )
        expect = case.get("expect")
        if not isinstance(expect, dict):
            errors.append(f"{label}.expect: нужен объект с наблюдаемым результатом")
        else:
            checks = 0
            exit_code = expect.get("exit_code", 0)
            if not isinstance(exit_code, int) or exit_code < 0:
                errors.append(f"{label}.expect.exit_code: нужен неотрицательный код")
            elif exit_code == 0 and script is not None:
                successfully_covered.add(script)
            for key in ("stdout_contains", "stderr_contains"):
                value = expect.get(key)
                if value is not None:
                    values = string_list(value)
                    if values is None or not values:
                        errors.append(f"{label}.expect.{key}: нужен непустой массив строк")
                    else:
                        checks += len(values)
            files = expect.get("files")
            if files is not None:
                if not isinstance(files, list) or not files:
                    errors.append(f"{label}.expect.files: нужен непустой массив")
                else:
                    for file_index, item in enumerate(files):
                        file_label = f"{label}.expect.files[{file_index}]"
                        if not isinstance(item, dict) or safe_relative(item.get("path")) is None:
                            errors.append(f"{file_label}.path: нужен безопасный относительный путь")
                            continue
                        if item.get("json") is not None and not isinstance(item["json"], bool):
                            errors.append(f"{file_label}.json: допускается только true или false")
                        contains = item.get("contains")
                        if contains is not None and (not isinstance(contains, str) or not contains):
                            errors.append(f"{file_label}.contains: нужна непустая строка")
                        checks += 1
            if not checks:
                errors.append(f"{label}.expect: нужен хотя бы один проверяемый результат")
        if is_runnable_case(skill, case):
            valid_cases.append(case)
    missing = sorted(expected_scripts - covered)
    if missing:
        errors.append(
            f"{contract}: нет контрактного сценария для: "
            + ", ".join(path.as_posix() for path in missing),
        )
    missing_success = sorted(expected_scripts - successfully_covered)
    if missing_success:
        errors.append(
            f"{contract}: нет успешного рабочего сценария для: "
            + ", ".join(path.as_posix() for path in missing_success),
        )
    return valid_cases


def render_command(command: list[str], script: Path, fixture: Path) -> list[str]:
    values = {
        "{python}": sys.executable,
        "{script}": str(script),
        "{fixture}": str(fixture),
    }
    return [
        item.replace("{python}", values["{python}"])
        .replace("{script}", values["{script}"])
        .replace("{fixture}", values["{fixture}"])
        for item in command
    ]


def verify_output(case: dict[str, Any], fixture: Path) -> list[str]:
    expect = case["expect"]
    errors: list[str] = []
    for item in expect.get("files", []):
        path = fixture / item["path"]
        if not path.is_file():
            errors.append(f"не создан ожидаемый файл {item['path']}")
            continue
        text = path.read_text(encoding="utf-8")
        if item.get("json"):
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{item['path']}: JSON не разобран: {exc}")
        contains = item.get("contains")
        if contains and contains not in text:
            errors.append(f"{item['path']}: нет ожидаемого текста {contains!r}")
    return errors


def run_case(skill: Path, case: dict[str, Any]) -> list[str]:
    source_fixture = skill / case["fixture"]
    script = (skill / case["script"]).resolve()
    with tempfile.TemporaryDirectory(prefix="проверка скрипта ") as temporary:
        fixture = Path(temporary) / "fixture"
        shutil.copytree(source_fixture, fixture)
        for index, prepare in enumerate(case.get("prepare", [])):
            prepared_command = render_command(prepare, script, fixture)
            try:
                prepared = subprocess.run(
                    prepared_command,
                    cwd=fixture,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return [f"не удалось запустить подготовительную команду {index}: {exc}"]
            if prepared.returncode != 0:
                details = prepared.stderr.strip() or prepared.stdout.strip()
                return [
                    f"подготовительная команда {index} завершилась с кодом "
                    f"{prepared.returncode}: {details}",
                ]
        command = render_command(case["command"], script, fixture)
        try:
            result = subprocess.run(
                command,
                cwd=fixture,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [f"не удалось выполнить контрактный сценарий за 60 с: {exc}"]
        errors: list[str] = []
        expect = case["expect"]
        expected_exit_code = expect.get("exit_code", 0)
        if result.returncode != expected_exit_code:
            errors.append(
                f"команда завершилась с кодом {result.returncode}, ожидался "
                f"{expected_exit_code}: "
                f"{result.stderr.strip() or result.stdout.strip()}",
            )
            return errors
        for value in expect.get("stdout_contains", []):
            if value not in result.stdout:
                errors.append(f"stdout не содержит {value!r}")
        for value in expect.get("stderr_contains", []):
            if value not in result.stderr:
                errors.append(f"stderr не содержит {value!r}")
        errors.extend(verify_output(case, fixture))
        return errors


def main() -> int:
    args = parse_args()
    missing = [str(path) for path in args.paths if not path.exists()]
    if missing:
        print(f"Пути не найдены: {', '.join(missing)}", file=sys.stderr)
        return 2
    errors: list[str] = []
    cases_by_skill = {
        skill: load_cases(skill, errors)
        for skill in skill_directories(args.paths)
    }
    run_errors: list[str] = []
    count = 0
    for skill, cases in cases_by_skill.items():
        for case in cases:
            count += 1
            for error in run_case(skill, case):
                run_errors.append(f"{skill}::{case['id']}: {error}")
    all_errors = errors + run_errors
    if all_errors:
        print("\n".join(all_errors), file=sys.stderr)
        return 1
    print(f"Контрактные сценарии скриптов пройдены: {count}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

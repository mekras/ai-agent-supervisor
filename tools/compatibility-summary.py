#!/usr/bin/env python3
"""Проверить и обновить сводку поддержки коллекции в README."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

import yaml

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / ".apm/skills/ai-setup-apm/references/compatibility.yml"
DEFAULT_README = ROOT / "README.md"
START_MARKER = "<!-- compatibility-summary:start -->"
END_MARKER = "<!-- compatibility-summary:end -->"
ENVIRONMENT_IDS = ("codex_cli", "claude_code", "hermes_agent")
CAPABILITY_IDS = (
    "collection_installation",
    "skill_loading_and_availability",
    "project_and_instruction_setup",
    "skill_creation_and_improvement",
    "subagent_setup_and_use",
    "work_analysis_and_result_evaluation",
)
RESULT_LABELS = {
    "passed": "пройдена",
    "failed": "не пройдена",
    "inconclusive": "неопределённая",
}
PACKAGE_PRESENCE_LABELS = {"included": "есть"}
DECLARED_IMPLEMENTATION_LABELS = {
    "documented": "описано в пакете",
    "partial": "описано частично",
    "not_established": "не установлено",
}
PARTICIPATION_LABELS = {
    "participated": "участвовала",
    "not_participated": "не участвовала",
}
VERIFICATION_SUBJECT_LABELS = {
    "agent_runtime": "работа в среде",
    "packaging_tooling": "упаковка и установка через инструментарий",
    "static_review": "статический анализ",
    "stub": "тестовая заглушка, не среда агента",
}


def has_agents_md_runtime_check(data: dict[str, Any], environment_id: str) -> bool:
    for check in data["checks"]:
        environment = check["environment"]
        if (
            check["result"] == "passed"
            and check["verification_subject"] == "agent_runtime"
            and check["capability"] == "project_and_instruction_setup"
            and environment["id"] == environment_id
            and environment["participation"] == "participated"
        ):
            return True
    return False


def has_codex_agents_md_check(data: dict[str, Any]) -> bool:
    return has_agents_md_runtime_check(data, "codex_cli")


def has_hermes_agents_md_check(data: dict[str, Any]) -> bool:
    return has_agents_md_runtime_check(data, "hermes_agent")


def load_registry(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"не удалось прочитать реестр: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("корень реестра должен быть объектом")
    validate_registry(data)
    return data


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 2:
        raise ValueError("schema_version должен быть равен 2")
    scope = data.get("scope")
    if not isinstance(scope, dict) or scope.get("id") != "collection":
        raise ValueError("реестр должен явно описывать всю коллекцию")

    environments = data.get("environments")
    if not isinstance(environments, list):
        raise ValueError("environments должен быть списком")
    environment_ids = [item.get("id") for item in environments if isinstance(item, dict)]
    if tuple(environment_ids) != ENVIRONMENT_IDS:
        raise ValueError("состав и порядок сред не совпадают с договором реестра")
    if any(
        not isinstance(item.get("name"), str)
        or item.get("declared_support") is not True
        or not isinstance(item.get("user_summary"), str)
        or not item["user_summary"].strip()
        for item in environments
        if isinstance(item, dict)
    ):
        raise ValueError("каждая среда должна иметь имя, заявленную поддержку и краткую сводку")

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list):
        raise ValueError("capabilities должен быть списком")
    capability_ids = [item.get("id") for item in capabilities if isinstance(item, dict)]
    if tuple(capability_ids) != CAPABILITY_IDS:
        raise ValueError("состав и порядок возможностей не совпадают с договором реестра")
    for item in capabilities:
        if not isinstance(item, dict):
            raise ValueError("каждая возможность должна быть объектом")
        if not isinstance(item.get("name"), str):
            raise ValueError(f"{item.get('id')}: отсутствует имя")
        if item.get("target_environments") != list(ENVIRONMENT_IDS):
            raise ValueError(f"{item.get('id')}: охват должен включать все три среды")
        package_presence = item.get("package_presence")
        if not isinstance(package_presence, dict):
            raise ValueError(f"{item.get('id')}: отсутствует наличие в пакете")
        if package_presence.get("status") not in PACKAGE_PRESENCE_LABELS:
            raise ValueError(f"{item.get('id')}: неизвестное состояние наличия в пакете")
        validate_basis(item["id"], package_presence.get("basis"), "наличия в пакете")
        implementation = item.get("declared_implementation")
        if not isinstance(implementation, dict) or set(implementation) != set(ENVIRONMENT_IDS):
            raise ValueError(f"{item.get('id')}: нужно заявленное состояние для каждой среды")
        for environment_id in ENVIRONMENT_IDS:
            state = implementation[environment_id]
            if not isinstance(state, dict) or state.get("status") not in DECLARED_IMPLEMENTATION_LABELS:
                raise ValueError(f"{item.get('id')}/{environment_id}: неизвестное заявленное состояние")
            status = state["status"]
            if status in {"documented", "partial"}:
                validate_basis(f"{item.get('id')}/{environment_id}", state.get("basis"), "заявленного состояния")
            if status == "partial" and not isinstance(state.get("gap"), str):
                raise ValueError(f"{item.get('id')}/{environment_id}: для partial нужен пробел")
            if status == "not_established" and not isinstance(state.get("note"), str):
                raise ValueError(f"{item.get('id')}/{environment_id}: для not_established нужна причина")

    checks = data.get("checks")
    if not isinstance(checks, list):
        raise ValueError("checks должен быть списком")
    known_capabilities = set(CAPABILITY_IDS)
    known_environments = set(ENVIRONMENT_IDS)
    seen_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("каждая проверка должна быть объектом")
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id or check_id in seen_ids:
            raise ValueError("идентификаторы проверок должны быть непустыми и уникальными")
        seen_ids.add(check_id)
        date_value = check.get("date")
        if not isinstance(date_value, (dt.date, dt.datetime, str)):
            raise ValueError(f"{check_id}: отсутствует дата")
        try:
            dt.date.fromisoformat(str(date_value))
        except ValueError as exc:
            raise ValueError(f"{check_id}: дата должна быть в формате ГГГГ-ММ-ДД") from exc
        if not isinstance(check.get("collection_version"), str):
            raise ValueError(f"{check_id}: отсутствует версия коллекции")
        environment = check.get("environment")
        if not isinstance(environment, dict):
            raise ValueError(f"{check_id}: отсутствует среда")
        if environment.get("id") not in known_environments:
            raise ValueError(f"{check_id}: неизвестная среда")
        if not isinstance(environment.get("version"), str):
            raise ValueError(f"{check_id}: отсутствует версия среды")
        participation = environment.get("participation")
        if participation not in PARTICIPATION_LABELS:
            raise ValueError(f"{check_id}: нужно участие среды")
        if participation == "not_participated" and environment["version"] != "not_participated":
            raise ValueError(f"{check_id}: неучаствующая среда не может иметь обычную версию")
        if participation == "participated" and environment["version"] == "not_participated":
            raise ValueError(f"{check_id}: участвующая среда не может иметь not_participated")
        if check.get("capability") not in known_capabilities:
            raise ValueError(f"{check_id}: неизвестная возможность")
        for field in ("conditions", "method"):
            if not isinstance(check.get(field), str) or not check[field].strip():
                raise ValueError(f"{check_id}: поле {field} должно быть непустым")
        verification_subject = check.get("verification_subject")
        if verification_subject not in VERIFICATION_SUBJECT_LABELS:
            raise ValueError(f"{check_id}: неизвестен предмет проверки")
        if participation == "not_participated" and verification_subject == "agent_runtime":
            raise ValueError(f"{check_id}: неучаствующая среда не может иметь проверку runtime")
        if check.get("result") not in RESULT_LABELS:
            raise ValueError(f"{check_id}: неизвестный результат")
        if not isinstance(check.get("scope"), str) or not check["scope"].strip():
            raise ValueError(f"{check_id}: отсутствует граница проверки")
        evidence = check.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise ValueError(f"{check_id}: нужно хотя бы одно свидетельство")


def validate_basis(identifier: str, basis: Any, label: str) -> None:
    if not isinstance(basis, list) or not basis or not all(
        isinstance(item, str) and item.strip() for item in basis
    ):
        raise ValueError(f"{identifier}: нужно основание {label}")


def render_summary(data: dict[str, Any]) -> str:
    validate_registry(data)
    has_codex_check = has_codex_agents_md_check(data)
    has_hermes_check = has_hermes_agents_md_check(data)
    environment_names = [item["name"] for item in data["environments"]]
    if len(environment_names) > 1:
        environment_list = ", ".join(environment_names[:-1]) + " и " + environment_names[-1]
    else:
        environment_list = environment_names[0]
    lines = [
        START_MARKER,
        "## Поддерживаемые среды",
        "",
        f"Коллекция развивает поддержку {environment_list}.",
        "",
        "| Среда | Текущее состояние |",
        "| --- | --- |",
    ]
    lines.extend(
        [
            f"| {item['name']} | {item['user_summary']} |" for item in data["environments"]
        ]
    )
    if has_codex_check and has_hermes_check:
        lines.extend(
            [
                "",
                "В Codex CLI и локальном кандидате коллекции для Hermes Agent проверена правка AGENTS.md с помощью установленного навыка. Границы остальных проверок указаны в реестре.",
                "",
            ]
        )
    elif has_codex_check:
        lines.extend(
            [
                "",
                "В Codex CLI проверена правка AGENTS.md с помощью установленного навыка ai-agents-md-maintenance. Проверки остальных навыков и сред ещё предстоят.",
                "",
            ]
        )
    elif has_hermes_check:
        lines.extend(
            [
                "",
                "В локальном кандидате коллекции для Hermes Agent проверена правка AGENTS.md с помощью установленного навыка. Границы остальных проверок указаны в реестре.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Проверки поведения навыков в реальных средах пока не отражены в реестре. Проверка установки через APM не подтверждает работу самих навыков.",
            ]
        )
    lines.extend(
        [
            "",
            "Подробные сведения приведены в [реестре поддержки](.apm/skills/ai-setup-apm/references/compatibility.yml).",
            "",
            END_MARKER,
        ]
    )
    return "\n".join(lines) + "\n"


def replace_block(readme: str, block: str) -> str:
    start = readme.find(START_MARKER)
    end = readme.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        raise ValueError("в README не найдены согласованные маркеры сводки")
    end += len(END_MARKER)
    return readme[:start] + block.rstrip("\n") + readme[end:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить или обновить сводку поддержки коллекции.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="записать сводку в README")
    mode.add_argument("--check", action="store_true", help="проверить сводку без записи")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = load_registry(args.registry)
        readme = args.readme.read_text(encoding="utf-8")
        expected = replace_block(readme, render_summary(data))
    except (OSError, ValueError) as exc:
        print(f"Ошибка сводки поддержки: {exc}", file=sys.stderr)
        return 2
    if args.check:
        if expected != readme:
            print("Сводка README устарела. Запустите режим --write.", file=sys.stderr)
            return 1
        print("Сводка README соответствует реестру.")
        return 0
    if expected != readme:
        args.readme.write_text(expected, encoding="utf-8")
        print(f"Сводка README обновлена: {args.readme}")
    else:
        print("Сводка README уже соответствует реестру.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

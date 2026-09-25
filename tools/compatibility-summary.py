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
TOOLING_LABELS = {"apm_cli": "APM CLI"}
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
        for item in environments
        if isinstance(item, dict)
    ):
        raise ValueError("каждая среда должна иметь имя и заявленную поддержку")

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


def check_date(check: dict[str, Any]) -> dt.date:
    return dt.date.fromisoformat(str(check["date"]))


def latest_checks(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for check in data["checks"]:
        key = (check["capability"], check["environment"]["id"])
        previous = latest.get(key)
        if previous is None or check_date(check) >= check_date(previous):
            latest[key] = check
    return latest


def environment_name(data: dict[str, Any], environment_id: str) -> str:
    return next(item["name"] for item in data["environments"] if item["id"] == environment_id)


def capability_name(data: dict[str, Any], capability_id: str) -> str:
    return next(item["name"] for item in data["capabilities"] if item["id"] == capability_id)


def environment_version(check: dict[str, Any]) -> str:
    environment = check["environment"]
    if environment["participation"] == "not_participated":
        parts = ["среда не участвовала"]
    else:
        version = "неизвестна" if environment["version"] == "unknown" else environment["version"]
        parts = [f"версия среды: {version}"]
    tooling = environment.get("tooling", {})
    if isinstance(tooling, dict):
        parts.extend(f"{TOOLING_LABELS.get(key, key)}: {value}" for key, value in tooling.items())
    return ", ".join(parts)


def check_cell(check: dict[str, Any] | None) -> str:
    if check is None:
        return "нет записей"
    if check["environment"]["participation"] == "not_participated":
        return f"среда не участвовала, {environment_version(check)}"
    result = RESULT_LABELS[check["result"]]
    return (
        f"{result}, {check['date']}, "
        f"коллекция {check['collection_version']}, {environment_version(check)}"
    )


def source_links(paths: list[str]) -> str:
    return ", ".join(f"[{path}]({path})" for path in paths)


def render_implementation_basis(data: dict[str, Any]) -> list[str]:
    lines = ["### Основания заявленного состояния", ""]
    for capability in data["capabilities"]:
        package = capability["package_presence"]
        lines.append(
            f"- **{capability['name']}**. В пакете: {PACKAGE_PRESENCE_LABELS[package['status']]}. "
            f"Основания: {source_links(package['basis'])}."
        )
        package_basis = set(package["basis"])
        grouped: dict[tuple[str, tuple[str, ...], str], list[str]] = {}
        for environment_id in ENVIRONMENT_IDS:
            state = capability["declared_implementation"][environment_id]
            key = (
                state["status"],
                tuple(path for path in state.get("basis", []) if path not in package_basis),
                state.get("gap", state.get("note", "")),
            )
            grouped.setdefault(key, []).append(environment_name(data, environment_id))
        for (status, basis, explanation), environments in grouped.items():
            environment_text = ", ".join(environments)
            detail = f" Пробел: {explanation}" if status == "partial" else ""
            if status == "not_established":
                detail = f" Причина: {explanation}"
            basis_text = f" Основание: {source_links(list(basis))}." if basis else ""
            lines.append(
                f"  - {environment_text} — {DECLARED_IMPLEMENTATION_LABELS[status]}."
                f"{detail}{basis_text}"
            )
    return lines


def render_summary(data: dict[str, Any]) -> str:
    validate_registry(data)
    latest = latest_checks(data)
    capabilities = {item["id"]: item for item in data["capabilities"]}
    lines = [
        START_MARKER,
        "## Состояние поддержки коллекции",
        "",
        "Реестр описывает поддержку всей коллекции навыков и отдельно хранит наличие в пакете, заявленное по материалам пакета состояние и результаты проверок.",
        "Заявленное состояние по материалам пакета не подтверждает загрузку навыков и их работу в реальной среде. «Не установлено» означает, что даже это состояние не выяснено.",
        "Проверка установки, упаковки или тестовой заглушки подтверждает только указанный предмет проверки.",
        "",
        "| Возможность | В пакете | Codex CLI: заявлено | Claude Code: заявлено | Hermes Agent: заявлено |",
        "| --- | --- | --- | --- | --- |",
    ]
    for capability_id in CAPABILITY_IDS:
        capability = capabilities[capability_id]
        cells = [PACKAGE_PRESENCE_LABELS[capability["package_presence"]["status"]]]
        for environment_id in ENVIRONMENT_IDS:
            cells.append(DECLARED_IMPLEMENTATION_LABELS[capability["declared_implementation"][environment_id]["status"]])
        lines.append(f"| {capability['name']} | {' | '.join(cells)} |")

    lines.extend(["", "Проверки не входят в заявленное состояние.", ""])
    lines.extend(render_implementation_basis(data))
    lines.extend(["", "### Зарегистрированные проверки", ""])
    if not data["checks"]:
        lines.append("Проверок пока нет.")
    else:
        lines.extend(
            [
                "| Дата | Среда | Коллекция | Возможность | Результат | Граница | Свидетельство |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for check in data["checks"]:
            evidence = ", ".join(
                f"[ссылка]({item})" for item in check["evidence"]
            )
            lines.append(
                f"| {check['date']} | {environment_name(data, check['environment']['id'])} "
                f"({environment_version(check)}) | {check['collection_version']} | "
                f"{capability_name(data, check['capability'])} | "
                f"{RESULT_LABELS[check['result']]} ({VERIFICATION_SUBJECT_LABELS[check['verification_subject']]}) | {check['scope']} | "
                f"{evidence} |"
            )
    lines.extend(["", END_MARKER])
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

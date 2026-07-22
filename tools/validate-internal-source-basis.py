#!/usr/bin/env python3
"""Проверить внутреннюю прослеживаемость сценариев результата к источникам."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
BASIS_PATH = ROOT / "evals" / "internal-source-basis.json"
SKILLS_ROOT = ROOT / ".apm" / "skills"


def load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path}: корень должен быть объектом JSON")
        return {}
    return data


def product_cases(errors: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted(SKILLS_ROOT.glob("*/evals/result-scenarios.json")):
        data = load_object(path, errors)
        skill_name = data.get("skill_name")
        cases = data.get("cases")
        if not isinstance(skill_name, str) or not isinstance(cases, list):
            errors.append(f"{path}: отсутствуют skill_name или cases")
            continue
        case_ids = {
            case.get("id")
            for case in cases
            if isinstance(case, dict) and isinstance(case.get("id"), str)
        }
        if len(case_ids) != len(cases):
            errors.append(f"{path}: не у каждого сценария есть уникальный id")
        result[skill_name] = case_ids
    return result


def source_claims(
    skill_name: str,
    value: dict[str, Any],
    errors: list[str],
) -> set[str]:
    claims: set[str] = set()
    source_basis = value.get("source_basis")
    if not isinstance(source_basis, list) or not source_basis:
        errors.append(f"{skill_name}: source_basis должен быть непустым массивом")
        return claims

    for index, item in enumerate(source_basis):
        label = f"{skill_name}: source_basis[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: ожидается объект")
            continue
        claim_id = item.get("claim_id")
        statement_path = item.get("statement_path")
        if not isinstance(claim_id, str) or not isinstance(statement_path, str):
            errors.append(f"{label}: нужны строковые claim_id и statement_path")
            continue
        if claim_id in claims:
            errors.append(f"{label}: повторяется {claim_id}")
        claims.add(claim_id)

        relative = Path(statement_path)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{label}: путь должен быть относительным и безопасным")
            continue
        source_path = ROOT / relative
        if not source_path.is_file():
            errors.append(f"{label}: файл не найден: {statement_path}")
            continue
        declaration = re.compile(
            rf"^\s*-\s+id:\s*['\"]?{re.escape(claim_id)}['\"]?\s*$",
            re.MULTILINE,
        )
        if not declaration.search(source_path.read_text(encoding="utf-8")):
            errors.append(f"{label}: утверждение {claim_id} не найдено в файле")
    return claims


def validate_case_links(
    skill_name: str,
    value: dict[str, Any],
    claims: set[str],
    expected_ids: set[str],
    errors: list[str],
) -> None:
    cases = value.get("cases")
    if not isinstance(cases, list):
        errors.append(f"{skill_name}: cases должен быть массивом")
        return
    actual_ids = {
        case.get("id")
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    if actual_ids != expected_ids:
        errors.append(f"{skill_name}: набор сценариев прослеживаемости устарел")

    used_claims: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            continue
        label = f"{skill_name}/{case['id']}"
        required = case.get("required_claims")
        finding_claims = case.get("finding_claims")
        if not isinstance(required, list) or not required:
            errors.append(f"{label}: required_claims должен быть непустым массивом")
            continue
        if not isinstance(finding_claims, list) or not finding_claims:
            errors.append(f"{label}: finding_claims должен быть непустым массивом")
            continue
        if not all(isinstance(item, str) for item in required):
            errors.append(f"{label}: required_claims должен содержать только строки")
            continue
        linked = set(required)
        for index, finding in enumerate(finding_claims):
            if not isinstance(finding, list) or not finding:
                errors.append(f"{label}: finding_claims[{index}] пуст или имеет неверный тип")
                continue
            if not all(isinstance(item, str) for item in finding):
                errors.append(f"{label}: finding_claims[{index}] должен содержать только строки")
                continue
            linked.update(finding)
        used_claims.update(linked)
        unknown = linked - claims
        if unknown:
            errors.append(f"{label}: неизвестные утверждения: {sorted(unknown)}")

    unused = claims - used_claims
    if unused:
        errors.append(f"{skill_name}: неиспользуемые утверждения: {sorted(unused)}")


def main() -> int:
    errors: list[str] = []
    data = load_object(BASIS_PATH, errors)
    skills = data.get("skills")
    expected = product_cases(errors)
    if not isinstance(skills, dict):
        errors.append(f"{BASIS_PATH}: skills должен быть объектом")
        skills = {}
    if set(skills) != set(expected):
        errors.append("Набор навыков во внутренней прослеживаемости устарел")

    for skill_name, expected_ids in expected.items():
        value = skills.get(skill_name)
        if not isinstance(value, dict):
            continue
        claims = source_claims(skill_name, value, errors)
        validate_case_links(skill_name, value, claims, expected_ids, errors)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Внутренняя прослеживаемость сценариев результата проверена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

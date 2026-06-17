#!/usr/bin/env python3
"""Run skill evals against a real Codex model."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-5.3-codex-spark"
DEFAULT_JUDGE_MODEL = "gpt-5.5"
CLAIM_RE = re.compile(r"^### ([A-Z0-9]+-\d+)\s*$", re.MULTILINE)


TRIGGER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "should_trigger", "rationale"],
                "properties": {
                    "id": {"type": "string"},
                    "should_trigger": {"type": "boolean"},
                    "rationale": {"type": "string"},
                },
            },
        },
    },
}


ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answers"],
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "answer"],
                "properties": {
                    "id": {"type": "string"},
                    "answer": {"type": "string"},
                },
            },
        },
    },
}


JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "passed", "reasons", "missing"],
                "properties": {
                    "id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "missing": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запустить evals навыков на реальной модели Codex.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Каталоги навыков или корни репозитория для обхода. По умолчанию текущий каталог.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("APM_EVAL_MODEL", DEFAULT_MODEL),
        help="Модель для применения навыков. По умолчанию APM_EVAL_MODEL или gpt-5.3-codex-spark.",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("APM_EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        help="Модель-судья. По умолчанию APM_EVAL_JUDGE_MODEL или gpt-5.5.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("APM_EVAL_LIMIT", "0")),
        help="Ограничить число result-сценариев. 0 означает все сценарии.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("APM_EVAL_TIMEOUT", "900")),
        help="Тайм-аут одного вызова Codex в секундах.",
    )
    return parser.parse_args()


def find_skill_dirs(paths: list[Path]) -> list[Path]:
    skill_dirs: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if (path / "SKILL.md").is_file():
            skill_dirs.add(path)
            continue
        for skill_file in path.rglob("SKILL.md"):
            if ".git" in skill_file.parts:
                continue
            skill_dirs.add(skill_file.parent)
    return sorted(skill_dirs)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_frontmatter(skill_path: Path) -> dict[str, str]:
    frontmatter: dict[str, str] = {}
    in_frontmatter = False
    current_key: str | None = None
    current_lines: list[str] = []

    for line in skill_path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if not in_frontmatter:
            continue
        if line and not line.startswith((" ", "\t")) and ":" in line:
            if current_key:
                frontmatter[current_key] = " ".join(current_lines).strip()
            current_key, value = line.split(":", 1)
            current_key = current_key.strip()
            current_lines = [value.strip().strip(">")]
            continue
        if current_key:
            current_lines.append(line.strip())

    if current_key:
        frontmatter[current_key] = " ".join(current_lines).strip()
    return frontmatter


def run_codex(
    *,
    model: str,
    prompt: str,
    schema: dict[str, Any],
    timeout: int,
    work_dir: Path,
) -> dict[str, Any]:
    schema_path = work_dir / "schema.json"
    output_path = work_dir / "last-message.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    if output_path.exists():
        output_path.unlink()

    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-",
    ]
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=work_dir,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Codex завершился с ошибкой "
            f"{completed.returncode}.\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
        )

    raw_output = output_path.read_text(encoding="utf-8").strip()
    if not raw_output:
        raw_output = completed.stdout.strip()
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Codex вернул не JSON: {exc}\nОтвет:\n{raw_output}",
        ) from exc


def collect_trigger_cases(skill_dirs: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for skill_dir in skill_dirs:
        trigger_path = skill_dir / "evals" / "triggers.json"
        if not trigger_path.exists():
            continue
        skill_path = skill_dir / "SKILL.md"
        frontmatter = read_frontmatter(skill_path)
        trigger_data = load_json(trigger_path)
        skill_name = trigger_data["skill_name"]
        for case in trigger_data["cases"]:
            cases.append(
                {
                    "id": case["id"],
                    "skill_name": skill_name,
                    "skill_description": frontmatter.get("description", ""),
                    "prompt": case["prompt"],
                    "expected_should_trigger": case["should_trigger"],
                    "expected_rationale": case["rationale"],
                },
            )
    return cases


def trigger_prompt(cases: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": case["id"],
            "skill_name": case["skill_name"],
            "skill_description": case["skill_description"],
            "user_prompt": case["prompt"],
        }
        for case in cases
    ]
    return (
        "Ты проверяешь маршрутизацию навыков агента.\n"
        "Для каждого кейса реши, должен ли указанный навык сработать для "
        "пользовательского запроса. Опирайся на description навыка как на "
        "контракт маршрутизации. Не угадывай по названию навыка, если "
        "description не покрывает ситуацию.\n"
        "Верни только JSON по заданной схеме.\n\n"
        f"Кейсы:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def run_trigger_evals(
    *,
    cases: list[dict[str, Any]],
    model: str,
    timeout: int,
    work_dir: Path,
) -> list[str]:
    if not cases:
        print("Модельные trigger-evals не найдены.", flush=True)
        return []

    print(f"Запускаю модельные trigger-evals: {len(cases)} кейс(ов).", flush=True)
    errors: list[str] = []
    missing_cases: list[dict[str, Any]] = []
    sorted_cases = sorted(cases, key=lambda item: item["skill_name"])
    for skill_name, grouped_cases in itertools.groupby(
        sorted_cases,
        key=lambda item: item["skill_name"],
    ):
        skill_cases = list(grouped_cases)
        print(
            f"Проверяю trigger-сценарии навыка {skill_name}: {len(skill_cases)}.",
            flush=True,
        )
        result = run_codex(
            model=model,
            prompt=trigger_prompt(skill_cases),
            schema=TRIGGER_SCHEMA,
            timeout=timeout,
            work_dir=work_dir,
        )
        actual_by_id = {item.get("id"): item for item in result.get("results", [])}
        for case in skill_cases:
            actual = actual_by_id.get(case["id"])
            if not actual:
                missing_cases.append(case)
                continue
            if actual.get("should_trigger") != case["expected_should_trigger"]:
                errors.append(
                    f"{case['id']}: ожидалось should_trigger="
                    f"{case['expected_should_trigger']}, модель вернула "
                    f"{actual.get('should_trigger')}. Обоснование: "
                    f"{actual.get('rationale', '')}",
                )
    for case in missing_cases:
        print(f"Повторяю trigger-сценарий {case['id']} отдельно.", flush=True)
        result = run_codex(
            model=model,
            prompt=trigger_prompt([case]),
            schema=TRIGGER_SCHEMA,
            timeout=timeout,
            work_dir=work_dir,
        )
        actual_by_id = {item.get("id"): item for item in result.get("results", [])}
        actual = actual_by_id.get(case["id"])
        if not actual:
            errors.append(f"{case['id']}: модель не вернула результат.")
            continue
        if actual.get("should_trigger") != case["expected_should_trigger"]:
            errors.append(
                f"{case['id']}: ожидалось should_trigger="
                f"{case['expected_should_trigger']}, модель вернула "
                f"{actual.get('should_trigger')}. Обоснование: "
                f"{actual.get('rationale', '')}",
            )
    if not errors:
        print(f"Пройдено модельных trigger-evals: {len(cases)} из {len(cases)}.", flush=True)
    return errors


def collect_result_groups(
    skill_dirs: list[Path],
    limit: int,
) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    remaining = limit
    groups: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = []
    for skill_dir in skill_dirs:
        result_path = skill_dir / "evals" / "result-scenarios.json"
        if not result_path.exists():
            continue
        data = load_json(result_path)
        cases = data["cases"]
        if limit > 0:
            if remaining <= 0:
                break
            cases = cases[:remaining]
            remaining -= len(cases)
        groups.append((skill_dir, data, cases))
    return groups


def extract_claim_block(statement_text: str, claim_id: str) -> str:
    matches = list(CLAIM_RE.finditer(statement_text))
    for index, match in enumerate(matches):
        if match.group(1) != claim_id:
            continue
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(statement_text)
        return statement_text[start:end].strip()
    return ""


def collect_source_basis_text(repo_root: Path, data: dict[str, Any]) -> list[dict[str, str]]:
    basis_text: list[dict[str, str]] = []
    for item in data.get("source_basis", []):
        claim_id = item.get("claim_id")
        statement_path = item.get("statement_path")
        if not isinstance(claim_id, str) or not isinstance(statement_path, str):
            continue
        path = repo_root / statement_path
        if not path.is_file():
            continue
        statement_text = path.read_text(encoding="utf-8")
        basis_text.append(
            {
                "claim_id": claim_id,
                "statement_path": statement_path,
                "text": extract_claim_block(statement_text, claim_id),
            },
        )
    return basis_text


def answer_prompt(
    repo_root: Path,
    skill_dir: Path,
    data: dict[str, Any],
    cases: list[dict[str, Any]],
) -> str:
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    target_cases = [
        {
            "id": case["id"],
            "prompt": case["prompt"],
            "input_files": case.get("input_files", []),
            "required_corpus_claims": case.get("required_corpus_claims", []),
            "expected_output": case.get("expected_output", {}),
            "assertions": case.get("assertions", []),
            "must_not": case.get("must_not", []),
        }
        for case in cases
    ]
    return (
        "Ты проверяемая модель. Примени навык к каждому пользовательскому "
        "сценарию и дай ответ так, как если бы пользователь реально попросил "
        "выполнить эту задачу. Ответ должен быть пригоден для проверки: покажи "
        "применённую процедуру навыка, конкретные выводы/findings, важные "
        "ограничения, действия или изменяемые файлы. Если даны "
        "required_corpus_claims, используй именно эти claim_id для ключевых "
        "выводов и не подменяй их похожими claim_id из source_basis. "
        "Используй expected_output, assertions и must_not как контракт "
        "приёмки результата: ответ должен содержать ожидаемую структуру, "
        "findings и проверяемые сведения, но не пересказывать контракт отдельно "
        "и не ссылаться на него как на тестовые данные. "
        "Если сценарий требует изменить файлы, а содержимое файлов не дано, "
        "верни проверяемый результат изменения: имена создаваемых или "
        "изменяемых файлов, какие фрагменты куда переносятся или удаляются, "
        "и какие правила остаются в каждом файле. Не отвечай планом: формулируй "
        "результат так, как будто применение навыка уже выполнено. Для каждого "
        "ключевого вывода используй поля severity, corpus_claims, "
        "observed_problem, expected_conclusion и acceptable_fix_direction. "
        "Не упоминай, что это тест, "
        "и не оценивай сам себя.\n"
        "Верни только JSON по заданной схеме.\n\n"
        f"Навык:\n{skill_text}\n\n"
        f"Сценарии:\n{json.dumps(target_cases, ensure_ascii=False, indent=2)}\n"
        "Фактические основания source_basis:\n"
        f"{json.dumps(collect_source_basis_text(repo_root, data), ensure_ascii=False, indent=2)}\n"
    )


def judge_prompt(
    data: dict[str, Any],
    cases: list[dict[str, Any]],
    answers: list[dict[str, str]],
) -> str:
    expected_cases = {case["id"]: case for case in data["cases"] if case in cases}
    payload = {
        "skill_name": data["skill_name"],
        "cases": [expected_cases[case["id"]] for case in cases],
        "answers": answers,
    }
    return (
        "Ты строгий судья evals навыков агента.\n"
        "Для каждого ответа проверь, реально ли модель применила навык к "
        "сценарию. Ответ проходит только если он удовлетворяет expected_output, "
        "application_evidence, oracle.success_criteria и assertions, а также не "
        "нарушает must_not и не содержит oracle.failure_indicators. Не засчитывай "
        "общие советы, пересказ схемы или формальное совпадение заголовков без "
        "признаков применения навыка. Оценивай только текст ответа, потому что "
        "runner не создаёт fixture-репозиторий для фактических файловых правок. "
        "Если assertion говорит, что результат меняет или создаёт файлы, считай "
        "его выполненным только когда ответ содержит конкретные имена файлов и "
        "проверяемые сведения о переносимых, удаляемых или добавляемых правилах.\n"
        "Верни только JSON по заданной схеме.\n\n"
        f"Данные для проверки:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )


def run_result_evals(
    *,
    repo_root: Path,
    groups: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]],
    model: str,
    judge_model: str,
    timeout: int,
    work_dir: Path,
) -> list[str]:
    total = sum(len(cases) for _, _, cases in groups)
    if not total:
        print("Модельные result-evals не найдены.", flush=True)
        return []

    print(f"Запускаю модельные result-evals: {total} сценариев.", flush=True)
    errors: list[str] = []
    passed = 0
    for skill_dir, data, cases in groups:
        print(
            f"Проверяю result-сценарии навыка {data['skill_name']}: {len(cases)}.",
            flush=True,
        )
        for case in cases:
            single_case = [case]
            answer_result = run_codex(
                model=model,
                prompt=answer_prompt(repo_root, skill_dir, data, single_case),
                schema=ANSWER_SCHEMA,
                timeout=timeout,
                work_dir=work_dir,
            )
            answers = answer_result.get("answers", [])
            judge_result = run_codex(
                model=judge_model,
                prompt=judge_prompt(data, single_case, answers),
                schema=JUDGE_SCHEMA,
                timeout=timeout,
                work_dir=work_dir,
            )
            verdicts = {
                item.get("id"): item for item in judge_result.get("results", [])
            }
            verdict = verdicts.get(case["id"])
            if not verdict:
                errors.append(f"{case['id']}: судья не вернул результат.")
                continue
            if verdict.get("passed") is True:
                passed += 1
                continue
            reasons = "; ".join(verdict.get("reasons", []))
            missing = "; ".join(verdict.get("missing", []))
            errors.append(
                f"{case['id']}: сценарий не пройден. Причины: {reasons}. "
                f"Не хватает: {missing}.",
            )
        print(
            f"Завершена проверка навыка {data['skill_name']}.",
            flush=True,
        )
    if not errors:
        print(f"Пройдено модельных result-evals: {passed} из {total}.", flush=True)
    return errors


def main() -> int:
    args = parse_args()
    judge_model = args.judge_model
    roots = args.paths or [Path.cwd()]
    repo_root = Path.cwd().resolve()
    skill_dirs = find_skill_dirs(roots)
    if not skill_dirs:
        print("Каталоги навыков не найдены.", file=sys.stderr)
        return 1

    print(f"Модель применения навыков: {args.model}.", flush=True)
    print(f"Модель оценки результатов: {judge_model}.", flush=True)

    with tempfile.TemporaryDirectory(prefix="apm-skill-evals-") as tmp:
        work_dir = Path(tmp)
        trigger_errors = run_trigger_evals(
            cases=collect_trigger_cases(skill_dirs),
            model=args.model,
            timeout=args.timeout,
            work_dir=work_dir,
        )
        result_errors = run_result_evals(
            repo_root=repo_root,
            groups=collect_result_groups(skill_dirs, args.limit),
            model=args.model,
            judge_model=judge_model,
            timeout=args.timeout,
            work_dir=work_dir,
        )

    errors = trigger_errors + result_errors
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"Модельные evals не пройдены: {len(errors)} ошибка(ок).", file=sys.stderr)
        return 1

    print("Модельные evals пройдены.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

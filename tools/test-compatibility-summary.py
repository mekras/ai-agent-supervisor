#!/usr/bin/env python3
"""Проверить реестр и генерацию сводки совместимости."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools/compatibility-summary.py"
MODULE = {"__name__": "compatibility_summary", "__file__": str(SCRIPT)}
exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), MODULE)


def registry(checks: list[dict] | None = None) -> dict:
    environments = [
        {"id": "codex_cli", "name": "Codex CLI", "declared_support": True, "user_summary": "Сводка Codex CLI."},
        {"id": "claude_code", "name": "Claude Code", "declared_support": True, "user_summary": "Сводка Claude Code."},
        {"id": "hermes_agent", "name": "Hermes Agent", "declared_support": True, "user_summary": "Сводка Hermes Agent."},
    ]
    capability_ids = MODULE["CAPABILITY_IDS"]
    capabilities = [
        {
            "id": capability_id,
            "name": capability_id,
            "target_environments": list(MODULE["ENVIRONMENT_IDS"]),
            "package_presence": {"status": "included", "basis": ["test-package"]},
            "declared_implementation": {
                environment_id: {
                    "status": "documented",
                    "basis": ["test-implementation"],
                }
                for environment_id in MODULE["ENVIRONMENT_IDS"]
            },
        }
        for capability_id in capability_ids
    ]
    return {
        "schema_version": 2,
        "scope": {"id": "collection", "name": "Вся коллекция навыков"},
        "environments": environments,
        "capabilities": capabilities,
        "checks": checks or [],
    }


def check(capability: str, environment: str, date: str, result: str, evidence: str) -> dict:
    return {
        "id": f"{environment}-{capability}-{date}-{result}",
        "date": date,
        "collection_version": "2.6.12",
        "environment": {
            "id": environment,
            "version": "1.0",
            "participation": "participated",
        },
        "capability": capability,
        "conditions": "тестовые условия",
        "method": "детерминированный сценарий",
        "verification_subject": "agent_runtime",
        "result": result,
        "scope": "только тестируемая возможность",
        "evidence": [evidence],
    }


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    render = MODULE["render_summary"]
    installation = "collection_installation"
    project = "project_and_instruction_setup"

    empty = render(registry())
    assert "Коллекция развивает поддержку Codex CLI, Claude Code и Hermes Agent." in empty
    assert "| Среда | Текущее состояние |" in empty
    assert "| Codex CLI | Сводка Codex CLI. |" in empty
    assert "| Claude Code | Сводка Claude Code. |" in empty
    assert "| Hermes Agent | Сводка Hermes Agent. |" in empty
    assert "Проверки поведения навыков в реальных средах пока не отражены в реестре." in empty
    assert "Проверка установки через APM не подтверждает работу самих навыков." in empty
    assert "[реестре поддержки](.apm/skills/ai-setup-apm/references/compatibility.yml)" in empty
    for detail in ("В пакете", "Основания заявленного состояния", "Зарегистрированные проверки", "old", "behavior"):
        assert detail not in empty

    installation_pass = check(installation, "codex_cli", "2026-09-20", "passed", "old")
    with_installation = render(registry([installation_pass]))
    assert with_installation == empty

    behavior_pass = check(project, "codex_cli", "2026-09-21", "passed", "behavior")
    with_behavior = render(registry([installation_pass, behavior_pass]))
    assert with_behavior == empty

    failure = check(project, "codex_cli", "2026-09-22", "failed", "new-failure")
    history = render(registry([installation_pass, behavior_pass, failure]))
    assert history == empty

    actual = MODULE["load_registry"](ROOT / ".apm/skills/ai-setup-apm/references/compatibility.yml")
    actual_check = actual["checks"][0]
    assert actual_check["capability"] == "collection_installation"
    assert actual_check["environment"]["participation"] == "not_participated"
    assert str(actual_check["date"]) == "2026-09-18"
    assert actual_check["collection_version"] == "2.6.3"
    assert actual_check["environment"]["tooling"]["apm_cli"] == "0.31.0"
    assert actual_check["verification_subject"] == "packaging_tooling"
    assert actual_check["result"] == "passed"
    assert "не запускался" in actual_check["scope"]
    assert "отдельный отчёт испытания в пакете не сохранён" in actual_check["scope"]
    assert actual_check["evidence"] == [
        ".apm/skills/ai-setup-apm/references/compatibility-history.md#L5-L12"
    ]
    actual_capabilities = {item["id"]: item for item in actual["capabilities"]}
    assert actual_capabilities["subagent_setup_and_use"]["declared_implementation"]["claude_code"]["status"] == "documented"
    for environment_id, environment_name in (("codex_cli", "Codex CLI"), ("claude_code", "Claude Code")):
        analysis = actual_capabilities["work_analysis_and_result_evaluation"]["declared_implementation"][environment_id]
        assert analysis["status"] == "partial"
        assert environment_name in analysis["gap"]
        assert "ai-work-result-evaluation" in analysis["gap"]
    actual_rendered = render(actual)
    assert "| Codex CLI | Предусмотрены установка и работа навыков." in actual_rendered
    assert "| Hermes Agent | Предусмотрена установка через APM." in actual_rendered
    assert "Загрузка и доступность навыков внутри Hermes не проверялись" not in actual_rendered
    assert ".apm/skills/ai-setup-subagents/references/operation-policy.md#L331-L342" not in actual_rendered
    assert "Общая оценка результата через ai-work-result-evaluation доступна" not in actual_rendered
    assert ".apm/skills/ai-setup-apm/references/compatibility-history.md#L5-L12" not in actual_rendered
    assert "<br>" not in actual_rendered
    assert "поставляется в коллекции" not in actual_rendered

    missing_basis = registry()
    missing_basis["capabilities"][0]["declared_implementation"]["codex_cli"]["basis"] = []
    try:
        MODULE["validate_registry"](missing_basis)
    except ValueError as error:
        assert "нужно основание заявленного состояния" in str(error)
    else:
        raise AssertionError("состояние реализации без основания принято")

    missing_gap = registry()
    missing_gap["capabilities"][0]["declared_implementation"]["codex_cli"] = {
        "status": "partial",
        "basis": ["test-implementation"],
    }
    try:
        MODULE["validate_registry"](missing_gap)
    except ValueError as error:
        assert "для partial нужен пробел" in str(error)
    else:
        raise AssertionError("частичное состояние без пробела принято")

    missing_subject = registry()
    missing_subject["checks"] = [check(installation, "codex_cli", "2026-09-20", "passed", "old")]
    del missing_subject["checks"][0]["verification_subject"]
    try:
        MODULE["validate_registry"](missing_subject)
    except ValueError as error:
        assert "неизвестен предмет проверки" in str(error)
    else:
        raise AssertionError("проверка без предмета принята")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        registry_path = root / "compatibility.yml"
        readme_path = root / "README.md"
        old_data = registry([installation_pass])
        new_data = registry([installation_pass, failure])
        new_data["environments"][0]["user_summary"] = "Обновлённая сводка."
        registry_path.write_text(yaml.safe_dump(new_data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        readme_path.write_text(render(old_data), encoding="utf-8")
        before = readme_path.read_bytes()
        result = run_cli("--check", "--registry", str(registry_path), "--readme", str(readme_path))
        assert result.returncode == 1
        assert readme_path.read_bytes() == before
        result = run_cli("--write", "--registry", str(registry_path), "--readme", str(readme_path))
        assert result.returncode == 0
        assert "Обновлённая сводка." in readme_path.read_text(encoding="utf-8")
        result = run_cli("--check", "--registry", str(registry_path), "--readme", str(readme_path))
        assert result.returncode == 0

    print("Реестр и сводка поддержки проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

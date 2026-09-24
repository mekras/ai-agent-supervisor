#!/usr/bin/env python3
"""Проверяет механическую миграцию старой политики подагентов."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".apm/skills/ai-setup-subagents/scripts/migrate-subagent-policy.py"
FIXTURE = ROOT / ".apm/skills/ai-setup-subagents/evals/script-fixtures/policy-migration"
ASSET = ROOT / ".apm/skills/ai-setup-subagents/assets/worker-policy-entrypoint.md"
START = "<!-- ai-setup-subagents:runtime-policy:start -->"
END = "<!-- ai-setup-subagents:runtime-policy:end -->"


def assert_unambiguous_entrypoint(text: str) -> None:
    normalized = " ".join(text.split())
    required = [
        "Чтение этой политики при обычном выполнении не превращает задачу в настройку или проверку политики.",
        "Не запускайте процедуру настройки, если пользователь не поручил настроить, изменить или проверить саму политику.",
        "Сразу после чтения политики и до первого чтения предметного входа, исследования или реализации примите одно краткое решение о маршруте и сохраните его во внешнем следе текущей сессии.",
        "Итоговый ответ не заменяет такой предварительный след.",
        "Не раскрывайте внутренние рассуждения: достаточно строки «Маршрут» с рассмотренным объёмом, исходом, предметным основанием и неопределённостью, если она есть.",
        "назовите каждую кандидатную ограниченную подзадачу либо прямо укажите, что кандидатов нет",
        "Отсутствие решения или следа — пропуск применения политики, даже если предметный ответ оказался полезным.",
        "`direct_execution_scope = \"whole_parent_task\"` означает только, что саму родительскую задачу целиком не передают.",
        "Оно не отменяет отдельного рассмотрения подходящей ограниченной read-only подзадачи.",
        "`subtask_routing = \"match_each_bounded_subtask\"` требует отдельно проверить такую подзадачу и её маршрут.",
        "Для рассматриваемой ограниченной read-only подзадачи дочернему исполнителю запрещены запись, утверждение решения и расширение области.",
        "Это ограничение относится только к этому маршруту и не отменяет отдельный контракт класса, который явно разрешает ограниченную запись.",
        "Независимо от класса дочерний исполнитель не изменяет защищённые источники, не утверждает решения и не расширяет область.",
        "Родитель сохраняет запись в защищённых источниках, утверждение решений и итоговую приёмку результата.",
        "Микрозадачи не декомпозируйте искусственно.",
        "Для прямого выполнения свяжите причину с конкретными свойствами рассматриваемой подзадачи и полной стоимостью передачи",
        "Само `whole_parent_task` и формат итогового ответа не являются причиной прямого выполнения.",
        "Если для выделения или передачи нет оправданного маршрута либо постановка, вход и приёмка дороже ожидаемой пользы, соответствующий объём работы выполняет родитель",
        "При недостатке сведений не приписывайте прямому выполнению непроверенное преимущество",
        "Не называйте передачу лучшей, более дешёвой или более качественной по непроверенному сравнению с родителем.",
        "Передача остаётся допустимой, если её предметное основание не зависит от неизвестного параметра",
        "Если без сравнения нельзя обосновать ни передачу, ни прямое выполнение, зафиксируйте маршрут как неразрешённый",
    ]
    for phrase in required:
        assert phrase in normalized, phrase
    assert "Если вся родительская задача совпала с `direct_execution`, выполните её у родителя целиком." not in normalized
    assert "Если сама родительская задача попала в `direct_execution`, её не делегируют целиком." not in normalized
    positions = [normalized.index(phrase) for phrase in required]
    assert positions == sorted(positions)


def run(config: Path, entrypoint: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCRIPT),
        "--config",
        str(config),
        "--entrypoint",
        f"codex={entrypoint}",
    ]
    if check:
        command.append("--check")
    return subprocess.run(
        command,
        cwd=config.parent,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="проверка миграции ") as temporary:
        root = Path(temporary)
        config = root / "subagents.local.toml"
        entrypoint = root / "AGENTS.md"
        shutil.copy2(FIXTURE / config.name, config)
        shutil.copy2(FIXTURE / "worker-instructions.md", entrypoint)

        first = run(config, entrypoint)
        assert first.returncode == 0, first.stderr
        data = tomllib.loads(config.read_text(encoding="utf-8"))
        runtime = data["policy_runtime"]
        assert runtime["schema_version"] == 2
        assert runtime["launcher"] == "local-launcher"
        assert runtime["target"] == "local-target"
        assert runtime["direct_execution"] == ["one-file microtask"]
        assert runtime["unavailable_route"] == "keep parent route"
        assert runtime["execution_failure"] == "discard child result"
        assert runtime["unconfirmed_model"] == "parent decides after acceptance"
        assert runtime["result_acceptance"] == "parent checks evidence"
        assert runtime["execution_status"] == "blocked"
        assert runtime["economy_status"] == "not_measured"
        assert runtime["routes"] == [{"when": "bounded read-only facts", "execution_class": "local-readonly"}]
        assert runtime["comparison_evidence_level"] == "client_execution"

        task = data["policy_design"]["tasks"][0]
        assert task["parent_basis"] == "historical_setup_observation"
        assert task["parent_basis_model"] == "historical assignment"
        assert task["parent_basis_effort"] == "historical effort"
        assert task["parent_basis_evidence"] == "setup observation"
        assert task["parent_basis_observed_at"] == "unknown"
        assert not any(key in task for key in ("parent_model", "parent_effort", "parent_evidence"))

        target = data["targets"]["local"]["execution_classes"]["local_readonly"]
        assert data["execution_classes"]["local_readonly"]["writes"] is False
        assert target == {
            "model": "configured local assignment",
            "effort": "configured local effort",
            "sandbox": "read-only",
            "adapter": ["configured adapter"],
        }

        migrated_entrypoint = entrypoint.read_text(encoding="utf-8")
        assert migrated_entrypoint.count(START) == 1
        assert migrated_entrypoint.count(END) == 1
        canonical = ASSET.read_text(encoding="utf-8")
        assert canonical in migrated_entrypoint
        assert_unambiguous_entrypoint(canonical)
        assert "Keep this surrounding rule unchanged." in migrated_entrypoint
        assert "Keep this rule after the managed fragment unchanged." in migrated_entrypoint

        saved_config = config.read_bytes()
        saved_entrypoint = entrypoint.read_bytes()
        second = run(config, entrypoint)
        assert second.returncode == 0, second.stderr
        assert "уже актуальна" in second.stdout
        assert config.read_bytes() == saved_config
        assert entrypoint.read_bytes() == saved_entrypoint
        assert run(config, entrypoint, check=True).returncode == 0

        entrypoint.write_text(
            "# Installed rules from version 2.6.7\n\n"
            + START
            + "\n"
            + "## Рабочая политика подагентов\n\n"
            + "Если вся родительская задача совпала с `direct_execution`, выполните её у родителя целиком.\n"
            + "Для отдельной подзадачи это условие не переносится: при подходящем маршруте передача допустима.\n"
            + END
            + "\n\n# Local rule preserved\n",
            encoding="utf-8",
        )
        schema2_config = config.read_bytes()
        repaired_schema2 = run(config, entrypoint)
        assert repaired_schema2.returncode == 0, repaired_schema2.stderr
        assert "Политика подагентов мигрирована." in repaired_schema2.stdout
        assert config.read_bytes() == schema2_config
        migrated_schema2 = entrypoint.read_text(encoding="utf-8")
        assert canonical in migrated_schema2
        assert_unambiguous_entrypoint(migrated_schema2)
        assert "Installed rules from version 2.6.7" in migrated_schema2
        assert "Local rule preserved" in migrated_schema2
        schema2_data = tomllib.loads(config.read_text(encoding="utf-8"))
        assert schema2_data["policy_runtime"]["schema_version"] == 2
        assert schema2_data["policy_runtime"]["launcher"] == "local-launcher"
        assert schema2_data["policy_runtime"]["target"] == "local-target"
        assert schema2_data["policy_runtime"]["direct_execution"] == ["one-file microtask"]
        assert schema2_data["policy_runtime"]["unavailable_route"] == "keep parent route"
        stable_schema2_entrypoint = entrypoint.read_bytes()
        stable_schema2 = run(config, entrypoint)
        assert stable_schema2.returncode == 0, stable_schema2.stderr
        assert "уже актуальна" in stable_schema2.stdout
        assert config.read_bytes() == schema2_config
        assert entrypoint.read_bytes() == stable_schema2_entrypoint

    print("Миграция политики подагентов проверена на изолированной установке.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

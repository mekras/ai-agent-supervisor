#!/usr/bin/env python3
"""Детерминированные проверки средств политики выполнения."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import tomllib
from pathlib import Path

# Русские сообщения не должны падать на консоли с однобайтовой кодировкой.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".apm/skills/ai-setup-execution-policy/scripts/execution-policy"
INSTALLER = ROOT / ".apm/skills/ai-setup-execution-policy/scripts/install-execution-policy-tools"
HANDOFF_TEMPLATE = ROOT / ".apm/skills/ai-setup-execution-policy/assets/handoff.md.template"


def run(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *arguments],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def write_policy(directory: Path) -> tuple[Path, Path]:
    core = directory / "user-core.toml"
    core.write_text(
        textwrap.dedent(
            """
            schema_version = 1
            required_evidence = ["test-result"]
            qualification_files = []

            [[routes]]
            id = "reference"
            environment = "harness"
            model = "reference-model"

            [[routes]]
            id = "candidate"
            environment = "harness"
            model = "candidate-model"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    project = directory / "project.toml"
    project.write_text(
        textwrap.dedent(
            """
            schema_version = 1

            [[task_classes]]
            id = "checked-change"
            reference_route = "reference"
            candidate_route = "candidate"
            automatic = true
            root_task = true
            acceptance_criteria = ["all-tests-pass"]
            required_evidence = ["test-result"]
            handoff_method = "new-session-handoff-v1"

            [[task_classes]]
            id = "manual-review"
            reference_route = "reference"
            candidate_route = "candidate"
            automatic = false
            root_task = false
            acceptance_criteria = ["reviewed"]
            required_evidence = ["test-result"]
            handoff_method = "new-session-handoff-v1"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return core, project


def qualify(core: Path, project: Path, output: Path, *, escalated: bool = False, rework: bool = False) -> None:
    prepared = run(
        "prepare-qualification",
        "--user-core",
        str(core),
        "--project-overlay",
        str(project),
        "--task-class",
        "checked-change",
        "--output",
        str(output),
    )
    assert prepared.returncode == 0, prepared.stderr
    traces = output.parent / "traces"
    traces.mkdir(exist_ok=True)
    checks = output.parent / "checks"
    checks.mkdir(exist_ok=True)
    (checks / "result.txt").write_text("Конечные критерии всего маршрута проверены.\n", encoding="utf-8")
    (traces / "reference.jsonl").write_text("reference\n", encoding="utf-8")
    (traces / "candidate.jsonl").write_text("candidate\n", encoding="utf-8")
    content = output.read_text(encoding="utf-8")
    content = content.replace('actual_reference_route = ""', 'actual_reference_route = "reference-run"')
    content = content.replace('actual_candidate_route = ""', 'actual_candidate_route = "candidate-run"')
    content = content.replace("result_evidence = {}", 'result_evidence = { "test-result" = "checks/result.txt" }')
    content = content.replace("criterion_results = {}", 'criterion_results = { "all-tests-pass" = "passed" }')
    content = content.replace('reference_trace = ""', 'reference_trace = "traces/reference.jsonl"')
    content = content.replace('candidate_trace = ""', 'candidate_trace = "traces/candidate.jsonl"')
    content = content.replace('outcome = "pending"', 'outcome = "qualified"')
    if escalated:
        content = content.replace("escalated = false", "escalated = true")
        content = content.replace('escalation_reason = ""', 'escalation_reason = "сложный этап"')
        content = content.replace("preserved_results = []", 'preserved_results = ["artifacts/phase-one.md"]')
    if rework:
        content = content.replace("rework_required = false", "rework_required = true")
    task_class = tomllib.loads(project.read_text(encoding="utf-8"))["task_classes"][0]
    route_record = {
        "scope": "whole_route",
        "candidate_steps": task_class.get("candidate_steps", ["candidate"]),
        "candidate_conditions": task_class.get("candidate_conditions", []),
        "transition_evidence": ["checks/result.txt"] * len(task_class.get("candidate_conditions", [])),
        "actual_candidate_steps": task_class.get("candidate_steps", ["candidate"]),
        "rework_required": rework,
        "criterion_results": {criterion: "passed" for criterion in task_class["acceptance_criteria"]},
        "result_evidence": {"test-result": "checks/result.txt"},
        "assessment_basis": "Проверен весь указанный маршрут с конечной приёмкой и ограничениями.",
        "rework_reason": "Исправление результата после обнаружения ошибки." if rework else "",
        "preserved_results": [],
        "discarded_results": ["первая версия результата"] if rework else [],
    }
    route_file = output.with_suffix(".route.json")
    route_file.write_text(json.dumps(route_record), encoding="utf-8")
    content = content.replace('route_evidence = ""', f'route_evidence = {json.dumps(route_file.name)}')
    output.write_text(content, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        core, project = write_policy(directory)
        qualification = directory / "qualification.toml"
        qualify(core, project, qualification)

        ready = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--qualification",
            str(qualification),
            "--task-class",
            "checked-change",
        )
        assert ready.returncode == 0, ready.stderr
        assert "automatic_candidate=qualified" in ready.stdout
        assert "source.routes=user_core" in ready.stdout
        assert "actual_reference_route=reference-run" in ready.stdout
        assert "escalated=false" in ready.stdout
        assert "unapplied_task_class=manual-review" in ready.stdout

        escalated_qualification = directory / "escalated-qualification.toml"
        qualify(core, project, escalated_qualification, escalated=True)
        escalated_ready = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--qualification",
            str(escalated_qualification),
            "--task-class",
            "checked-change",
        )
        assert escalated_ready.returncode == 0, escalated_ready.stderr
        assert "escalated=true" in escalated_ready.stdout
        assert "escalation_reason=сложный этап" in escalated_ready.stdout
        assert "preserved_result=artifacts/phase-one.md" in escalated_ready.stdout

        reworked_qualification = directory / "reworked-qualification.toml"
        qualify(core, project, reworked_qualification, escalated=True, rework=True)
        reworked = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--qualification",
            str(reworked_qualification),
            "--task-class",
            "checked-change",
        )
        assert reworked.returncode == 0, reworked.stderr
        assert "rework_required=true" in reworked.stdout
        assert "automatic_candidate=qualified" in reworked.stdout

        rework_evidence_file = reworked_qualification.with_suffix(".route.json")
        rework_evidence = json.loads(rework_evidence_file.read_text(encoding="utf-8"))
        for key, value in (
            ("actual_candidate_steps", ["candidate", "reference"]),
            ("rework_required", False), ("rework_reason", ""),
            ("assessment_basis", ""), ("preserved_results", None),
            ("discarded_results", None), ("criterion_results", {"all-tests-pass": "failed"}),
            ("result_evidence", {"test-result": "absent.txt"}),
            ("transition_evidence", ["checks/result.txt"]),
        ):
            rework_evidence_file.write_text(json.dumps({**rework_evidence, key: value}), encoding="utf-8")
            rejected = run("check", "--user-core", str(core), "--project-overlay", str(project),
                           "--qualification", str(reworked_qualification), "--task-class", "checked-change")
            assert rejected.returncode == 1, (key, rejected.stdout)
        rework_evidence_file.write_text(json.dumps(rework_evidence), encoding="utf-8")

        missing_route = directory / "missing-route.toml"
        missing_route.write_text(
            qualification.read_text(encoding="utf-8").replace('route_evidence = "qualification.route.json"', 'route_evidence = "absent.json"'),
            encoding="utf-8",
        )
        rejected = run("check", "--user-core", str(core), "--project-overlay", str(project),
                       "--qualification", str(missing_route), "--task-class", "checked-change")
        assert rejected.returncode == 1
        assert "неполное свидетельство всего маршрута" in rejected.stderr

        planned = directory / "planned"
        planned.mkdir()
        planned_core, planned_project = write_policy(planned)
        planned_project.write_text(
            planned_project.read_text(encoding="utf-8").replace(
                'id = "checked-change"',
                'id = "checked-change"\ncandidate_steps = ["candidate", "reference"]\n'
                'candidate_conditions = ["первый результат не прошёл проверку"]',
            ), encoding="utf-8",
        )
        planned_qualification = planned / "qualification.toml"
        qualify(planned_core, planned_project, planned_qualification, escalated=True, rework=True)
        planned_ready = run("check", "--user-core", str(planned_core), "--project-overlay", str(planned_project),
                            "--qualification", str(planned_qualification), "--task-class", "checked-change")
        assert planned_ready.returncode == 0, planned_ready.stderr
        planned_qualification.write_text(
            planned_qualification.read_text(encoding="utf-8").replace(
                'preserved_results = ["artifacts/phase-one.md"]', 'preserved_results = []',
            ), encoding="utf-8",
        )
        fully_reworked = run("check", "--user-core", str(planned_core), "--project-overlay", str(planned_project),
                             "--qualification", str(planned_qualification), "--task-class", "checked-change")
        assert fully_reworked.returncode == 0, fully_reworked.stderr
        assert "automatic_candidate=qualified" in fully_reworked.stdout
        planned_project.write_text(
            planned_project.read_text(encoding="utf-8").replace("первый результат не прошёл проверку", "всегда"), encoding="utf-8",
        )
        stale_plan = run("check", "--user-core", str(planned_core), "--project-overlay", str(planned_project),
                         "--qualification", str(planned_qualification), "--task-class", "checked-change")
        assert stale_plan.returncode == 1
        assert "требует пересмотра" in stale_plan.stderr

        incomplete_qualification = directory / "incomplete-qualification.toml"
        prepared = run(
            "prepare-qualification",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--task-class",
            "checked-change",
            "--output",
            str(incomplete_qualification),
        )
        assert prepared.returncode == 0, prepared.stderr
        incomplete = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--qualification",
            str(incomplete_qualification),
            "--task-class",
            "checked-change",
        )
        assert incomplete.returncode == 1
        assert "отсутствуют результаты" in incomplete.stderr

        core.write_text(
            core.read_text(encoding="utf-8").replace("candidate-model", "candidate-model-v2"),
            encoding="utf-8",
        )
        stale = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--qualification",
            str(qualification),
        )
        assert stale.returncode == 1
        assert "требует пересмотра" in stale.stderr

        core.write_text(
            core.read_text(encoding="utf-8").replace("candidate-model-v2", "candidate-model"),
            encoding="utf-8",
        )
        leaking_project = directory / "leaking-project.toml"
        leaking_project.write_text(project.read_text(encoding="utf-8") + 'model = "private"\n', encoding="utf-8")
        leaking = run(
            "check",
            "--user-core",
            str(core),
            "--project-overlay",
            str(leaking_project),
        )
        assert leaking.returncode == 2
        assert "приватные поля" in leaking.stderr

        incomplete_handoff = directory / "incomplete-handoff.md"
        incomplete_handoff.write_bytes(HANDOFF_TEMPLATE.read_bytes())
        incomplete = run("check-handoff", "--input", str(incomplete_handoff))
        assert incomplete.returncode == 1
        complete_handoff = directory / "handoff.md"
        handoff_content = HANDOFF_TEMPLATE.read_text(encoding="utf-8")
        for section in (
            "Причина передачи",
            "Цель и критерии готовности",
            "Границы и запреты",
            "Проверенные основания",
            "Непроверенные выводы",
            "Результаты и изменённые файлы",
            "Выполненные проверки",
            "Открытые вопросы и риски",
            "Следующий шаг",
            "Результат продолжения",
            "Оценка экономии",
        ):
            handoff_content = handoff_content.replace(f"## {section}", f"## {section}\n\nЗаполнено.")
        handoff_content = handoff_content.replace("status: <pending|continued|failed>", "status: continued")
        handoff_content = handoff_content.replace("full_transcript_required: <true|false>", "full_transcript_required: false")
        handoff_content = handoff_content.replace("rework_required: <true|false>", "rework_required: false")
        handoff_content = handoff_content.replace("confirmed: <true|false>", "confirmed: true")
        handoff_content = handoff_content.replace("basis: <заполнить>", "basis: сопоставлены результаты проверок")
        economy_record = {
            "scope": "whole_task",
            "task_completed": True,
            "quality_preserved": True,
            "constraints_preserved": True,
            "comparable_conditions": True,
            "complete_accounting": True,
            "acceptance_evidence": "acceptance.txt",
            "accounting_evidence": "accounting.txt",
            "accounting_basis": "Учтены все попытки, переделки, проверка и труд человека по общей методике.",
            "unit": "условная единица полной стоимости",
            "reference_total": 100,
            "candidate_total": 80,
        }
        economy_file = directory / "economy.json"
        (directory / "acceptance.txt").write_text(
            "Итоговые результаты обоих маршрутов приняты по одинаковым критериям.\n", encoding="utf-8",
        )
        (directory / "accounting.txt").write_text(
            "Учебное свидетельство: эталон 100, кандидат 80. Учтены все попытки и участие человека.\n", encoding="utf-8",
        )
        economy_file.write_text(json.dumps(economy_record), encoding="utf-8")
        handoff_content = handoff_content.replace(
            "evidence: <путь к свидетельству JSON, обязателен при confirmed: true>",
            "evidence: economy.json",
        )
        complete_handoff.write_text(handoff_content, encoding="utf-8")
        complete = run("check-handoff", "--input", str(complete_handoff))
        assert complete.returncode == 0, complete.stderr
        assert "handoff_bytes=" in complete.stdout
        assert "handoff_continuation_status=continued" in complete.stdout
        assert "handoff_economy_confirmed=true" in complete.stdout
        assert "economy_scope=whole_task" in complete.stdout
        assert "evidence_check=structure_only" in complete.stdout
        assert "economy_evidence_sha256=" in complete.stdout

        failed_handoff = directory / "failed-handoff.md"
        failed_handoff.write_text(
            handoff_content.replace("status: continued", "status: failed").replace(
                "rework_required: false", "rework_required: true"
            ),
            encoding="utf-8",
        )
        failed = run("check-handoff", "--input", str(failed_handoff))
        assert failed.returncode == 0, failed.stderr
        assert "handoff_continuation_status=failed" in failed.stdout
        assert "handoff_economy_confirmed=true" in failed.stdout

        # Экономия всей задачи не превращает неуспешную передачу в успешную.
        failed_handoff.write_text(
            handoff_content.replace("rework_required: false", "rework_required: true"),
            encoding="utf-8",
        )
        inconsistent = run("check-handoff", "--input", str(failed_handoff))
        assert inconsistent.returncode == 1
        assert "требуют status: failed" in inconsistent.stderr

        for key, value in (
            ("task_completed", False), ("quality_preserved", False),
            ("constraints_preserved", False), ("comparable_conditions", False),
            ("complete_accounting", False), ("unit", ""),
            ("acceptance_evidence", ""), ("accounting_basis", ""),
            ("acceptance_evidence", "absent.txt"), ("accounting_evidence", "absent.txt"),
            ("candidate_total", 100), ("candidate_total", 101),
            ("candidate_total", -1), ("candidate_total", True),
            ("candidate_total", float("nan")), ("reference_total", float("inf")),
            ("scope", "handoff"),
        ):
            economy_file.write_text(json.dumps({**economy_record, key: value}), encoding="utf-8")
            rejected = run("check-handoff", "--input", str(complete_handoff))
            assert rejected.returncode == 1, (key, value, rejected.stdout)
            assert "неподтверждённая экономия всей задачи" in rejected.stderr

        for value in ("[]", "{", "null"):
            economy_file.write_text(value, encoding="utf-8")
            rejected = run("check-handoff", "--input", str(complete_handoff))
            assert rejected.returncode == 1, rejected.stdout

        complete_handoff.write_text(handoff_content.replace("economy.json", "absent.json"), encoding="utf-8")
        missing_evidence = run("check-handoff", "--input", str(complete_handoff))
        assert missing_evidence.returncode == 1
        complete_handoff.write_text(
            handoff_content.replace("confirmed: true", "confirmed: false").replace("economy.json", "absent.json"),
            encoding="utf-8",
        )
        unknown_economy = run("check-handoff", "--input", str(complete_handoff))
        assert unknown_economy.returncode == 0, unknown_economy.stderr
        assert "handoff_economy_confirmed=false" in unknown_economy.stdout

        repository = directory / "repository"
        repository.mkdir()
        initialized = subprocess.run(["git", "init", str(repository)], text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stderr
        private_core = repository / "private.toml"
        refused = run("init-user", "--output", str(private_core))
        assert refused.returncode == 2
        assert "исключён из Git" in refused.stderr
        nested_private_core = repository / "nested/private.toml"
        nested_refused = run("init-user", "--output", str(nested_private_core))
        assert nested_refused.returncode == 2
        exclude = repository / ".git/info/exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + "\nprivate.toml\n", encoding="utf-8")
        created = run("init-user", "--output", str(private_core))
        assert created.returncode == 0, created.stderr
        assert stat.S_IMODE(private_core.stat().st_mode) == 0o600
        repeated = run("init-user", "--output", str(private_core))
        assert repeated.returncode == 2

        private_qualification = repository / "qualification.toml"
        qualification_refused = run(
            "prepare-qualification",
            "--user-core",
            str(core),
            "--project-overlay",
            str(project),
            "--task-class",
            "checked-change",
            "--output",
            str(private_qualification),
        )
        assert qualification_refused.returncode == 2
        assert "исключён из Git" in qualification_refused.stderr

        installed_root = directory / "installed-project"
        installed = subprocess.run([str(INSTALLER), str(installed_root)], text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
        assert installed.returncode == 0, installed.stderr
        installed_script = installed_root / "tools/execution-policy"
        assert installed_script.read_bytes() == SCRIPT.read_bytes()
        assert (installed_root / "tools/handoff.md.template").read_bytes() == HANDOFF_TEMPLATE.read_bytes()

    print("Проверки политики выполнения пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

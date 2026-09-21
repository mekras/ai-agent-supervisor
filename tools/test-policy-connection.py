#!/usr/bin/env python3
"""Проверяет подключение политики подагентов к рабочей инструкции."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".apm/skills/ai-setup-subagents/scripts/assess-subagent-policy-connection.py"
ENTRYPOINT = ROOT / ".apm/skills/ai-setup-subagents/assets/worker-policy-entrypoint.md"


def invoke(config: Path, entrypoint: Path, record: Path | None = None, output: Path | None = None) -> subprocess.CompletedProcess[str]:
    arguments = [
        str(SCRIPT), "--config", str(config), "--entrypoint", f"codex={entrypoint}", "--json",
    ]
    if record is not None:
        arguments.extend(["--run-record", str(record)])
    if output is not None:
        arguments.extend(["--output", str(output)])
    return subprocess.run(
        arguments, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = root / "subagents.local.toml"
        config.write_text(
            """[policy_runtime]
schema_version = 2
launcher = "tools/run-execution-class"
target = "codex"
direct_execution = ["microtask"]
direct_execution_scope = "whole_parent_task"
subtask_routing = "match_each_bounded_subtask"
parent_comparison = "actual_current_session"
unknown_parent_parameters = "comparison_unresolved"
parent_change = "invalidate_comparison"
assignment_basis = "historical_only"
unavailable_route = "parent"
execution_failure = "parent without result"
unconfirmed_model = "parent decides whether the result is usable"
result_acceptance = "parent accepts"

[[policy_runtime.routes]]
when = "bounded evidence gathering"
execution_class = "cheap_readonly_research"
""",
            encoding="utf-8",
        )
        entrypoint = root / "worker-instructions.md"
        entrypoint.write_text(ENTRYPOINT.read_text(encoding="utf-8"), encoding="utf-8")

        output = root / "report.json"
        connected = invoke(config, entrypoint, output=output)
        assert connected.returncode == 0, connected.stderr
        report = json.loads(connected.stdout)
        assert report["configuration"] == "saved"
        assert report["instruction_entrypoints"] == "referenced"
        assert report["working_sessions"] == "not_observed"
        assert json.loads(output.read_text(encoding="utf-8"))["instruction_entrypoints"] == "referenced"
        assert report["execution"] == {
            "process": "not_checked", "result": "not_checked", "acceptance_record": "not_checked", "quality": "not_evidenced", "model": "not_checked", "economy": "not_checked",
        }

        config.write_text(
            config.read_text(encoding="utf-8").replace(
                'parent_comparison = "actual_current_session"',
                'parent_comparison = "saved_assignment"',
            ),
            encoding="utf-8",
        )
        invalid_runtime = invoke(config, entrypoint)
        assert invalid_runtime.returncode == 1
        assert "parent_comparison" in json.loads(invalid_runtime.stdout)["errors"][0]

        config.write_text(
            config.read_text(encoding="utf-8").replace(
                'parent_comparison = "saved_assignment"',
                'parent_comparison = "actual_current_session"',
            ),
            encoding="utf-8",
        )

        entrypoint.write_text("# Instructions\n", encoding="utf-8")
        missing_connection = invoke(config, entrypoint)
        assert missing_connection.returncode == 1
        report = json.loads(missing_connection.stdout)
        assert report["configuration"] == "saved"
        assert report["instruction_entrypoints"] == "not_referenced"
        assert "обязательного фрагмента" in report["errors"][0]

        entrypoint.write_text(ENTRYPOINT.read_text(encoding="utf-8"), encoding="utf-8")
        record = root / "run.json"
        record.write_text(
            json.dumps({"returncode": 0, "result_available": True, "result_path": str(entrypoint), "model_status": "unconfirmed", "model_matches": None}),
            encoding="utf-8",
        )
        unconfirmed = invoke(config, entrypoint, record)
        assert unconfirmed.returncode == 0, unconfirmed.stderr
        report = json.loads(unconfirmed.stdout)
        assert report["execution"] == {
            "process": "completed", "result": "available", "acceptance_record": "not_checked", "quality": "not_evidenced", "model": "unconfirmed", "economy": "not_measured",
        }

        record.write_text(
            json.dumps({
                "returncode": 0, "result_available": True, "result_path": str(entrypoint), "model_status": "confirmed", "model_matches": True,
                "acceptance": {"status": "accepted"}, "quality_assessment": {"status": "passed"}, "economy": {"status": "measured"},
            }), encoding="utf-8",
        )
        accepted = invoke(config, entrypoint, record)
        assert accepted.returncode == 0, accepted.stderr
        assert json.loads(accepted.stdout)["execution"] == {
            "process": "completed", "result": "available", "acceptance_record": "accepted_recorded", "quality": "assessment_recorded", "model": "confirmed", "economy": "measurement_recorded",
        }

        config.write_text("[policy_runtime]\nschema_version = 2\n", encoding="utf-8")
        incomplete = invoke(config, entrypoint)
        assert incomplete.returncode == 1
        report = json.loads(incomplete.stdout)
        assert report["configuration"] == "incomplete"
    print("Проверка подключения политики подагентов пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

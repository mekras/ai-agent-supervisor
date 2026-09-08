#!/usr/bin/env python3
"""Проверить подготовку пилота без вызова моделей и изменения настроек."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
import tempfile
from pathlib import Path


def main() -> None:
    sys.dont_write_bytecode = True
    pilot = Path(__file__).resolve().parent
    root = pilot.parents[2]
    runner = runpy.run_path(str(root / "tools/run-skill-evals.py"))

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("Проверка подготовки не должна создавать вызов модели")

    runner["freeze_comparison"].__globals__["make_model_call"] = forbidden_model_call
    draft = runner["parse_evals_yaml"]((pilot / "evals.draft.yml").read_text(encoding="utf-8"))
    assert draft["adapters"] == {} and draft["models"] == [] and not draft["judge"]
    assert draft["workspace_models"] == []
    assert draft["repetitions"] == 1 and draft["judge_repetitions"] == 1
    # Только структурные значения для freeze_comparison, не конфигурация запуска.
    config = {"runs": [{"label": "offline-check", "adapter": [], "model": "none", "workspace": True}],
              "judge": {"label": "offline-judge", "adapter": [], "model": "none"},
              "repetitions": 1, "judge_repetitions": 1, "timeout": draft["timeout"],
              "pricing": {}, "results_dir": draft["results_dir"]}
    scratch = root / "eval-results"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pilot-preparation-", dir=scratch) as temporary:
        metadata, cases, skills = runner["freeze_comparison"](root, pilot / "plan.draft.json", config, Path(temporary))
        runner["check_comparison_snapshot"](metadata, cases, skills)
        assert metadata["plan"]["status"] == "draft_not_approved_for_model_calls"
        assert metadata["plan"]["common_background"].startswith("НЕ ПРОВЕРЕН.")
        assert [case["id"] for case in cases] == ["pilot-runbook", "pilot-release-review", "pilot-route-assessment"]
        for case in cases:
            files = runner["fixture_snapshot"](case["fixture_dir"])
            assert not any(Path(item["path"]).name in {"AGENTS.md", "CLAUDE.md", "SKILL.md"} for item in files)
            assert not any(part in {".agents", ".claude", ".codex", ".apm", "apm_modules"}
                           for item in files for part in Path(item["path"]).parts)
            oracle = case["oracle_data"]
            assert oracle["allowed_changed_paths"] == oracle["required_diff"]["paths"]
            assert oracle["failure_indicators"]
            assert runner["check_required_diff"](oracle, "", [])  # Один рассказ о правке не проходит.
            text = metadata["minimal_instructions"]["text"]
            minimal = runner["comparison_candidate_prompt"](case, "minimal", text)
            collection = runner["comparison_candidate_prompt"](case, "collection", text)
            ordinary = runner["comparison_candidate_prompt"](case, "ordinary", text)
            assert minimal == collection and text in minimal and text not in ordinary
        digests = {path.relative_to(pilot).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sorted(pilot.rglob("*")) if path.is_file()}
        print(json.dumps({"status": "preparation_structure_checked", "model_calls": 0,
            "cases": len(cases), "planned_trials": len(metadata["order"]),
            "planned_adapter_calls_at_most": len(metadata["order"]) * 2,
            "collection_packages": len(skills), "input_sha256": digests,
            "limitations": ["model_and_budget_not_approved", "runtime_environment_not_verified",
                            "semantic_acceptance_not_automated", "draft_status_is_not_a_runner_gate"]},
            ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

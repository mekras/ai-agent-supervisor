#!/usr/bin/env python3
"""Проверки детерминированной оценки выбора моделей подагентов."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".apm/skills/ai-setup-subagents/scripts/evaluate-model-selection.py"
FIXTURE = (
    ROOT
    / ".apm/skills/ai-setup-subagents/evals/script-fixtures/model-selection/complete.json"
)
SPEC = importlib.util.spec_from_file_location("evaluate_model_selection", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Не удалось загрузить оценщик моделей")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def evaluate(data: dict) -> dict:
    return MODULE.evaluate(data, "test-digest")


def candidate(data: dict, candidate_id: str) -> dict:
    return next(item for item in data["candidates"] if item["id"] == candidate_id)


def main() -> int:
    confirmed = evaluate(base())
    assert confirmed["hypothesis_status"] == "confirmed"
    assert confirmed["selected_candidate"] == "candidate-a"
    assert confirmed["policy_action"] == "owner_decision_required"
    assert confirmed["cost_comparison"]["total_cost_savings_percent"] > 40

    missing_total = base()
    for run in missing_total["runs"]:
        run.pop("total_cost_units", None)
    insufficient = evaluate(missing_total)
    assert insufficient["hypothesis_status"] == "insufficient_data"
    assert any("полная стоимость" in reason for reason in insufficient["reasons"])

    one_candidate = base()
    candidate(one_candidate, "candidate-b")["eligibility"]["within_budget"] = False
    single = evaluate(one_candidate)
    assert single["hypothesis_status"] == "insufficient_data"
    assert "минимум два" in single["reasons"][0]

    all_tuning_critical = base()
    for run in all_tuning_critical["runs"]:
        if run["candidate_id"] == "candidate-a" and run["case_id"] == "normal-1":
            run["critical_defect"] = True
    no_selection = evaluate(all_tuning_critical)
    assert no_selection["selected_candidate"] is None
    assert "все кандидаты исключены" in no_selection["reasons"][0]

    no_holdout_baseline = base()
    for run in no_holdout_baseline["runs"]:
        if run["case_id"].startswith("holdout-"):
            run["critical_defect"] = True
    no_baseline = evaluate(no_holdout_baseline)
    assert no_baseline["hypothesis_status"] == "insufficient_data"
    assert "у всех кандидатов" in no_baseline["reasons"][0]

    cost_refuted = base()
    cost_refuted["settings"]["refutation_savings_percent"] = 70
    cost_refuted["settings"]["confirmation_savings_percent"] = 80
    refuted = evaluate(cost_refuted)
    assert refuted["hypothesis_status"] == "refuted"
    assert any("экономия полной стоимости" in reason for reason in refuted["reasons"])

    interval_elimination = base()
    for run in interval_elimination["runs"]:
        if run["candidate_id"] == "candidate-b":
            run["critical_defect"] = False
    interval_report = evaluate(interval_elimination)
    assert any(
        "quality_interval" in round_item["eliminated"].values()
        for round_item in interval_report["rounds"]
    )

    critical_refuted = base()
    for run in critical_refuted["runs"]:
        if run["candidate_id"] == "candidate-b" and not run["case_id"].startswith("holdout-"):
            run["accepted_without_revision"] = True
            run["critical_defect"] = False
            run["total_cost_units"] = 1
        if run["candidate_id"] == "candidate-b" and run["case_id"].startswith("holdout-"):
            run["critical_defect"] = True
    critical_report = evaluate(critical_refuted)
    assert critical_report["hypothesis_status"] == "refuted"
    assert any("критический дефект" in reason for reason in critical_report["reasons"])

    malformed = base()
    malformed["settings"]["minimum_repeats"] = 1.5
    try:
        evaluate(malformed)
    except MODULE.InputError as error:
        assert "целое число" in str(error)
    else:
        raise AssertionError("дробное число повторов должно быть отклонено")

    negative = copy.deepcopy(base())
    negative["runs"][0]["model_cost_units"] = -1
    try:
        evaluate(negative)
    except MODULE.InputError as error:
        assert "не меньше" in str(error)
    else:
        raise AssertionError("отрицательная стоимость должна быть отклонена")

    print("Проверки выбора моделей подагентов пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

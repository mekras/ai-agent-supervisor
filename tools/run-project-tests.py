#!/usr/bin/env python3
"""Run repository checks without relying on a POSIX shell pipeline."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "tools/validate-python-artifacts.py",
    "tools/validate-python-syntax.py",
    ".apm/skills/ai-setup-apm/scripts/eval-tools/check-eval-tools-drift.py",
    "tools/test-apm-audit-ci.py",
    "tools/test-check-subagent-models.py",
    "tools/test-execution-class.py",
    "tools/test-model-selection-evaluator.py",
    "tools/test-execution-policy.py",
    "tools/test-codex-model-subagent.py",
    "tools/test-run-skill-evals.py",
    "tools/test-run-fixture-checks.py",
    "tools/test-setup-apm-collection.py",
    "tools/test-run-skill-script-contract-tests.py",
    "tools/test-run-apm-safe.py",
    "tools/test-validate-python-artifacts.py",
    "tools/test-validate-python-syntax.py",
    "tools/test-skill-portability.py",
    "tools/test-validate-apm-git-boundary.py",
    "tools/test-product-isolation.py",
    "tools/test-validate-statement-excerpts.py",
    "tools/validate-internal-source-basis.py",
    "tools/validate-statement-excerpts.py",
    "tools/validate-hidden-unicode.py",
    "tools/validate-product-boundary.py",
    "tools/validate-skill-descriptions.py",
    "tools/validate-trigger-evals.py",
    "tools/validate-skill-result-evals.py",
    "tools/validate-skill-portability.py",
    "tools/validate-fixture-evals.py",
    "tools/run-fixture-checks.py",
    "tools/validate-python-artifacts.py",
]


def main() -> int:
    target = os.environ.get("APM_EVAL_PATH", ".apm/skills")
    for relative in SCRIPTS:
        args = [sys.executable, str(ROOT / relative)]
        if relative.endswith("validate-product-boundary.py"):
            args.append(target)
        elif relative.endswith("validate-skill-descriptions.py"):
            args.append(target)
        elif relative.endswith("validate-trigger-evals.py"):
            args.extend([target, "--require-all"])
        elif relative.endswith("validate-skill-result-evals.py"):
            args.append(target)
        elif relative.endswith("validate-skill-portability.py"):
            args.append(target)
        result = subprocess.run(
            args,
            cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
    print("Все проверки проекта пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

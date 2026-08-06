#!/usr/bin/env python3
"""Проверки исполнимых контрактов поставляемых Python-скриптов навыков."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "run-skill-script-contract-tests.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_contract(skill: Path) -> None:
    fixture = skill / "evals" / "script-fixtures" / "проект с пробелом"
    fixture.mkdir(parents=True, exist_ok=True)
    contract = {
        "version": 2,
        "operations": [
            {
                "id": "save-state",
                "script": "scripts/save_state.py",
                "command_prefix": ["--output"],
            },
        ],
        "cases": [
            {
                "id": "save-state",
                "script": "scripts/save_state.py",
                "fixture": "evals/script-fixtures/проект с пробелом",
                "covers": ["save-state"],
                "command": [
                    "{python}",
                    "{script}",
                    "--output",
                    "{fixture}/state.json",
                ],
                "prepare": [
                    [
                        "{python}",
                        "-c",
                        "from pathlib import Path; Path('prepared.txt').write_text('yes')",
                    ],
                ],
                "expect": {
                    "stdout_contains": ["state_saved"],
                    "files": [
                        {"path": "state.json", "json": True, "contains": "ready"},
                    ],
                },
            },
        ],
    }
    (skill / "evals" / "script-contract-tests.json").write_text(
        json.dumps(contract, ensure_ascii=False),
        encoding="utf-8",
    )


def write_script(skill: Path, source: str) -> None:
    scripts = skill / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "---\nname: example\ndescription: Проверяет пример.\n---\n",
        encoding="utf-8",
    )
    (scripts / "save_state.py").write_text(source, encoding="utf-8")


def main() -> int:
    script = '''import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
assert os.environ.get("PYTHONDONTWRITEBYTECODE") == "1"
assert Path("prepared.txt").read_text(encoding="utf-8") == "yes"
args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")
print("state_saved")
'''
    with tempfile.TemporaryDirectory(prefix="контракт навыка ") as temporary:
        skill = Path(temporary) / "навык"
        write_script(skill, script)
        write_contract(skill)
        passed = run(skill)
        assert passed.returncode == 0, passed.stderr
        assert "Контрактные сценарии скриптов пройдены: 1." in passed.stdout

        contract_path = skill / "evals" / "script-contract-tests.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["operations"][0]["command_prefix"] = ["--inspect"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        mismatched_prefix = run(skill)
        assert mismatched_prefix.returncode == 1
        assert "команда не начинается с command_prefix операции 'save-state'" in mismatched_prefix.stderr

        write_contract(skill)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["operations"].append(
            {
                "id": "inspect-state",
                "script": "scripts/save_state.py",
                "command_prefix": ["--inspect"],
            },
        )
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        missing_operation = run(skill)
        assert missing_operation.returncode == 1
        assert "нет успешного рабочего сценария для операций: inspect-state" in missing_operation.stderr

        write_contract(skill)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["operations"][0]["inputs"] = ["project-impact.json"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        missing_input = run(skill)
        assert missing_input.returncode == 1
        assert (
            "объявленный вход project-impact.json отсутствует во всех фикстурах "
            "успешных сценариев операции 'save-state'" in missing_input.stderr
        )

        declared_input = (
            skill / "evals" / "script-fixtures" / "проект с пробелом" / "project-impact.json"
        )
        declared_input.write_text('{"version": 1}', encoding="utf-8")
        covered_input = run(skill)
        assert covered_input.returncode == 0, covered_input.stderr
        declared_input.unlink()

        write_contract(skill)

        broken = script.replace('{"status": "ready"}', '{"status": {"ready"}}')
        write_script(skill, broken)
        failed = run(skill)
        assert failed.returncode == 1
        assert "Object of type set is not JSON serializable" in failed.stderr

        other_script = skill / "scripts" / "other.py"
        other_script.write_text("print('other')\n", encoding="utf-8")
        failed_with_coverage_gap = run(skill)
        assert failed_with_coverage_gap.returncode == 1
        assert "Object of type set is not JSON serializable" in failed_with_coverage_gap.stderr
        assert "не объявлена операция для: scripts/other.py" in failed_with_coverage_gap.stderr
        other_script.unlink()

        write_script(skill, script)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["command"] = ["{python}", "{script}", "--help"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        help_only = run(skill)
        assert help_only.returncode == 1
        assert "--help не является контрактным сценарием" in help_only.stderr

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["command"] = ["{python}", "{script}"]
        contract["cases"][0]["expect"] = {
            "exit_code": 2,
            "stderr_contains": ["required"],
        }
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        failure_only = run(skill)
        assert failure_only.returncode == 1
        assert "нет успешного рабочего сценария" in failure_only.stderr

    with tempfile.TemporaryDirectory() as temporary:
        skill = Path(temporary) / "навык"
        write_script(skill, script)
        missing = run(skill)
        assert missing.returncode == 1
        assert "script-contract-tests.json" in missing.stderr

    print("Исполнимые контрактные проверки скриптов навыков проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

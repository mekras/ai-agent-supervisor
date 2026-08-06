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
    fixture.mkdir(parents=True)
    contract = {
        "version": 1,
        "cases": [
            {
                "id": "save-state",
                "script": "scripts/save_state.py",
                "fixture": "evals/script-fixtures/проект с пробелом",
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

        broken = script.replace('{"status": "ready"}', '{"status": {"ready"}}')
        write_script(skill, broken)
        failed = run(skill)
        assert failed.returncode == 1
        assert "Object of type set is not JSON serializable" in failed.stderr

        write_script(skill, script)
        contract_path = skill / "evals" / "script-contract-tests.json"
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

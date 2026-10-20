#!/usr/bin/env python3
"""Проверки исполнимых контрактов поставляемых Python-скриптов навыков."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Русские сообщения не должны падать на консоли с однобайтовой кодировкой.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "run-skill-script-contract-tests.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), str(path)],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
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
                "inputs": [],
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


def check_absence_contracts() -> None:
    """Проверить новый договор через публичную команду запускателя."""
    with tempfile.TemporaryDirectory() as temporary:
        skill = Path(temporary) / "навык отсутствия"
        write_contract(skill)
        contract_path = skill / "evals/script-contract-tests.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["version"] = 3
        case = contract["cases"][0]
        fixture = skill / case["fixture"]
        declaration = {"path": "legacy", "reason": "Устаревший слой запрещён"}
        case["absent_inputs"] = [declaration]
        ending = '''
Path('state.json').write_text('{"status": "ready"}', encoding='utf-8')
print('state_saved')
'''
        source = '''from pathlib import Path
if Path('legacy').exists():
    print('legacy forbidden')
    raise SystemExit(1)
''' + ending
        write_script(skill, source)

        def save() -> None:
            contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")

        def expect(code: int, message: str = "") -> None:
            result = run(skill)
            assert result.returncode == code, result.stderr
            assert message in result.stderr, result.stderr

        save()
        expect(0)
        # Один и тот же запрет должен отклонять как файл, так и каталог.
        legacy = fixture / "legacy"
        legacy.write_text("old", encoding="utf-8")
        expect(1, "путь legacy существует после подготовки")
        legacy.unlink()
        legacy.mkdir()
        expect(1, "путь legacy существует после подготовки")
        legacy.rmdir()
        try:
            legacy.symlink_to("nonexistent-target")
        except (OSError, NotImplementedError):
            pass
        else:
            legacy.unlink()
            case["prepare"].append(["{python}", "-c", "import os; os.symlink('nonexistent-target', 'legacy')"])
            save()
            expect(1, "путь legacy существует после подготовки")
            case["prepare"].pop()

        negative = json.loads(json.dumps(case))
        negative["id"] = "legacy-is-rejected"
        negative.pop("absent_inputs")
        negative["prepare"] = [["{python}", "-c", "from pathlib import Path; Path('legacy').mkdir()"]]
        negative["expect"] = {"exit_code": 1, "stdout_contains": ["legacy forbidden"]}
        contract["cases"].append(negative)
        save()
        expect(0)
        contract["cases"].pop()

        unscoped = json.loads(json.dumps(case))
        unscoped["id"] = "absence-is-not-global"
        unscoped.pop("absent_inputs")
        contract["cases"].append(unscoped)
        save()
        expect(1, "legacy, но не объявляет его в inputs")
        contract["cases"].pop()

        case["prepare"].append(["{python}", "-c", "from pathlib import Path; Path('legacy').touch()"])
        save()
        expect(1, "путь legacy существует после подготовки")
        case["prepare"].pop()

        write_script(skill, "from pathlib import Path\n" + ending)
        save()
        expect(1, "путь legacy не проверен командой")
        successful_expectation = case["expect"]
        case["expect"] = {"exit_code": 1, "stdout_contains": ["expected failure"]}
        write_script(skill, "print('expected failure')\nraise SystemExit(1)\n")
        save()
        expect(1, "путь legacy не проверен командой")
        case["expect"] = successful_expectation
        save()
        write_script(skill, source + "assert not Path('other').exists()\n")
        expect(1, "other, но не объявляет его в inputs")
        write_script(skill, source)

        contract["operations"][0]["inputs"] = ["legacy"]
        save()
        expect(1, "объявленный вход legacy отсутствует во всех фикстурах")
        contract["operations"][0]["inputs"] = []

        for invalid, message in [
            ("legacy", "нужен массив записей"),
            (["legacy"], "нужна запись с path и reason"),
            ([{"path": "legacy"}], "нужна непустая причина"),
            ([{"path": "legacy", "reason": "  "}], "нужна непустая причина"),
            ([{"path": "../legacy", "reason": "unsafe"}], "безопасный относительный путь"),
            ([{"path": "/legacy", "reason": "unsafe"}], "безопасный относительный путь"),
            ([{"path": "C:\\legacy", "reason": "unsafe"}], "безопасный относительный путь"),
            ([declaration, declaration], "повтор 'legacy'"),
        ]:
            case["absent_inputs"] = invalid
            save()
            expect(1, message)
        case["absent_inputs"] = [declaration]
        contract["version"] = 2
        save()
        expect(1, "требуется version: 3")
        contract["version"] = 3
        contract["operations"][0]["absent_inputs"] = ["legacy"]
        save()
        expect(1, "перенеси объявления в cases[].absent_inputs")
        contract["operations"][0].pop("absent_inputs")
        contract["version"] = 99
        save()
        expect(1, "нужен объект с version: 2 или version: 3")

        # Конфигурация выбирается по приоритету. Отсутствие не скрывает входы.
        contract["version"] = 3
        contract["operations"][0]["inputs"] = ["config.txt", "nested/config.txt"]
        case["absent_inputs"] = [{"path": "nested/config.txt", "reason": "Поиск от вложенного каталога"}]
        case["expect"]["stdout_contains"] = ["chosen: root"]
        (fixture / "config.txt").write_text("root", encoding="utf-8")
        write_script(skill, '''from pathlib import Path
selected = next((p for p in [Path('nested/config.txt'), Path('config.txt')] if p.is_file()), None)
if selected is None:
    print('no config')
    raise SystemExit(1)
print('chosen: ' + selected.read_text(encoding='utf-8'))
''' + ending)
        both = skill / "evals/script-fixtures/both"
        shutil.copytree(fixture, both)
        (both / "nested").mkdir()
        (both / "nested/config.txt").write_text("near", encoding="utf-8")
        priority = json.loads(json.dumps(case))
        priority.update(id="priority", fixture="evals/script-fixtures/both")
        priority.pop("absent_inputs")
        priority["expect"]["stdout_contains"] = ["chosen: near"]
        contract["cases"].append(priority)
        empty = skill / "evals/script-fixtures/empty"
        empty.mkdir()
        missing = json.loads(json.dumps(case))
        missing.update(id="missing-config", fixture="evals/script-fixtures/empty")
        missing["absent_inputs"].append({"path": "config.txt", "reason": "Нет ни одного кандидата"})
        missing["expect"] = {"exit_code": 1, "stdout_contains": ["no config"]}
        contract["cases"].append(missing)
        save()
        expect(0)
        priority["fixture"] = case["fixture"]
        save()
        # Настоящий вход всё равно должен присутствовать в успешной фикстуре.
        expect(1, "объявленный вход nested/config.txt отсутствует во всех фикстурах")


def check_annotation_function_coverage() -> None:
    """REQ-0007.2: отличать функции исходника от вычисления аннотаций."""
    annotated = '''def example(
    value: int,
) -> int:
    return value
'''
    user_annotation = '''def __annotate__(
    value: int,
) -> int:
    return value
'''
    cases = [
        (annotated + 'example(1)\n', None),
        (annotated, 'example'),
        ('def __annotate__(value):\n    return value\n', '__annotate__'),
        ('def __annotate__(value):\n    return value\n__annotate__(1)\n', None),
        (user_annotation, '__annotate__'),
        (user_annotation + '__annotate__(1)\n', None),
        # При общей строке сигнатуры и тела проверка по строкам неприменима.
        ('''def __annotate__(
    value: int,
) -> int: return value
print(__annotate__.__annotations__)
''', None),
        (annotated + user_annotation +
         'example(1)\nprint(example.__annotations__)\n', '__annotate__'),
        (annotated + user_annotation +
         'example(1)\nprint(example.__annotations__)\n__annotate__(1)\n', None),
        ('''def outer():
    def inner(value: int) -> int:
        return value
    return inner(1)
outer()
''', None),
        ('''def outer():
    def inner(value: int) -> int:
        return value
outer()
''', 'outer.<locals>.inner'),
        ('''class Example:
    def method(self, value: int) -> int:
        return value
Example().method(1)
''', None),
        ('''class Example:
    def method(self, value: int) -> int:
        return value
''', 'Example.method'),
        ('''def decorate(function):
    return function
@(
    decorate
)
def example(value: int) -> int:
    return value
example(1)
''', None),
        ('''def decorate(function):
    return function
@decorate
def example(value: int) -> int:
    return value
''', 'example'),
        ('''import asyncio
async def example(value: int) -> int:
    return value
asyncio.run(example(1))
''', None),
        ('''async def example(value: int) -> int:
    return value
''', 'example'),
    ]
    with tempfile.TemporaryDirectory() as temporary:
        skill = Path(temporary) / 'аннотации'
        write_contract(skill)
        contract_path = skill / 'evals/script-contract-tests.json'
        contract = json.loads(contract_path.read_text(encoding='utf-8'))
        contract['cases'][0]['expect'] = {'stdout_contains': ['fixture-ok']}
        contract_path.write_text(json.dumps(contract), encoding='utf-8')
        for future in ('', 'from __future__ import annotations\n'):
            contract.pop('unexercised_functions', None)
            contract_path.write_text(json.dumps(contract), encoding='utf-8')
            for source, missing in cases:
                write_script(skill, future + source + 'print("fixture-ok")\n')
                result = run(skill)
                assert result.returncode == (1 if missing else 0), (
                    sys.version, future + source, result.stdout, result.stderr
                )
                if missing:
                    assert f'функция {missing} не выполнена ни одним сценарием' in result.stderr
            contract['unexercised_functions'] = [{
                'script': 'scripts/save_state.py',
                'function': '__annotate__',
                'reason': 'защитный отказ для внешнего окружения',
            }]
            contract_path.write_text(json.dumps(contract), encoding='utf-8')
            allowance_cases = [
                (annotated + 'example(1)\n', 1, 'неизвестную функцию __annotate__'),
                ('''def __annotate__(
    value: int,
) -> int: return value
print(__annotate__.__annotations__)
''', 1, 'неизвестную функцию __annotate__'),
                (user_annotation, 0, ''),
                (user_annotation + '__annotate__(1)\n', 1,
                 'запись unexercised_functions о функции __annotate__ устарела'),
            ]
            for source, code, message in allowance_cases:
                write_script(skill, future + source + 'print("fixture-ok")\n')
                result = run(skill)
                assert result.returncode == code, (sys.version, source, result.stderr)
                assert message in result.stderr


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
        del contract["operations"][0]["inputs"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        missing_input_inventory = run(skill)
        assert missing_input_inventory.returncode == 1
        assert (
            ".inputs: нужен явный массив. Пустой массив означает, "
            "что условные входы операции проверены и не найдены"
            in missing_input_inventory.stderr
        )

        write_contract(skill)
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
                "inputs": [],
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

        existing_file = (
            skill / "evals" / "script-fixtures" / "проект с пробелом" / "project-impact.json"
        )
        existing_directory = (
            skill / "evals" / "script-fixtures" / "проект с пробелом" / "src"
        )
        existing_file.write_text('{"version": 1}', encoding="utf-8")
        existing_directory.mkdir()
        type_probe_script = script.replace(
            'args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")',
            '''impact_path = Path("project-impact.json")
source_path = Path("src")
assert not impact_path.is_dir()
assert not source_path.is_file()
assert not os.path.isdir("project-impact.json")
assert not os.path.isfile("src")
args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")''',
        )
        write_script(skill, type_probe_script)
        existing_paths_are_not_missing_inputs = run(skill)
        assert existing_paths_are_not_missing_inputs.returncode == 0, (
            existing_paths_are_not_missing_inputs.stderr
        )
        existing_file.unlink()
        existing_directory.rmdir()

        output_probe_script = script.replace(
            'args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")',
            '''state = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {"status": "ready"}
temporary_output = args.output.with_suffix(".tmp")
temporary_output.write_text(json.dumps(state), encoding="utf-8")
os.replace(temporary_output, args.output)''',
        )
        write_script(skill, output_probe_script)
        output_is_not_input = run(skill)
        assert output_is_not_input.returncode == 0, output_is_not_input.stderr

        mixed_paths_script = script.replace(
            'args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")',
            '''impact_path = Path("project-impact.json")
impact = json.loads(impact_path.read_text(encoding="utf-8")) if impact_path.is_file() else None
state = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {"status": "ready"}
state["impact"] = impact
temporary_output = args.output.with_suffix(".tmp")
temporary_output.write_text(
    json.dumps(state),
    encoding="utf-8",
)
os.replace(temporary_output, args.output)''',
        )
        write_script(skill, mixed_paths_script)
        undeclared_conditional_input = run(skill)
        assert undeclared_conditional_input.returncode == 1
        assert (
            "операция 'save-state' проверяет отсутствующий путь "
            "project-impact.json, но не объявляет его в inputs"
            in undeclared_conditional_input.stderr
        )
        assert "state.json, но не объявляет его в inputs" not in undeclared_conditional_input.stderr

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["operations"][0]["inputs"] = ["project-impact.json"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        declared_input.write_text('{"version": 1}', encoding="utf-8")
        traced_input_covered = run(skill)
        assert traced_input_covered.returncode == 0, traced_input_covered.stderr

        declared_input.write_text(
            '{"version": 1, "nodes": [], "edges": []}',
            encoding="utf-8",
        )
        degenerate_input = run(skill)
        assert degenerate_input.returncode == 1
        assert "содержит только пустые коллекции" in degenerate_input.stderr

        declared_input.write_text(
            '{"version": 1, "nodes": [{"id": "a"}], "edges": []}',
            encoding="utf-8",
        )
        meaningful_input = run(skill)
        assert meaningful_input.returncode == 0, meaningful_input.stderr
        declared_input.unlink()

        write_contract(skill)
        dead_branch_script = script.replace(
            'args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")',
            '''state = {"status": "ready"}
if os.environ.get("APM_NEVER_SET_MARKER"):
    state["scope"] = {"paths": set()}
args.output.write_text(json.dumps(state), encoding="utf-8")''',
        )
        write_script(skill, dead_branch_script)
        uncovered_branch = run(skill)
        assert uncovered_branch.returncode == 0, uncovered_branch.stderr
        assert "сценарии не выполнили" in uncovered_branch.stdout
        assert "кандидаты проверки по риску" in uncovered_branch.stdout

        write_script(skill, script)
        full_coverage = run(skill)
        assert full_coverage.returncode == 0, full_coverage.stderr
        assert "сценарии выполнили все" in full_coverage.stdout

        dead_function_script = script.replace(
            'args.output.write_text(json.dumps({"status": "ready"}), encoding="utf-8")',
            '''def build_scope():
    return {"paths": []}

state = {"status": "ready"}
if os.environ.get("APM_NEVER_SET_MARKER"):
    state["scope"] = build_scope()
args.output.write_text(json.dumps(state), encoding="utf-8")''',
        )
        write_script(skill, dead_function_script)
        unexecuted_function = run(skill)
        assert unexecuted_function.returncode == 1
        assert (
            "функция build_scope не выполнена ни одним сценарием"
            in unexecuted_function.stderr
        )

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["unexercised_functions"] = [
            {
                "script": "scripts/save_state.py",
                "function": "build_scope",
                "reason": "ветвь активируется только внешней переменной среды",
            },
        ]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        acknowledged_function = run(skill)
        assert acknowledged_function.returncode == 0, acknowledged_function.stderr
        assert (
            "непроверенные функции по объявленным причинам: build_scope"
            in acknowledged_function.stdout
        )

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["unexercised_functions"][0]["function"] = "missing_helper"
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        unknown_function = run(skill)
        assert unknown_function.returncode == 1
        assert "неизвестную функцию missing_helper" in unknown_function.stderr

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["unexercised_functions"][0]["function"] = "build_scope"
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        live_function_script = dead_function_script.replace(
            '''if os.environ.get("APM_NEVER_SET_MARKER"):
    state["scope"] = build_scope()''',
            'state["scope"] = build_scope()',
        )
        write_script(skill, live_function_script)
        stale_allowance = run(skill)
        assert stale_allowance.returncode == 1
        assert (
            "запись unexercised_functions о функции build_scope устарела"
            in stale_allowance.stderr
        )

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

        # Внешняя команда сценария: отсутствие среды — не нарушение контракта.
        write_contract(skill)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["requires"] = ["команда-которой-нет"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        skipped = run(skill)
        assert skipped.returncode == 0, skipped.stderr
        assert "сценарий пропущен" in skipped.stdout and "команда-которой-нет" in skipped.stdout
        assert "Пропущено сценариев из-за отсутствующих внешних команд: 1." in skipped.stdout
        assert "Контрактные сценарии скриптов пройдены: 0." in skipped.stdout

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["requires"] = ["git"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        available = run(skill)
        assert available.returncode == 0, available.stderr
        assert "Контрактные сценарии скриптов пройдены: 1." in available.stdout
        assert "пропущен" not in available.stdout

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["requires"] = ["tools/apm"]
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        path_in_requires = run(skill)
        assert path_in_requires.returncode == 1
        assert "нужно имя внешней команды без пути" in path_in_requires.stderr

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["cases"][0]["requires"] = "apm"
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        broken_requires = run(skill)
        assert broken_requires.returncode == 1
        assert "нужен массив непустых имён внешних команд" in broken_requires.stderr

    with tempfile.TemporaryDirectory() as temporary:
        skill = Path(temporary) / "навык"
        write_script(skill, script)
        missing = run(skill)
        assert missing.returncode == 1
        assert "script-contract-tests.json" in missing.stderr

    check_absence_contracts()
    check_annotation_function_coverage()
    print("Исполнимые контрактные проверки скриптов навыков проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

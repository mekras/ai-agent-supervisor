#!/usr/bin/env python3
"""Проверки валидатора переносимости навыков."""

from __future__ import annotations

import copy
import json
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
VALIDATOR = ROOT / ".apm/skills/ai-setup-apm/scripts/eval-tools/validate-skill-portability.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_skill(root: Path, frontmatter: str, procedure: str, script: str) -> None:
    skill = root / "навык с пробелом"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: example\n{frontmatter}---\n\n# Example\n\n"
        f"## Переносимость\n\n{procedure}\n",
        encoding="utf-8",
    )
    (scripts / "check.py").write_text(script, encoding="utf-8")
    fixture = skill / "evals" / "script-fixtures" / "empty"
    fixture.mkdir(parents=True)
    (skill / "evals" / "script-contract-tests.json").write_text(
        """{
  "version": 2,
  "operations": [
    {
      "id": "check",
      "script": "scripts/check.py",
      "command_prefix": [],
      "inputs": []
    }
  ],
  "cases": [
    {
      "id": "check",
      "script": "scripts/check.py",
      "fixture": "evals/script-fixtures/empty",
      "covers": ["check"],
      "command": ["{python}", "{script}"],
      "expect": {"stdout_contains": ["ok"]}
    }
  ]
}
""",
        encoding="utf-8",
    )


def regression_checks() -> None:
    """Проверить режим процесса, собственные модули и границы исключений."""
    compatibility = "compatibility: Python 3.10+.\n"
    procedure = "P0 работает вручную без скрипта. Если Python недоступен, используется P0."

    def check(
        script: str,
        files: dict[str, str] | None = None,
        dependency: dict | None = None,
        expected_error: str | None = None,
        frontmatter: str = "",
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_skill(root, compatibility + frontmatter, procedure, script)
            skill = root / "навык с пробелом"
            for relative, content in (files or {}).items():
                path = skill / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            if dependency is not None:
                references = skill / "references"
                references.mkdir(exist_ok=True)
                (references / "dependency-exceptions.json").write_text(
                    json.dumps({"schema_version": 1, "dependencies": [dependency]}),
                    encoding="utf-8",
                )
            # Соседние модули также получают успешный контракт поставляемой команды.
            contract_path = skill / "evals/script-contract-tests.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            for path in sorted((skill / "scripts").glob("*.py")):
                if path.name == "check.py":
                    continue
                relative = path.relative_to(skill).as_posix()
                operation = {"id": path.stem, "script": relative, "command_prefix": [], "inputs": []}
                case = copy.deepcopy(contract["cases"][0])
                case.update(id=path.stem, script=relative, covers=[path.stem])
                contract["operations"].append(operation)
                contract["cases"].append(case)
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            result = run(root)
            if expected_error is None:
                assert result.returncode == 0, result.stderr
            else:
                assert result.returncode == 1, result.stderr
                assert expected_error in result.stderr, result.stderr

    for function in ("run", "Popen", "check_output"):
        for flag in ("", ", text=False", ", universal_newlines=False", ", text=False, universal_newlines=False"):
            check(
                f"import subprocess\nimport sys\n"
                f"subprocess.{function}([sys.executable, '-c', \"print('ok')\"]{flag})\n"
                "print('ok')\n"
            )
        for flag in ("text=True", "universal_newlines=True", "text=True, encoding=None", "text=False, errors='replace'"):
            check(
                f"import subprocess\nsubprocess.{function}([], {flag})\n",
                expected_error="текстовом режиме без encoding",
            )
    check(
        "import subprocess\nimport sys\nsubprocess.run([sys.executable, '-c', \"print('ok')\"], text=True, encoding='utf-8')\nprint('ok')\n"
    )
    check(
        "import subprocess\nsubprocess.run([], text=mode)\n",
        expected_error="не удалось определить режим",
    )
    check(
        "import subprocess\nsubprocess.run([], text=True, encoding=codec)\n",
        expected_error="не удалось проверить encoding",
    )
    check(
        "from evaluation_suite import VALUE\nprint(VALUE)\n",
        {"scripts/evaluation_suite.py": "VALUE = 'ok'\nprint(VALUE)\n"},
    )
    check(
        "from package.module import VALUE\nprint(VALUE)\n",
        {
            "scripts/package/__init__.py": "",
            "scripts/package/module.py": "from .helper import VALUE\n",
            "scripts/package/helper.py": "VALUE = 'ok'\n",
        },
    )
    check("from evaluation_suite import VALUE\n", expected_error="evaluation_suite")
    check(
        "from evaluation_suite import VALUE\n",
        {"evals/evaluation_suite.py": "VALUE = 'ok'\n"},
        expected_error="evaluation_suite",
    )
    check(
        "from evaluation_suite import VALUE\n",
        {"scripts/unrelated/evaluation_suite.py": "VALUE = 'ok'\n"},
        expected_error="evaluation_suite",
    )
    check(
        "from evaluation_suite import VALUE\n",
        {"scripts/evaluation_suite.py": "import yaml\nVALUE = 'ok'\nprint(VALUE)\n"},
        expected_error="yaml",
    )

    approved = {
        "package": "PyYAML", "imports": ["yaml"], "version": "6.0.2",
        "scripts": ["scripts/check.py"],
        "approval": {"status": "approved", "owner": "Владелец тестового навыка", "decision": "references/approval.md"},
        "justification": "Чтение YAML в необязательной автоматизации.",
        "installation": {"command": "python -m pip install --require-hashes -r requirements.txt", "integrity": "sha256:" + "a" * 64},
        "source": "https://pypi.org/project/PyYAML/6.0.2/", "license": "MIT", "network": True,
        "absence_behavior": "Остановить автоматизацию с понятным сообщением.",
        "basic_route": "Вручную прочитать YAML и проверить данные без пакета.",
    }
    evidence = {"references/approval.md": "Владелец тестового навыка разрешил PyYAML 6.0.2 для scripts/check.py.\n"}
    # Тест не устанавливает пакет и не требует его присутствия в окружении.
    external_script = "if False:\n    import yaml\nprint('ok')\n"
    check(external_script, evidence, approved)
    check(external_script, frontmatter="optional_dependencies: PyYAML\n", expected_error="yaml")
    for field in approved:
        incomplete = copy.deepcopy(approved)
        del incomplete[field]
        check(external_script, evidence, incomplete, expected_error=field)
    for owner_field in ("status", "owner", "decision"):
        incomplete = copy.deepcopy(approved)
        del incomplete["approval"][owner_field]
        check(external_script, evidence, incomplete, expected_error=owner_field)
    for install_field in ("command", "integrity"):
        incomplete = copy.deepcopy(approved)
        del incomplete["installation"][install_field]
        check(external_script, evidence, incomplete, expected_error=install_field)
    check(external_script, dependency=approved, expected_error="approval.decision")
    for field, value in (
        ("scripts", ["scripts/other.py"]),
        ("scripts", ["scripts/bad\x00path.py"]),
        ("imports", ["other"]),
        ("network", "false"),
        ("approval", {"status": "pending", "owner": "Owner", "decision": "references/approval.md"}),
        ("installation", {"command": "install", "integrity": "unverified"}),
        ("approval", {"owner": "Owner", "decision": "../outside.md"}),
    ):
        invalid = copy.deepcopy(approved)
        invalid[field] = value
        check(external_script, evidence, invalid, expected_error="yaml" if field == "imports" else field)
    check(
        external_script,
        {"references/dependency-exceptions.json": "{"},
        expected_error="dependency-exceptions.json",
    )
    for manifest, expected_error in (
        ({"schema_version": 2, "dependencies": []}, "schema_version"),
        ({"schema_version": True, "dependencies": []}, "schema_version"),
        ({"schema_version": 1, "dependencies": {}}, "dependencies"),
        ({"schema_version": 1, "dependencies": [None]}, "объект исключения"),
        ({"schema_version": 1, "dependencies": [approved, approved]}, "повторное исключение"),
    ):
        check(
            external_script,
            {**evidence, "references/dependency-exceptions.json": json.dumps(manifest)},
            expected_error=expected_error,
        )
    wrong_scope = copy.deepcopy(approved)
    wrong_scope["scripts"] = ["scripts/other.py"]
    check(external_script, {**evidence, "scripts/other.py": "print('ok')\n"}, wrong_scope, expected_error="yaml")
    helper_approved = copy.deepcopy(approved)
    helper_approved["scripts"] = ["scripts/evaluation_suite.py"]
    check(
        "from evaluation_suite import VALUE\nprint(VALUE)\n",
        {**evidence, "scripts/evaluation_suite.py": "if False:\n    import yaml\nVALUE = 'ok'\nprint(VALUE)\n"},
        helper_approved,
    )
    check("import yaml\n", evidence, helper_approved, expected_error="scripts")


def main() -> int:
    regression_checks()
    with tempfile.TemporaryDirectory(prefix="переносимость ") as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта. Если Python недоступен, проверка помечается как невыполненная.",
            "#!/usr/bin/env python3\nimport json\nprint(json.dumps({'ok': True}))\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "",
            "Скрипт обязателен.",
            "#!/usr/bin/env python3\nimport yaml\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "нет поля compatibility" in failed.stderr
        assert "не описан базовый маршрут P0" in failed.stderr
        assert "сторонние импорты запрещены" in failed.stderr
        assert "yaml" in failed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает, если Python отсутствует.",
            "#!/usr/bin/env python3\n# pip install unsafe\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "скрытая установка" in failed.stderr

    # Печать русского текста без переключения потоков ломает консоль Windows.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nprint('готово')\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "не переключает" in failed.stderr

    # Текстовый файл без кодировки читается кодовой страницей системы.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nfrom pathlib import Path\n"
            "Path('data.txt').write_text('ok')\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "без encoding" in failed.stderr

    # Чтение вывода дочернего процесса без кодировки ломается на Windows.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nimport subprocess\n"
            "subprocess.run(['git', 'status'], text=True)\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "без encoding" in failed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nimport sys\n"
            "sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
            "print('ok')\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    # Открытие файла без кодировки остаётся ошибкой.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\n"
            "with open('data.txt') as stream:\n    stream.read()\n",
        )
        failed = run(root)
        assert failed.returncode == 1
        assert "без encoding" in failed.stderr

    # os.open возвращает дескриптор, кодировки у него нет.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nimport os\n"
            "with open('data.bin', 'wb') as stream:\n    stream.write(b'ok')\n"
            "fd = os.open('data.bin', os.O_RDONLY)\n"
            "with os.fdopen(fd, 'rb') as stream:\n    stream.read()\n"
            "print('ok')\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    # Режим, заданный выражением, не считается подтверждённым текстовым.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nmode = 'rb'\n"
            "with open('data.bin', 'wb') as stream:\n    stream.write(b'ok')\n"
            "with open('data.bin', mode) as stream:\n    stream.read()\n"
            "print('ok')\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    # Двоичный режим у Path.open не требует кодировки.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_skill(
            root,
            "compatibility: P0 не требует Python. P1 требует Python 3.\n",
            "P0 работает без скрипта, если Python недоступен.",
            "#!/usr/bin/env python3\nfrom pathlib import Path\n"
            "with open('data.bin', 'wb') as stream:\n    stream.write(b'ok')\n"
            "with Path('data.bin').open('rb') as stream:\n    stream.read()\n"
            "print('ok')\n",
        )
        passed = run(root)
        assert passed.returncode == 0, passed.stderr

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        skill = root / "навык с пробелом"
        scripts = skill / "scripts"
        scripts.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            """---
name: example
compatibility: P0 не требует Python. P1 требует Python 3.
---

# Example

## Переносимость

P0 работает без скрипта. Если Python недоступен, проверка помечается как невыполненная.
""",
            encoding="utf-8",
        )
        (scripts / "check.py").write_text("print('ok')\n", encoding="utf-8")
        failed = run(root)
        assert failed.returncode == 1
        assert "script-contract-tests.json" in failed.stderr

    print("Валидатор переносимости навыков проверен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

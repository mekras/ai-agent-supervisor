#!/usr/bin/env python3
"""Проверки создания манифеста APM без внешнего YAML-пакета."""

from __future__ import annotations

import os
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
SETUP = ROOT / ".apm/skills/ai-setup-apm/scripts/setup-apm-collection"


def fixture_environment() -> dict[str, str]:
    """Не передавать выбор навыков внешнего проекта во временный проект."""
    environment = os.environ.copy()
    environment.pop("APM_EVAL_PATH", None)
    return environment


def run(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SETUP), str(project), *extra],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def check_repeat_setup_delivery() -> None:
    """Проверить доставку после обновления навыка при независимых старых tests."""
    with tempfile.TemporaryDirectory(prefix="повторная настройка ") as temporary:
        project = Path(temporary)
        skill = project / ".agents/skills/ai-setup-apm"
        shutil.copytree(SETUP.parent.parent, skill)
        manifest_path = project / "apm.yml"
        manifest = "name: existing-collection\nversion: 1.0.0\nscripts:\n  tests: python checks.py\n"
        manifest_path.write_text(manifest, encoding="utf-8")
        custom_check = project / "checks.py"
        custom_check.write_text('print("existing checks passed")\n', encoding="utf-8")
        checker = skill / "scripts/eval-tools/check-eval-tools-drift.py"
        installer = skill / "scripts/install-eval-tools"

        def invoke(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                list(args), cwd=project, env=fixture_environment(), check=False,
                text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

        assert invoke(sys.executable, str(custom_check)).returncode == 0
        assert (skill / "scripts/eval-tools/apm-audit-ci").is_file()
        auditor = project / "tools/apm-audit-ci"
        assert not auditor.exists()
        missing = invoke(sys.executable, str(checker))
        assert missing.returncode == 1, missing.stdout + missing.stderr
        assert "нет рабочей копии: tools/apm-audit-ci" in missing.stderr

        # Переносимая доставка Python работает и без POSIX-оболочки.
        # Bash-установщик дополнительно проверяется там, где запускается напрямую.
        python_install = (
            "import runpy, sys; from pathlib import Path; "
            "runpy.run_path(sys.argv[1])['install_eval_tools'](Path(sys.argv[2]))"
        )
        install_commands = [(sys.executable, "-c", python_install,
                             str(skill / "scripts/setup-apm-collection"), str(project))]
        if os.name == "posix":
            install_commands.append((str(installer), str(project)))
        for command in install_commands:
            installed = invoke(*command)
            assert installed.returncode == 0, installed.stdout + installed.stderr
            if command[0] == str(installer):
                assert f"installed={project}" in installed.stdout
        for line in (skill / "scripts/eval-tools/manifest.txt").read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            source, destination, mode = line.split("|")
            working_copy = project / destination
            assert working_copy.read_bytes() == (skill / "scripts/eval-tools" / source).read_bytes(), destination
            if os.name == "posix":
                assert working_copy.stat().st_mode & 0o777 == int(mode, 8), destination
        assert manifest_path.read_text(encoding="utf-8") == manifest
        assert custom_check.read_text(encoding="utf-8") == 'print("existing checks passed")\n'
        complete = invoke(sys.executable, str(checker))
        assert complete.returncode == 0, complete.stdout + complete.stderr

        # Прежние tests продолжают проходить, если из комплекта исчез один файл.
        for command in install_commands:
            auditor.unlink()
            assert invoke(sys.executable, str(custom_check)).returncode == 0
            incomplete = invoke(sys.executable, str(checker))
            assert incomplete.returncode == 1
            assert "нет рабочей копии: tools/apm-audit-ci" in incomplete.stderr
            restored = invoke(*command)
            assert restored.returncode == 0, restored.stdout + restored.stderr
            assert invoke(sys.executable, str(checker)).returncode == 0

        adapter = project / "tools/adapters/codex"
        own_content = "#!/bin/sh\nprintf 'project-owned adapter'\n"
        adapter.write_text(own_content, encoding="utf-8")
        conflict = invoke(sys.executable, str(checker))
        assert conflict.returncode == 1
        assert "расхождение: tools/adapters/codex" in conflict.stderr
        assert adapter.read_text(encoding="utf-8") == own_content


def main() -> int:
    check_repeat_setup_delivery()
    with tempfile.TemporaryDirectory(prefix="навык с пробелом ") as temporary:
        project = Path(temporary)
        shutil.copytree(
            ROOT / ".apm" / "skills" / "ai-setup-apm",
            project / ".apm" / "skills" / "ai-setup-apm",
        )
        created = run(
            project,
            "--name",
            "example-package",
            "--description",
            "Example collection",
            "--target",
            "codex",
            "--target",
            "claude",
        )
        assert created.returncode == 0, created.stderr
        manifest = (project / "apm.yml").read_text(encoding="utf-8")
        assert 'name: "example-package"' in manifest
        assert '  - "codex"' in manifest
        assert '  - "claude"' in manifest
        assert 'tests: "python tools/run-collection-checks.py"' in manifest
        assert 'evals: "python tools/run-skill-evals.py"' in manifest
        assert (project / ".apm" / "skills").is_dir()
        assert (project / "tools" / "run-collection-checks.py").is_file()
        assert (project / "tools" / "validate-skill-descriptions.py").is_file()
        assert (project / "tools" / "validate-python-artifacts.py").is_file()
        assert (project / "tools" / "validate-python-syntax.py").is_file()
        assert (project / "tools" / "run-apm-safe.py").is_file()
        assert (project / "tools" / "run-skill-script-contract-tests.py").is_file()
        checks = subprocess.run(
            [sys.executable, str(project / "tools" / "run-collection-checks.py")],
            cwd=project,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=fixture_environment(),
        )
        assert checks.returncode == 0, checks.stdout + checks.stderr

        cache = project / ".apm" / "skills" / "example" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "check.cpython-313.pyc").write_bytes(b"bytecode")
        rejected = subprocess.run(
            [sys.executable, str(project / "tools" / "run-collection-checks.py")],
            cwd=project,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=fixture_environment(),
        )
        assert rejected.returncode == 1
        assert "скомпилированные Python-артефакты" in rejected.stderr

        repeated = run(project)
        assert repeated.returncode == 2
        assert "уже существует" in repeated.stderr
        assert (project / "apm.yml").read_text(encoding="utf-8") == manifest

    help_result = subprocess.run(
        [sys.executable, str(SETUP), "--help"],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert help_result.returncode == 0
    assert "Create apm.yml" in help_result.stdout
    print("Создание и повторная доставка оснастки, пропажа аудитора и конфликт адаптера проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

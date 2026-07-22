#!/usr/bin/env python3
"""Проверки изоляции публикуемой коллекции от проекта-разработчика."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_SKILLS = ROOT / ".apm" / "skills"
BOUNDARY_CHECK = ROOT / "tools" / "validate-product-boundary.py"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        skills = project / ".apm" / "skills"
        shutil.copytree(SOURCE_SKILLS, skills)

        boundary = run(sys.executable, str(BOUNDARY_CHECK), str(skills), cwd=project)
        assert boundary.returncode == 0, boundary.stderr

        setup_skill = skills / "ai-setup-apm"
        installer = setup_skill / "scripts" / "install-eval-tools"
        installed = run(str(installer), str(project), cwd=project)
        assert installed.returncode == 0, installed.stderr
        assert f"installed={project}" in installed.stdout

        assert not (project / "knowledge").exists()
        obsolete_files = (
            project / "tools" / "corpus_statements.py",
            project / "tools" / "test-corpus-statements.py",
            project / "tools" / "validate-portable-corpus-references.py",
        )
        assert not any(path.exists() for path in obsolete_files)

        result_check = run(
            sys.executable,
            str(project / "tools" / "validate-skill-result-evals.py"),
            str(skills),
            cwd=project,
        )
        assert result_check.returncode == 0, result_check.stderr

        (project / "apm.yml").write_text(
            """name: isolated-product-check
version: 0.0.0
type: skill
scripts:
  tests: >-
    sh -c 'set -e; target=".apm/skills";
    python3 tools/validate-hidden-unicode.py;
    python3 tools/validate-skill-descriptions.py "$target";
    python3 tools/validate-trigger-evals.py "$target" --require-all;
    python3 tools/validate-skill-result-evals.py "$target"'
""",
            encoding="utf-8",
        )
        apm_test = run("apm", "run", "tests", cwd=project)
        assert apm_test.returncode == 0, apm_test.stdout + apm_test.stderr

        leaking = project / "leaking-product"
        leaking.mkdir()
        (leaking / "example.md").write_text(
            """Внутренняя ссылка: knowledge/data/example.
Поле сценария: "source_basis".
Служебное основание: APMP-001.
Исторический пакет: ai-dev-team.
Локальный путь: /home/example/project.
Тариф разработчика: ChatGPT Pro 5x.
""",
            encoding="utf-8",
        )
        rejected = run(
            sys.executable,
            str(BOUNDARY_CHECK),
            str(leaking),
            cwd=project,
        )
        assert rejected.returncode == 1
        expected_leaks = (
            "внутренний корпус",
            "внутренняя прослеживаемость сценариев",
            "внутренний идентификатор источника",
            "историческое имя проекта или пакета",
            "локальный абсолютный путь",
            "конкретный внутренний пример тарифа",
        )
        assert all(label in rejected.stderr for label in expected_leaks)

    print("Проверки изоляции публикуемого продукта пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

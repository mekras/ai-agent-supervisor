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
CLAUDE_INSTRUCTIONS = ROOT / ".claude" / "CLAUDE.md"


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
    assert not (ROOT / "CLAUDE.md").exists()
    assert CLAUDE_INSTRUCTIONS.read_text(encoding="utf-8") == "@../AGENTS.md\n"

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
  tests: python tools/run-collection-checks.py
""",
            encoding="utf-8",
        )
        apm_test = run("apm", "run", "tests", cwd=project)
        assert apm_test.returncode == 0, apm_test.stdout + apm_test.stderr

        shutil.copy(ROOT / "AGENTS.md", project / "AGENTS.md")
        (project / ".claude").mkdir()
        shutil.copy(CLAUDE_INSTRUCTIONS, project / ".claude" / "CLAUDE.md")

        with tempfile.TemporaryDirectory() as consumer_temporary:
            consumer = Path(consumer_temporary)
            local_install = run(
                "apm",
                "install",
                str(project),
                "--target",
                "claude",
                cwd=consumer,
            )
            assert local_install.returncode == 0, (
                local_install.stdout + local_install.stderr
            )

            compile_result = run(
                "apm",
                "compile",
                "--target",
                "claude",
                cwd=consumer,
            )
            assert compile_result.returncode == 0, (
                compile_result.stdout + compile_result.stderr
            )
            assert not (consumer / "CLAUDE.md").exists()
            dependency_entries = list(
                (consumer / "apm_modules").rglob(".claude/CLAUDE.md")
            )
            assert len(dependency_entries) == 1

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

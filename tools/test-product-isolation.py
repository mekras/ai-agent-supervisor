#!/usr/bin/env python3
"""Проверки изоляции публикуемой коллекции от проекта-разработчика."""

from __future__ import annotations

import os
import runpy
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
SOURCE_SKILLS = ROOT / ".apm" / "skills"
BOUNDARY_CHECK = ROOT / "tools" / "validate-product-boundary.py"
CLAUDE_INSTRUCTIONS = ROOT / ".claude" / "CLAUDE.md"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def check_consumer_audit(consumer: Path) -> None:
    """Проверить доставленный аудитор и весь цикл на локальных входах потребителя."""
    fixture = runpy.run_path(str(consumer / "tools/test-apm-audit-ci.py"))
    with tempfile.TemporaryDirectory(prefix="аудит потребителя ") as temporary:
        project = Path(temporary)
        fake = fixture["write_project"](project)
        lock = project / "apm.lock.yaml"
        _, _, deployments = lock.read_text(encoding="utf-8").partition("deployments:")
        lock.write_text(
            "dependencies:\n- repo_url: example/local-package\n"
            "  name: local-package\n  version: 1.0.0\n"
            "deployments:" + deployments, encoding="utf-8",
        )
        shutil.copytree(consumer / "tools", project / "tools")
        fake_source = project / "fake-apm"
        original = fake_source.read_text(encoding="utf-8")
        # Подставной APM сохраняет lock-граф при install и возвращает дрейф при audit.
        fake_source.write_text(
            original.replace("import json\n", "import json, sys\nif sys.argv[1] == 'install': raise SystemExit(0)\n"),
            encoding="utf-8",
        )
        fake_command = project / ("apm.cmd" if os.name == "nt" else "apm")
        shutil.copy2(fake, fake_command)
        command = [
            sys.executable, "-S", str(project / "tools/run-apm-safe.py"),
            "--project-root", str(project), "--apm", str(fake_command),
            "--audit-runner", "tools/apm-audit-ci",
        ]
        env = {**os.environ, "PATH": str(project) + os.pathsep + os.environ.get("PATH", ""),
               "PYTHONDONTWRITEBYTECODE": "1"}
        def cycle() -> subprocess.CompletedProcess[str]:
            return subprocess.run(command, cwd=project, env=env, check=False,
                                  text=True, encoding="utf-8", errors="replace",
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        accepted = cycle()
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "подтверждено файлов — 1" in accepted.stdout
        deployed = project / ".agents/skills/example/SKILL.md"
        deployed.write_text("unrelated edit\n", encoding="utf-8")
        rejected = cycle()
        assert rejected.returncode == 1, rejected.stdout + rejected.stderr
        assert '"modified"' in rejected.stdout


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
            installed_skill = consumer / ".claude/skills/ai-setup-apm"
            consumer_installer = installed_skill / "scripts/install-eval-tools"
            delivered = run(str(consumer_installer), str(consumer), cwd=consumer)
            assert delivered.returncode == 0, delivered.stdout + delivered.stderr
            assert (consumer / "tools/apm-audit-ci").read_bytes() == (
                setup_skill / "scripts/eval-tools/apm-audit-ci"
            ).read_bytes()
            check_consumer_audit(consumer)

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

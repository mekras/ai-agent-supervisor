#!/usr/bin/env python3
"""Проверить, что выпуск ждёт общую матрицу переносимости."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PORTABILITY = ROOT / ".github" / "workflows" / "portability.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CHECKS = ROOT / ".github" / "workflows" / "portability-checks.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def jobs(text: str) -> str:
    marker = "jobs:\n"
    assert marker in text
    return text.split(marker, 1)[1]


def check_package_documentation(release: str) -> None:
    # Исполняем настоящие команды копирования в изолированном каталоге пакета.
    start = release.index('          mkdir -p "$candidate_dir"')
    end = release.index('          python3 tools/sync-marketplace-manifest.py', start)
    commands = "\n".join(line[10:] for line in release[start:end].splitlines())
    bash = shutil.which("bash")
    if bash is None:
        raise AssertionError("Для проверки сборки документации требуется bash")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        previous = root / "previous"
        previous.mkdir()
        (previous / "apm.yml").write_text("name: fixture\n", encoding="utf-8")
        candidate = root / "candidate"
        subprocess.run(
            [bash, "-euc", commands], cwd=ROOT, check=True,
            env={**os.environ, "candidate_dir": candidate.as_posix(),
                 "package_dir": previous.as_posix()},
        )
        for base in (ROOT, candidate):
            readme = read(base / "README.md")
            targets = re.findall(r"\]\((docs/[^)#]+)(?:#[^)]*)?\)", readme)
            assert {"docs/hermes.md", "docs/concept.md", "docs/intro.webp"} <= set(targets)
            for target in targets:
                path = base / target
                assert path.is_file(), f"Недоступна ссылка README: {path}"
                assert path.stat().st_size, f"Пустой документ: {path}"
            assert (base / "docs/../README.md").is_file()
        for target in targets:
            assert (candidate / target).read_bytes() == (ROOT / target).read_bytes()


def main() -> int:
    checks = read(CHECKS)
    portability = read(PORTABILITY)
    release = read(RELEASE)

    assert "workflow_call:" in checks
    assert "windows-latest" in checks
    assert "macos-latest" in checks
    assert "ubuntu-latest" in checks
    assert "deterministic-tests:" in checks
    assert jobs(portability) == jobs(checks)
    assert "verify-portability:" in release
    assert "needs: verify-portability" in release
    assert release.index("needs: verify-portability") < release.index("name: Проверить и опубликовать")
    assert "Проверить опубликованный пакет в изолированном проекте" in release
    assert 'apm marketplace add "$GITHUB_WORKSPACE/marketplace" --name release-test --ref master' in release
    assert 'apm install "${PACKAGE_NAME}@release-test" --target codex' in release
    assert "python3 tools/sync-marketplace-manifest.py" in release
    assert "--source apm.yml" in release
    assert '--package "$candidate_dir/apm.yml"' in release
    assert '--version "$RELEASE_VERSION"' in release
    assert "apm pack --marketplace=claude,codex" in release
    assert release.index("Опубликовать версию пакета") < release.index(
        "Проверить опубликованный пакет в изолированном проекте"
    )
    check_package_documentation(release)
    print("Выпуск ожидает матрицу переносимости и проверяет опубликованный пакет отдельно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

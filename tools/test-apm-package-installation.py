#!/usr/bin/env python3
"""Проверить установку кандидата пакета для каждой заявленной цели APM."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    manifest = yaml.safe_load((ROOT / "apm.yml").read_text(encoding="utf-8"))
    manifest.pop("devDependencies", None)
    with tempfile.TemporaryDirectory(prefix="apm-package-") as temporary:
        workspace = Path(temporary)
        candidate = workspace / "candidate"
        shutil.copytree(ROOT / ".apm", candidate / ".apm")
        (candidate / "apm.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        (candidate / "docs").mkdir()
        for path in (
            "README.md", "CHANGELOG.md", "LICENSE",
            "docs/hermes.md", "docs/concept.md", "docs/intro.webp",
        ):
            shutil.copy2(ROOT / path, candidate / path)

        for target in manifest["target"]:
            consumer = workspace / target
            consumer.mkdir()
            subprocess.run(
                ["apm", "install", str(candidate), "--target", target], cwd=consumer, check=True
            )
            skill_root = ".claude" if target == "claude" else ".agents"
            skill = consumer / skill_root / "skills" / "ai-setup-apm" / "SKILL.md"
            if not skill.is_file() or not skill.stat().st_size:
                raise SystemExit(f"APM не развернул навык ai-setup-apm для цели {target}.")
            subprocess.run(["apm", "audit", "--ci"], cwd=consumer, check=True)


if __name__ == "__main__":
    main()

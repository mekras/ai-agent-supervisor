#!/usr/bin/env python3
"""Проверить синхронизацию манифеста кандидата выпуска."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools/sync-marketplace-manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_marketplace_manifest", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить преобразование манифеста")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    source_text = (
        "name: ai-agent-supervisor\n"
        "version: 9.9.9\n"
        "description: исходное описание\n"
        "target:\n"
        "- claude\n"
        "- codex\n"
        "- hermes\n"
        "type: skill\n"
        "devDependencies:\n"
        "  apm:\n"
        "  - internal/development#^1.0.0\n"
    )
    package_text = (
        "name: ai-agent-supervisor\n"
        "version: 1.0.0\n"
        "description: описание пакета\n"
        "target:\n"
        "- claude\n"
        "- codex\n"
        "type: skill\n"
        "includes: auto\n"
        "dependencies:\n"
        "  apm: []\n"
        "  mcp: []\n"
    )
    expected = (
        "name: ai-agent-supervisor\n"
        "version: 2.6.13\n"
        "description: описание пакета\n"
        "target:\n"
        "- claude\n"
        "- codex\n"
        "- hermes\n"
        "type: skill\n"
        "includes: auto\n"
        "dependencies:\n"
        "  apm: []\n"
        "  mcp: []\n"
    )
    with tempfile.TemporaryDirectory(prefix="sync-marketplace-manifest-") as temporary:
        directory = Path(temporary)
        source = directory / "source-apm.yml"
        package = directory / "package-apm.yml"
        source.write_text(source_text, encoding="utf-8")
        package.write_text(package_text, encoding="utf-8")
        module.sync_manifest(source, package, "2.6.13")
        result = package.read_text(encoding="utf-8")
        assert result == expected
        assert "devDependencies:" not in result
        assert "internal/development" not in result
        assert result.count("- claude") == 1
        assert result.count("- codex") == 1
        assert result.count("- hermes") == 1
        try:
            module.sync_manifest(source, package, "2.6.13\\n")
        except ValueError as error:
            assert "формат SemVer" in str(error)
        else:
            raise AssertionError("некорректная версия принята")
    print("Проверка синхронизации target манифеста выпуска пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

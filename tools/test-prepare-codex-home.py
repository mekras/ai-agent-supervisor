#!/usr/bin/env python3
"""Проверить безопасную подготовку отдельного CODEX_HOME."""

from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools/compatibility/prepare_codex_home.py"
AUTH_SENTINEL = "auth-only-sentinel"
HEADER_SENTINEL = "Bearer telemetry-sentinel"
IRRELEVANT_SENTINEL = "must-not-copy"


def load_tool():
    spec = importlib.util.spec_from_file_location("prepare_codex_home", TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить инструмент подготовки CODEX_HOME")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def create_source(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    (source / "auth.json").write_text(AUTH_SENTINEL, encoding="utf-8")
    (source / "config.toml").write_text(
        """[otel]
environment = "test-environment"
metrics_exporter = { otlp-http = { endpoint = "https://otel.example/v1/metrics", protocol = "binary", headers = { Authorization = "Bearer telemetry-sentinel" } } }

[mcp_servers.unrelated]
secret = "must-not-copy"
""",
        encoding="utf-8",
    )
    return source


def test_copies_only_auth_and_otel_with_safe_modes() -> None:
    with tempfile.TemporaryDirectory(prefix="prepare-codex-home-") as temporary:
        root = Path(temporary)
        source = create_source(root)
        destination = root / "destination"
        result = subprocess.run(
            [sys.executable, str(TOOL_PATH), "--source", str(source), "--destination", str(destination)],
            check=False,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert result.returncode == 0
        assert AUTH_SENTINEL not in result.stdout + result.stderr
        assert HEADER_SENTINEL not in result.stdout + result.stderr
        assert stat.S_IMODE(destination.stat().st_mode) == 0o700
        assert stat.S_IMODE((destination / "auth.json").stat().st_mode) == 0o600
        assert stat.S_IMODE((destination / "config.toml").stat().st_mode) == 0o600
        assert sorted(path.name for path in destination.iterdir()) == ["auth.json", "config.toml"]
        assert (destination / "auth.json").read_text(encoding="utf-8") == AUTH_SENTINEL
        output_config = (destination / "config.toml").read_text(encoding="utf-8")
        assert output_config.startswith('cli_auth_credentials_store = "file"')
        assert "[otel]" in output_config
        assert 'environment = "test-environment"' in output_config
        assert "metrics_exporter =" in output_config
        assert 'endpoint = "https://otel.example/v1/metrics"' in output_config
        assert 'protocol = "binary"' in output_config
        assert HEADER_SENTINEL in output_config
        assert IRRELEVANT_SENTINEL not in output_config
        assert (source / "auth.json").read_text(encoding="utf-8") == AUTH_SENTINEL


def test_refuses_existing_targets_and_overlapping_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="prepare-codex-home-refuse-") as temporary:
        root = Path(temporary)
        source = create_source(root)
        destination = root / "destination"
        destination.mkdir()
        existing_auth = destination / "auth.json"
        existing_auth.write_text("existing", encoding="utf-8")
        try:
            tool.prepare(source, destination)
        except ValueError as error:
            assert "уже существуют" in str(error)
        else:
            raise AssertionError("Инструмент перезаписал существующий auth.json")
        assert existing_auth.read_text(encoding="utf-8") == "existing"

        try:
            tool.prepare(source, source)
        except ValueError as error:
            assert "пересекаться" in str(error)
        else:
            raise AssertionError("Инструмент принял исходный каталог как назначение")

        nested = source / "nested-destination"
        try:
            tool.prepare(source, nested)
        except ValueError as error:
            assert "пересекаться" in str(error)
        else:
            raise AssertionError("Инструмент принял назначение внутри исходного каталога")

        linked_destination = root / "linked-destination"
        linked_destination_target = root / "linked-destination-target"
        linked_destination_target.mkdir()
        linked_destination.symlink_to(linked_destination_target, target_is_directory=True)
        try:
            tool.prepare(source, linked_destination)
        except ValueError as error:
            assert "символической ссылкой" in str(error)
        else:
            raise AssertionError("Инструмент принял символическую ссылку как назначение")


def main() -> int:
    test_copies_only_auth_and_otel_with_safe_modes()
    test_refuses_existing_targets_and_overlapping_paths()
    print("Проверки подготовки CODEX_HOME пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

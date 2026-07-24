#!/usr/bin/env python3
"""Детерминированные проверки запускателя классов исполнения."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".apm/skills/ai-setup-subagents/scripts/run-execution-class"
CLAUDE_ROLE = ROOT / ".apm/skills/ai-setup-subagents/scripts/adapters/claude-role"
CLAUDE_INSTALLER = ROOT / ".apm/skills/ai-setup-subagents/scripts/install-claude-tools"
LOADER = importlib.machinery.SourceFileLoader("claude_role", str(CLAUDE_ROLE))
SPEC = importlib.util.spec_from_loader("claude_role", LOADER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Не удалось загрузить адаптер Claude")
CLAUDE_ROLE_MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(CLAUDE_ROLE_MODULE)


def write_fixture(directory: Path, actual_model: str) -> Path:
    adapter = directory / "adapter.py"
    adapter.write_text(
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "request = json.loads(input())\n"
        "assert request['contract']['writes'] is False\n"
        "assert request['inputs']\n"
        "Path(os.environ['CODEX_ROLE_LOG']).write_text('{}\\n')\n"
        f"print(json.dumps({{'model': '{actual_model}', 'usage': {{'input_tokens': 1}}}}))\n"
        "print('готово')\n",
        encoding="utf-8",
    )
    return adapter


def write_config(directory: Path, adapter: Path, prefix: str = "") -> Path:
    config = directory / "subagents.local.toml"
    prefix_line = f'actual_model_prefix = "{prefix}"\n' if prefix else ""
    config.write_text(
        textwrap.dedent(
            f"""
            [execution_classes.cheap_readonly_research]
            writes = false
            result = "status, evidence"

            [targets.claude.execution_classes.cheap_readonly_research]
            model = "haiku"
            effort = "low"
            sandbox = "read-only"
            adapter = ["{sys.executable}", "{adapter}"]
            {prefix_line}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config


def run(config: Path, out: Path, input_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(RUNNER),
            "cheap_readonly_research",
            "--target",
            "claude",
            "--config",
            str(config),
            "--out",
            str(out),
            "--input",
            str(input_file),
        ],
        input="Найди один факт.",
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        input_file = directory / "input.md"
        input_file.write_text("факт\n", encoding="utf-8")

        matching = write_fixture(directory, "claude-haiku-4-5")
        config = write_config(directory, matching, "claude-haiku-")
        success = run(config, directory / "success", input_file)
        assert success.returncode == 0, success.stderr
        record = json.loads(success.stdout)
        assert record["assigned_model"] == "haiku"
        assert record["actual_model"] == "claude-haiku-4-5"
        assert record["model_matches"]
        for key in ("final", "stderr", "journal"):
            assert Path(record[key]).is_file()

        mismatched = write_fixture(directory, "claude-opus-4-8")
        failed_config = write_config(directory, mismatched, "claude-haiku-")
        failed = run(failed_config, directory / "failed", input_file)
        assert failed.returncode == 1
        assert not json.loads(failed.stderr)["model_matches"]

        installed_root = directory / "installed-project"
        installed = subprocess.run(
            [str(CLAUDE_INSTALLER), str(installed_root)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert installed.returncode == 0, installed.stderr
        assert "installed=" in installed.stdout
        installed_runner = installed_root / "tools/run-execution-class"
        installed_adapter = installed_root / "tools/adapters/claude-role"
        assert installed_runner.read_bytes() == RUNNER.read_bytes()
        assert installed_adapter.read_bytes() == CLAUDE_ROLE.read_bytes()

    stream = "\n".join(
        [
            json.dumps({"type": "system", "model": "claude-haiku-4-5"}),
            json.dumps(
                {
                    "type": "system",
                    "subtype": "informational",
                    "content": "Model \"haiku\" is restricted.",
                }
            ),
            json.dumps(
                {"type": "assistant", "message": {"model": "claude-opus-4-8"}}
            ),
            json.dumps(
                {
                    "type": "result",
                    "result": "готово",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ),
        ]
    )
    model, usage, result, notice = CLAUDE_ROLE_MODULE.response_details(stream)
    assert model == "claude-opus-4-8"
    assert usage == {"input_tokens": 1, "output_tokens": 1}
    assert result == "готово"
    assert notice == "Model \"haiku\" is restricted."

    print("Проверка классов исполнения пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

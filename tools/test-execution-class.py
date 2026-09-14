#!/usr/bin/env python3
"""Детерминированные проверки запускателя классов исполнения."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import contextlib
import io
import json
import runpy
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

# Русские сообщения не должны падать на консоли с однобайтовой кодировкой.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".apm/skills/ai-setup-subagents/scripts/run-execution-class"
MODEL_EVALUATOR = ROOT / ".apm/skills/ai-setup-subagents/scripts/evaluate-model-selection.py"
MODEL_EVALUATOR_SAMPLE = ROOT / ".apm/skills/ai-setup-subagents/assets/model-selection-input.sample.json"
CLAUDE_ROLE = ROOT / ".apm/skills/ai-setup-subagents/scripts/adapters/claude-role"
CLAUDE_INSTALLER = ROOT / ".apm/skills/ai-setup-subagents/scripts/install-claude-tools"
LOADER = importlib.machinery.SourceFileLoader("claude_role", str(CLAUDE_ROLE))
SPEC = importlib.util.spec_from_loader("claude_role", LOADER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Не удалось загрузить адаптер Claude")
CLAUDE_ROLE_MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(CLAUDE_ROLE_MODULE)


def write_fixture(directory: Path, actual_model: str, *, evidence=True, journal=True,
                  wrong_reference=False) -> Path:
    adapter = directory / "adapter.py"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "request = json.loads(input())\n"
        "assert request['contract']['writes'] is False\n"
        "assert request['inputs']\n"
        + (f"Path(os.environ['CODEX_ROLE_LOG']).write_text(json.dumps({{'message': {{'model': '{actual_model}'}}}}) + '\\n')\n" if journal else "")
        + f"header = {{'model': '{actual_model}', 'usage': {{'input_tokens': 1}}}}\n"
        + (f"header['model_evidence'] = {{'source': 'journal', 'line': {2 if wrong_reference else 1}, 'field': ['message', 'model']}}\n" if evidence else "")
        + "print(json.dumps(header))\n"
        "print('готово')\n",
        encoding="utf-8",
    )
    adapter.chmod(0o755)
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

            [roles.reviewer]
            model = "claude-haiku-4-5"
            effort = "low"
            sandbox = "read-only"
            adapter = "{adapter}"
            [roles.reviewer.contract]
            writes = false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config


def run(
    config: Path, out: Path, input_file: Path, obligation: str | None = None
) -> subprocess.CompletedProcess[str]:
    arguments = [
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
    ]
    if obligation is not None:
        arguments.extend(["--obligation", obligation])
    return subprocess.run(
        arguments,
        input="Найди один факт.",
        text=True,
        encoding="utf-8",
        errors="replace",
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
        success = run(config, directory / "success", input_file, "security-review")
        assert success.returncode == 0, success.stderr
        record = json.loads(success.stdout)
        assert record["assigned_model"] == "haiku"
        assert record["actual_model"] == "claude-haiku-4-5"
        assert record["model_matches"]
        assert record["model_status"] == "confirmed"
        assert record["model_evidence"]["line"] == 1
        assert len(record["model_evidence"]["sha256"]) == 64
        assert record["obligation_id"] == "security-review"
        assert record["run_id"]
        assert record["result_available"]
        assert record["returncode"] == 0
        assert record["result_path"] == record["final"]
        for key in ("final", "stderr", "journal"):
            assert Path(record[key]).is_file()

        mismatched = write_fixture(directory, "claude-opus-4-8")
        failed_config = write_config(directory, mismatched, "claude-haiku-")
        failed = run(failed_config, directory / "failed", input_file, "security-review")
        assert failed.returncode == 1
        failed_record = json.loads(failed.stderr)
        assert failed_record["obligation_id"] == "security-review"
        assert not failed_record["model_matches"]

        matching = write_fixture(directory, "claude-haiku-4-5")
        config = write_config(directory, matching, "claude-haiku-")
        legacy = run(config, directory / "legacy", input_file)
        assert legacy.returncode == 0, legacy.stderr
        assert "obligation_id" not in json.loads(legacy.stdout)

        for name, options in (
            ("missing-evidence", {"evidence": False}),
            ("missing-journal", {"journal": False}),
            ("bad-reference", {"wrong_reference": True}),
        ):
            adapter = write_fixture(directory, "claude-haiku-4-5", **options)
            config = write_config(directory, adapter, "claude-haiku-")
            unknown = run(config, directory / name, input_file, "security-review")
            assert unknown.returncode == 1, unknown.stdout
            unknown_record = json.loads(unknown.stderr)
            assert unknown_record["model_status"] == "unconfirmed"
            assert unknown_record["actual_model"] is None
            assert unknown_record["model_matches"] is None
            assert unknown_record["result_available"]

        for evidence in (False, True):
            adapter = write_fixture(directory, "claude-haiku-4-5", evidence=evidence)
            config = write_config(directory, adapter)
            role = subprocess.run(
                [str(RUNNER.with_name("run-subagent-role")), "reviewer",
                 "--config", str(config), "--input", str(input_file),
                 "--out", str(directory / f"role-{evidence}")],
                input="Проверь факт.", text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            assert role.returncode == (0 if evidence else 1), role.stderr
            role_record = json.loads(role.stdout if evidence else role.stderr)
            assert role_record["model_status"] == ("confirmed" if evidence else "unconfirmed")

        installed_root = directory / "installed-project"
        installed = subprocess.run(
            [str(CLAUDE_INSTALLER), str(installed_root)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert installed.returncode == 0, installed.stderr
        assert "installed=" in installed.stdout
        installed_runner = installed_root / "tools/run-execution-class"
        installed_evaluator = installed_root / "tools/evaluate-model-selection.py"
        installed_sample = installed_root / "tools/model-selection-input.sample.json"
        installed_adapter = installed_root / "tools/adapters/claude-role"
        assert installed_runner.read_bytes() == RUNNER.read_bytes()
        assert (installed_root / "tools/run-subagent-role").read_bytes() == (
            ROOT / ".apm/skills/ai-setup-subagents/scripts/run-subagent-role"
        ).read_bytes()
        assert installed_evaluator.read_bytes() == MODEL_EVALUATOR.read_bytes()
        assert installed_sample.read_bytes() == MODEL_EVALUATOR_SAMPLE.read_bytes()
        assert installed_adapter.read_bytes() == CLAUDE_ROLE.read_bytes()
        assert (installed_root / "tools/lib/model_evidence.py").read_bytes() == (
            RUNNER.parent / "lib/model_evidence.py"
        ).read_bytes()

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

    actual, reference = CLAUDE_ROLE_MODULE.model_evidence(stream)
    assert actual == model and reference["line"] == 3
    assert CLAUDE_ROLE_MODULE.model_evidence('{"type":"system","model":"assigned"}') == (None, None)
    conflict = stream + '\n' + json.dumps({"type": "assistant", "message": {"model": "other"}})
    assert CLAUDE_ROLE_MODULE.model_evidence(conflict) == (None, None)

    # Успешный процесс без свидетельства модели не подтверждает назначение.
    output = io.StringIO()
    temporary = MagicMock()
    temporary.__enter__.return_value = "/unused-model-evidence-test"
    completed = subprocess.CompletedProcess([], 0, '{"type":"turn.completed","usage":{}}\n', '')
    with patch('sys.argv', ['codex-role', 'requested-model', 'low', 'read-only']), \
         patch('sys.stdin', io.StringIO('{}')), \
         patch('tempfile.TemporaryDirectory', return_value=temporary), \
         patch('subprocess.run', return_value=completed), \
         patch('pathlib.Path.exists', return_value=False), \
         patch('pathlib.Path.write_text'), contextlib.redirect_stdout(output):
        try:
            runpy.run_path(str(RUNNER.parent / 'adapters/codex-role'), run_name='__main__')
        except SystemExit as exit_status:
            assert exit_status.code == 0
    assert json.loads(output.getvalue())["model"] is None
    assert json.loads(output.getvalue())["model_evidence"] is None

    print("Проверка классов исполнения пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

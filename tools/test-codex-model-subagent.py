#!/usr/bin/env python3
"""Регрессии приёмки завершённого запуска Codex."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNERS = (
    ROOT / ".apm/skills/ai-setup-subagents/scripts/codex-model-subagent",
    ROOT / "tools/codex-model-subagent",
)


def write_mock_codex(directory: Path) -> Path:
    command = directory / "codex"
    command.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
final = arguments[arguments.index("-o") + 1]
mode = os.environ["MOCK_CODEX_MODE"]
if mode != "incomplete_error":
    with open(final, "w", encoding="utf-8") as output:
        output.write("model answer\\n")
print(json.dumps({"type": "thread.started", "thread_id": "test-thread"}))
if mode != "incomplete_error":
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}}))
print("manager warning", file=sys.stderr)
raise SystemExit(17 if mode != "success" else 0)
""",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command


def parse_paths(output: str) -> dict[str, Path]:
    values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    return {name: Path(values[name]) for name in ("jsonl", "final", "stderr")}


def run_case(runner: Path, directory: Path, mode: str) -> subprocess.CompletedProcess[str]:
    output = directory / f"output-{runner.parents[0].name}-{mode}"
    environment = {
        **os.environ,
        "PATH": f"{directory}:{os.environ['PATH']}",
        "CODEX_SUBAGENT_OUT_DIR": str(output),
        "CODEX_SUBAGENT_USAGE_LINE": "0",
        "MOCK_CODEX_MODE": mode,
    }
    return subprocess.run(
        [str(runner), "test-model", "acceptance", "test prompt"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        write_mock_codex(directory)
        for runner in RUNNERS:
            successful = run_case(runner, directory, "success")
            assert successful.returncode == 0
            assert "status=completed\n" in successful.stdout
            assert "process_exit_code=0\n" in successful.stdout
            for path in parse_paths(successful.stdout).values():
                assert path.is_file()

            completed_with_error = run_case(runner, directory, "completed_error")
            assert completed_with_error.returncode == 0
            assert "status=completed_with_process_error\n" in completed_with_error.stdout
            assert "process_exit_code=17\n" in completed_with_error.stdout
            accepted_paths = parse_paths(completed_with_error.stdout)
            assert accepted_paths["final"].read_text(encoding="utf-8") == "model answer\n"
            assert "manager warning" in accepted_paths["stderr"].read_text(encoding="utf-8")

            failed = run_case(runner, directory, "incomplete_error")
            assert failed.returncode == 17
            assert "status=failed\n" in failed.stdout
            assert not parse_paths(failed.stdout)["final"].exists()

    print("Проверки приёмки запускателя Codex пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

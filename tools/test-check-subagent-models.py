#!/usr/bin/env python3
"""Детерминированные проверки переносимого средства проверки моделей."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".apm/skills/ai-setup-subagents/scripts/check-subagent-models"
DISCOVER = ROOT / ".apm/skills/ai-setup-subagents/scripts/discover-subagent-models"
ANALYZER = ROOT / ".apm/skills/ai-setup-subagents/scripts/analyze-subagent-sessions"
ROLE_RUNNER = ROOT / ".apm/skills/ai-setup-subagents/scripts/run-subagent-role"


def make_adapter(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text("#!/usr/bin/env sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def run(*args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [str(CHECKER), "--json", *args], text=True, capture_output=True, check=False
    )
    return completed.returncode, json.loads(completed.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        good = make_adapter(directory, "good", "cat >/dev/null\nprintf 'OK\\n'\n")
        bad = make_adapter(directory, "bad", "cat >/dev/null\necho denied >&2\nexit 9\n")
        slow = make_adapter(directory, "slow", "cat >/dev/null\nsleep 2\n")

        code, result = run("--adapter", f"good={good}", "--model", "good:ready")
        assert code == 0 and result["models"][0]["status"] == "available"

        code, result = run("--adapter", f"bad={bad}", "--model", "bad:denied")
        assert code == 1 and result["models"][0]["status"] == "unavailable"

        code, result = run("--adapter", f"slow={slow}", "--timeout", "1", "--model", "slow:late")
        assert code == 1 and result["models"][0]["status"] == "unverified"

        code, result = run("--model", "missing:model")
        assert code == 1 and result["models"][0]["status"] == "unverified"

        catalog = make_adapter(directory, "catalog", "if [ \"$1\" = list ]; then printf '%s\\n' '{\"harness\":\"other\",\"models\":[{\"id\":\"family-exact\",\"hidden\":false,\"supportedReasoningEfforts\":[{\"reasoningEffort\":\"low\"}]}]}'; else exit 2; fi\n")
        discovered = subprocess.run([str(DISCOVER), "--adapter", str(catalog)], text=True, capture_output=True, check=False)
        payload = json.loads(discovered.stdout)
        assert discovered.returncode == 0 and payload["harness"] == "other" and payload["models"][0]["id"] == "family-exact"

        unavailable = make_adapter(directory, "unavailable", "exit 5\n")
        discovered = subprocess.run([str(DISCOVER), "--adapter", str(unavailable)], text=True, capture_output=True, check=False)
        assert discovered.returncode == 1 and json.loads(discovered.stdout)["status"] == "not_received"

        sessions = directory / "sessions" / "2026" / "07" / "10"; sessions.mkdir(parents=True)
        cwd = "/project"
        parent = [
            {"type":"session_meta","payload":{"cwd":cwd}},
            {"type":"turn_context","payload":{"model":"exact-model"}},
            {"type":"response_item","payload":{"type":"function_call","name":"apply_patch"}},
            {"type":"event_msg","payload":{"type":"task_complete"}},
        ]
        child = [{"type":"session_meta","payload":{"cwd":cwd,"source":{"subagent":{"thread_spawn":{"agent_path":None,"agent_role":None}}}}}, {"type":"event_msg","payload":{"type":"task_complete"}}]
        (sessions / "parent.jsonl").write_text("\n".join(json.dumps(x) for x in parent), encoding="utf-8")
        (sessions / "child.jsonl").write_text("\n".join(json.dumps(x) for x in child), encoding="utf-8")
        report = subprocess.run([str(ANALYZER), "--sessions", str(directory / "sessions"), "--cwd", cwd, "--min-sessions", "1", "--min-turns", "1", "--min-days", "1"], text=True, capture_output=True, check=False)
        analysis = json.loads(report.stdout)
        assert analysis["history_sufficient"] and analysis["parent_sessions"] == 1 and analysis["child_runs"] == 1 and analysis["file_change_sessions"] == 1
        assert "apply_patch" not in report.stdout and "parent.jsonl" not in report.stdout
        assert analysis["child_model_inheritance_signals"] == 1
        insufficient = subprocess.run([str(ANALYZER), "--sessions", str(directory / "sessions"), "--cwd", cwd, "--min-sessions", "2", "--min-turns", "2", "--min-days", "2"], text=True, capture_output=True, check=False)
        assert not json.loads(insufficient.stdout)["history_sufficient"]

        role_adapter = make_adapter(directory, "role", "cat >/dev/null\nprintf '{\"model\":\"wrong\"}\\n'\n")
        role_config = directory / "roles.toml"
        role_config.write_text("[roles.reviewer]\nmodel = 'exact'\neffort = 'low'\nsandbox = 'read-only'\nadapter = '" + str(role_adapter) + "'\ncontract = { writes = false }\n", encoding="utf-8")
        failed_role = subprocess.run([str(ROLE_RUNNER), "reviewer", "--config", str(role_config), "--out", str(directory / "runs")], input="no prompt is retained", text=True, capture_output=True, check=False)
        assert failed_role.returncode != 0
    print("Проверка моделей подагентов пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

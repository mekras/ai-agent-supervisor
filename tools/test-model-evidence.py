#!/usr/bin/env python3
"""Проверяет сбор клиентских и серверных свидетельств запуска."""

from __future__ import annotations

import json
import runpy
import sqlite3
import sys
import tempfile
from pathlib import Path


for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(
    str(ROOT / ".apm/skills/ai-setup-subagents/scripts/lib/model_evidence.py")
)
collect = MODULE["collect_execution_evidence"]


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )


def write_database(path: Path, rollout_path: str = "rollout.jsonl") -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE thread_records (id TEXT, model TEXT, reasoning_effort TEXT, rollout_path TEXT)"
    )
    connection.execute(
        "INSERT INTO thread_records VALUES (?, ?, ?, ?)",
        ("thread-1", "model-a", "low", rollout_path),
    )
    connection.commit()
    connection.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        journal = root / "adapter.jsonl"
        codex_home = root / "codex-home"
        codex_home.mkdir()
        rollout = codex_home / "rollout.jsonl"
        write_jsonl(
            journal,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {
                    "type": "turn_context",
                    "model": "model-a",
                    "effort": "low",
                    "collaboration_mode": {"settings": {"reasoning_effort": "low"}},
                },
                {"type": "world_state", "state": {"model": "model-a"}},
            ],
        )
        write_jsonl(
            rollout,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn_context", "payload": {"model": "model-a", "effort": "low"}},
            ],
        )
        write_database(codex_home / "state-42.db")

        confirmed = collect(
            journal,
            assigned_model="model-a",
            assigned_effort="low",
            codex_home=codex_home,
        )
        assert confirmed["thread_id"] == "thread-1"
        assert confirmed["actual_model"] == "model-a"
        assert confirmed["actual_effort"] == "low"
        assert confirmed["model_status"] == "confirmed"
        assert confirmed["effort_status"] == "confirmed"
        assert confirmed["model_matches"] is True
        assert confirmed["effort_matches"] is True
        assert confirmed["client_route_status"] == "confirmed"
        assert confirmed["server_model_status"] == "unconfirmed"
        assert confirmed["server_effort_status"] == "unconfirmed"
        assert {item["source"] for item in confirmed["model_evidence"]["sources"]} == {
            "codex_rollout",
            "codex_sqlite",
        }
        assert all(
            item["confirmation_boundary"] == "client_execution"
            for item in confirmed["model_evidence"]["sources"]
        )

        model_mismatch = collect(
            journal,
            assigned_model="model-b",
            assigned_effort="low",
            codex_home=codex_home,
        )
        assert model_mismatch["model_status"] == "confirmed"
        assert model_mismatch["model_matches"] is False
        assert model_mismatch["client_route_status"] == "mismatch"

        effort_mismatch = collect(
            journal,
            assigned_model="model-a",
            assigned_effort="high",
            codex_home=codex_home,
        )
        assert effort_mismatch["effort_status"] == "confirmed"
        assert effort_mismatch["effort_matches"] is False
        assert effort_mismatch["client_route_status"] == "mismatch"

        missing = collect(
            root / "missing.jsonl",
            assigned_model="model-a",
            assigned_effort="low",
            codex_home=codex_home,
        )
        assert missing["thread_status"] == "missing"
        assert missing["model_status"] == "unconfirmed"
        assert missing["model_evidence_reason"] == "missing_evidence"

        unknown = root / "unknown.jsonl"
        write_jsonl(unknown, [{"type": "turn_context", "model": "model-a", "effort": "low"}])
        unknown_result = collect(unknown, assigned_model="model-a", assigned_effort="low")
        assert unknown_result["actual_model"] is None
        assert unknown_result["model_evidence_reason"] == "ambiguous_thread"
        assert unknown_result["client_route_status"] == "unconfirmed"

        unknown_format = root / "unknown-format.jsonl"
        write_jsonl(
            unknown_format,
            [
                {"type": "thread.started", "thread_id": "thread-unknown"},
                {"type": "future_event", "payload": {"model": "model-a", "effort": "low"}},
            ],
        )
        unknown_format_result = collect(
            unknown_format,
            assigned_model="model-a",
            assigned_effort="low",
            codex_home=codex_home,
        )
        assert unknown_format_result["thread_status"] == "resolved"
        assert unknown_format_result["model_status"] == "unconfirmed"
        assert unknown_format_result["model_evidence_reason"] == "missing_evidence"

        mismatched_rollout_home = root / "mismatched-rollout-home"
        mismatched_rollout_home.mkdir()
        mismatched_rollout = mismatched_rollout_home / "rollout.jsonl"
        write_jsonl(
            mismatched_rollout,
            [
                {"type": "thread.started", "thread_id": "another-thread"},
                {"type": "turn_context", "model": "model-a", "effort": "low"},
            ],
        )
        write_database(mismatched_rollout_home / "state-other.sqlite", "rollout.jsonl")
        mismatched_rollout_result = collect(
            journal,
            assigned_model="model-a",
            assigned_effort="low",
            codex_home=mismatched_rollout_home,
        )
        assert mismatched_rollout_result["model_status"] == "unconfirmed"
        assert mismatched_rollout_result["model_evidence_reason"] == "ambiguous_thread"

        repeated = root / "repeated.jsonl"
        write_jsonl(
            repeated,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn_context", "model": "model-a", "effort": "low"},
                {"type": "turn_context", "model": "model-a", "effort": "low"},
            ],
        )
        repeated_result = collect(repeated, assigned_model="model-a", assigned_effort="low")
        assert repeated_result["model_status"] == "confirmed"
        assert repeated_result["effort_status"] == "confirmed"

        changed = root / "changed.jsonl"
        write_jsonl(
            changed,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn_context", "model": "model-a", "effort": "low"},
                {"type": "turn_context", "model": "model-b", "effort": "high"},
            ],
        )
        changed_result = collect(
            changed,
            header={
                "model": "model-a",
                "model_evidence": {
                    "source": "journal",
                    "line": 2,
                    "field": ["model"],
                },
                "effort": "low",
                "effort_evidence": {
                    "source": "journal",
                    "line": 2,
                    "field": ["effort"],
                },
            },
            assigned_model="model-a",
            assigned_effort="low",
        )
        assert changed_result["actual_model"] is None
        assert changed_result["actual_effort"] is None
        assert changed_result["model_status"] == "conflict"
        assert changed_result["effort_status"] == "conflict"
        assert changed_result["client_route_status"] == "conflict"

        server_journal = root / "server.jsonl"
        write_jsonl(
            server_journal,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "response.completed", "server": {"model": "model-a", "effort": "low"}},
            ],
        )
        server_result = collect(server_journal, assigned_model="model-a", assigned_effort="low")
        assert server_result["model_status"] == "confirmed"
        assert server_result["client_model_status"] == "unconfirmed"
        assert server_result["server_model_status"] == "confirmed"
        assert server_result["model_evidence"]["confirmation_boundary"] == "server_execution"
        assert server_result["server_model_matches"] is True

    print("Проверка свидетельств модели и усилия пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

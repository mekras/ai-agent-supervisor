#!/usr/bin/env python3
"""Проверяет механическую миграцию старой политики подагентов."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".apm/skills/ai-setup-subagents/scripts/migrate-subagent-policy.py"
FIXTURE = ROOT / ".apm/skills/ai-setup-subagents/evals/script-fixtures/policy-migration"
ASSET = ROOT / ".apm/skills/ai-setup-subagents/assets/worker-policy-entrypoint.md"
START = "<!-- ai-setup-subagents:runtime-policy:start -->"
END = "<!-- ai-setup-subagents:runtime-policy:end -->"


def run(config: Path, entrypoint: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(SCRIPT),
        "--config",
        str(config),
        "--entrypoint",
        f"codex={entrypoint}",
    ]
    if check:
        command.append("--check")
    return subprocess.run(
        command,
        cwd=config.parent,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="проверка миграции ") as temporary:
        root = Path(temporary)
        config = root / "subagents.local.toml"
        entrypoint = root / "AGENTS.md"
        shutil.copy2(FIXTURE / config.name, config)
        shutil.copy2(FIXTURE / "worker-instructions.md", entrypoint)

        first = run(config, entrypoint)
        assert first.returncode == 0, first.stderr
        data = tomllib.loads(config.read_text(encoding="utf-8"))
        runtime = data["policy_runtime"]
        assert runtime["schema_version"] == 2
        assert runtime["launcher"] == "local-launcher"
        assert runtime["target"] == "local-target"
        assert runtime["direct_execution"] == ["one-file microtask"]
        assert runtime["unavailable_route"] == "keep parent route"
        assert runtime["execution_failure"] == "discard child result"
        assert runtime["unconfirmed_model"] == "parent decides after acceptance"
        assert runtime["result_acceptance"] == "parent checks evidence"
        assert runtime["execution_status"] == "blocked"
        assert runtime["economy_status"] == "not_measured"
        assert runtime["routes"] == [{"when": "bounded read-only facts", "execution_class": "local-readonly"}]

        task = data["policy_design"]["tasks"][0]
        assert task["parent_basis"] == "historical_setup_observation"
        assert task["parent_basis_model"] == "historical assignment"
        assert task["parent_basis_effort"] == "historical effort"
        assert task["parent_basis_evidence"] == "setup observation"
        assert task["parent_basis_observed_at"] == "unknown"
        assert not any(key in task for key in ("parent_model", "parent_effort", "parent_evidence"))

        target = data["targets"]["local"]["execution_classes"]["local_readonly"]
        assert data["execution_classes"]["local_readonly"]["writes"] is False
        assert target == {
            "model": "configured local assignment",
            "effort": "configured local effort",
            "sandbox": "read-only",
            "adapter": ["configured adapter"],
        }

        migrated_entrypoint = entrypoint.read_text(encoding="utf-8")
        assert migrated_entrypoint.count(START) == 1
        assert migrated_entrypoint.count(END) == 1
        canonical = ASSET.read_text(encoding="utf-8")
        assert canonical in migrated_entrypoint
        assert "Keep this surrounding rule unchanged." in migrated_entrypoint
        assert "Keep this rule after the managed fragment unchanged." in migrated_entrypoint

        saved_config = config.read_bytes()
        saved_entrypoint = entrypoint.read_bytes()
        second = run(config, entrypoint)
        assert second.returncode == 0, second.stderr
        assert "уже актуальна" in second.stdout
        assert config.read_bytes() == saved_config
        assert entrypoint.read_bytes() == saved_entrypoint
        assert run(config, entrypoint, check=True).returncode == 0

    print("Миграция политики подагентов проверена на изолированной установке.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

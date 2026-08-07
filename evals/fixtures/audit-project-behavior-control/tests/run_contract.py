from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
fixture = root / ".apm/skills/policy-export/evals/script-fixtures/project"
script = root / ".apm/skills/policy-export/scripts/export.py"
for mode in ("standard", "strict"):
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / "project"
        shutil.copytree(fixture, target)
        command = ["python3", str(script), "--root", str(target)]
        if mode == "strict":
            command.extend(["--mode", "strict"])
        completed = subprocess.run(command, check=False)
        assert completed.returncode == 0
        state = json.loads((target / ".policy/state.json").read_text(encoding="utf-8"))
        assert state["mode"] == mode
print("contract passed")

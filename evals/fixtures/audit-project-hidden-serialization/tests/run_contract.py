from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
fixture = root / ".apm/skills/project-review/evals/script-fixtures/empty-graph"
script = root / ".apm/skills/project-review/scripts/review.py"
with tempfile.TemporaryDirectory() as temporary:
    target = Path(temporary) / "project"
    shutil.copytree(fixture, target)
    completed = subprocess.run(["python3", str(script), "init", "--root", str(target)], check=False)
    assert completed.returncode == 0
    state = json.loads((target / ".review/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "started"
print("contract passed")

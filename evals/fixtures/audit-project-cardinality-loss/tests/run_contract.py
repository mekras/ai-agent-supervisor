from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
fixture = root / ".apm/skills/event-summary/evals/script-fixtures/single"
script = root / ".apm/skills/event-summary/scripts/summarize.py"
with tempfile.TemporaryDirectory() as temporary:
    target = Path(temporary) / "project"
    shutil.copytree(fixture, target)
    completed = subprocess.run(["python3", str(script), "--root", str(target)], check=False)
    assert completed.returncode == 0
    state = json.loads((target / ".events/summary.json").read_text(encoding="utf-8"))
    assert state["event_count"] == 1
print("contract passed")

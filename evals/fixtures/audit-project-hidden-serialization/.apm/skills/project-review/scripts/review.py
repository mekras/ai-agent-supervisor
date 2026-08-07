from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    state: dict[str, object] = {"status": "started"}
    impact = root / "project-impact.json"
    if impact.is_file():
        graph = json.loads(impact.read_text(encoding="utf-8"))
        paths = {
            path
            for node in graph.get("nodes", [])
            for path in node.get("paths", [])
        }
        if paths:
            state["scope"] = {"paths": paths}
    destination = root / ".review" / "state.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    events = json.loads((root / "events.json").read_text(encoding="utf-8"))
    by_id = {event["id"]: event for event in events}
    state = {"event_count": len(by_id), "event_ids": sorted(by_id)}
    destination = root / ".events" / "summary.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

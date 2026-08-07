from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    policy_path = root / "policy.json"
    configured_mode = "standard"
    if policy_path.is_file():
        configured_mode = json.loads(policy_path.read_text(encoding="utf-8")).get("mode", "standard")
    state = {"mode": "standard", "source": "generated"}
    destination = root / ".policy" / "state.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    print(f"configured mode: {configured_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Регрессионные проверки узкого обхода ложного APM drift."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "tools" / "apm-audit-ci"


def write_project(
    root: Path,
    *,
    active_owner: str = ".",
    extra_failure: bool = False,
    phantom_bytecode: bool = False,
    present_bytecode: bool = False,
) -> Path:
    (root / "apm.yml").write_text("name: local-package\n", encoding="utf-8")
    source = root / ".apm" / "skills" / "example" / "SKILL.md"
    deployed = root / ".agents" / "skills" / "example" / "SKILL.md"
    source.parent.mkdir(parents=True)
    deployed.parent.mkdir(parents=True)
    source.write_text("local source\n", encoding="utf-8")
    deployed.write_text("local source\n", encoding="utf-8")
    adapter_source = root / ".apm" / "skills" / "example" / "scripts" / "adapter"
    adapter_deployed = root / ".agents" / "skills" / "example" / "scripts" / "adapter"
    adapter_source.parent.mkdir(parents=True)
    adapter_deployed.parent.mkdir(parents=True)
    adapter_source.write_text("#!/bin/sh\n", encoding="utf-8")
    adapter_deployed.write_text("#!/bin/sh\n", encoding="utf-8")
    lockfile = f"""dependencies:
- repo_url: example/local-package
  name: local-package
deployments:
- value: .agents/skills/example/SKILL.md
  owners: [example/local-package, .]
  active_owner: {active_owner}
- value: .agents/skills/example/scripts/adapter
  owners: [example/local-package, .]
  active_owner: .
"""
    (root / "apm.lock.yaml").write_text(lockfile, encoding="utf-8")
    checks = [
        {"name": "lockfile-exists", "passed": True},
        {"name": "drift", "passed": False},
    ]
    if extra_failure:
        checks.append({"name": "content-integrity", "passed": False})
    drift = [
        {
            "path": ".agents/skills/example/SKILL.md",
            "kind": "modified",
            "package": "example/local-package",
        }
    ]
    if phantom_bytecode:
        bytecode = root / ".agents" / "skills" / "example" / "scripts" / "__pycache__" / "adaptercpython-313.pyc"
        if present_bytecode:
            bytecode.parent.mkdir(parents=True)
            bytecode.write_bytes(b"not phantom")
        drift.append(
            {
                "path": ".agents/skills/example/scripts/__pycache__/adaptercpython-313.pyc",
                "kind": "unintegrated",
                "package": "",
            }
        )
    report = {
        "passed": False,
        "checks": checks,
        "drift": {
            "drift": drift
        },
    }
    fake_apm = root / "fake-apm"
    fake_apm.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'\n"
        f"print({json.dumps(json.dumps(report))})\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    fake_apm.chmod(fake_apm.stat().st_mode | stat.S_IXUSR)
    return fake_apm


def run(root: Path, fake_apm: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT), "--apm", str(fake_apm), "--project-root", str(root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        accepted = run(root, write_project(root))
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "подтверждено файлов — 1" in accepted.stdout

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        accepted = run(root, write_project(root, phantom_bytecode=True))
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "подтверждено файлов — 2" in accepted.stdout

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rejected = run(
            root,
            write_project(root, phantom_bytecode=True, present_bytecode=True),
        )
        assert rejected.returncode == 1, rejected.stdout + rejected.stderr
        assert '"unintegrated"' in rejected.stdout

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rejected = run(root, write_project(root, active_owner="example/local-package"))
        assert rejected.returncode == 1, rejected.stdout + rejected.stderr
        assert '"passed": false' in rejected.stdout

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rejected = run(root, write_project(root, extra_failure=True))
        assert rejected.returncode == 1, rejected.stdout + rejected.stderr
        assert '"content-integrity"' in rejected.stdout

    print("Узкий обход ложного APM drift проверен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

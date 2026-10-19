#!/usr/bin/env python3
"""Проверить трассировку к требованиям без вымышленных ссылок на корпус."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    validator = Path(__file__).with_name('validate-internal-source-basis.py')
    with tempfile.TemporaryDirectory(prefix='requirement-basis-') as directory:
        root = Path(directory)
        (root / 'tools').mkdir()
        shutil.copyfile(validator, root / 'tools' / validator.name)
        skill = root / '.apm/skills/example/evals'
        skill.mkdir(parents=True)
        (skill / 'result-scenarios.json').write_text(json.dumps({
            'skill_name': 'example', 'cases': [{'id': 'example-result-basic'}]}))
        (root / 'docs/requirements').mkdir(parents=True)
        (root / 'docs/requirements/REQ-0001.md').write_text('Согласованный критерий проверки.\n')
        (root / 'evals').mkdir()
        (root / 'evals/basis.yml').write_text('statements:\n  - id: EXAMPLE-001\n')

        def check(requirements, claims, expected, *, source=True):
            basis = {'skills': {'example': {
                'source_basis': [{'claim_id': 'EXAMPLE-001', 'statement_path': 'evals/basis.yml'}] if source else [],
                'cases': [{'id': 'example-result-basic', 'requirement_basis': requirements,
                           'required_claims': claims, 'finding_claims': [claims] if claims else []}]}}}
            (root / 'evals/internal-source-basis.json').write_text(json.dumps(basis))
            run = subprocess.run([sys.executable, '-B', str(root / 'tools' / validator.name)],
                                 cwd=root, capture_output=True, text=True,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            assert run.returncode == expected, (basis, run.returncode, run.stdout, run.stderr)

        check(['docs/requirements/REQ-0001.md'], [], 0, source=False)
        check([], ['EXAMPLE-001'], 0)
        check(['docs/requirements/REQ-0001.md'], ['EXAMPLE-001'], 0)
        check([], [], 1, source=False)
        check(['docs/requirements/missing.md'], [], 1, source=False)
        check(['../outside.md'], [], 1, source=False)
        check(['docs/requirements/REQ-0001.md'], ['UNKNOWN'], 1)
        check(['docs/requirements/REQ-0001.md'], [], 1)
    print('Трассировка проверена: требования, прежние утверждения, ошибки и неиспользуемые связи.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

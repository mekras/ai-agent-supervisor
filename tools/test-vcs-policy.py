#!/usr/bin/env python3
"""Регрессии защиты локальных данных и сред VCS без вызовов моделей."""
from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / '.apm/skills'
POLICY = runpy.run_path(str(SKILLS / 'ai-setup-execution-policy/scripts/execution-policy'))
STORAGE = runpy.run_path(str(SKILLS / 'ai-setup-subagents/scripts/lib/run_storage.py'))
EVALS = runpy.run_path(str(SKILLS / 'ai-setup-apm/scripts/eval-tools/run-skill-evals.py'))


def git(root: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(root), *args], text=True, encoding='utf-8',
                            errors='replace', capture_output=True, check=True)
    return result.stdout


def refused(callback, *args, **kwargs):
    try:
        callback(*args, **kwargs)
    except (ValueError, RuntimeError, POLICY['PolicyError']) as error:
        assert 'Git' in str(error) or 'VCS' in str(error), str(error)
    else:
        raise AssertionError('Неподтверждённая защита должна остановить запись')


def bootstrap(root: Path, config: Path, **settings) -> str:
    output = io.StringIO()
    with patch.dict(os.environ, settings, clear=True), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        EVALS['bootstrap_config'](root, config)
    return output.getvalue()


def finish(directory: Path, run_id: str):
    record = directory / 'run.json'
    record.write_text(json.dumps({'run_id': run_id, 'status': 'completed',
        'storage': {'schema_version': 1, 'retain_reason': ''},
        'result_path': str(directory / 'result.final.txt')}), encoding='utf-8')
    (directory / 'result.final.txt').write_text('Проверенный тестовый результат', encoding='utf-8')
    result = STORAGE['finish_run'](record, run_id, validate=lambda value: None)
    assert result['storage'] == 'removed' and not directory.exists()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='vcs-policy-') as temporary:
        base = Path(temporary).resolve()
        no_vcs = base / 'без VCS'; no_vcs.mkdir()
        sample = no_vcs / 'evals.sample.yml'; sample.write_text('models: []\n', encoding='utf-8')
        config = no_vcs / 'evals.local.yml'
        output = bootstrap(no_vcs, config)
        assert not config.exists() and 'Файлы не созданы' in output
        output = bootstrap(no_vcs, config, APM_EVAL_BOOTSTRAP='git')
        assert not config.exists() and 'Git не обнаружен' in output
        output = bootstrap(no_vcs, config, APM_EVAL_STORAGE_VERIFIED='1')
        assert config.exists() and 'вызывающим агентом' in output
        assert not (no_vcs / '.git').exists()

        with patch('subprocess.run', side_effect=FileNotFoundError('git absent')):
            refused(POLICY['ensure_private_output'], no_vcs / 'private.toml', False, git_storage=True)
            refused(STORAGE['create_run_directory'], no_vcs / 'out', str(uuid.uuid4()), git_storage=True)
            config.unlink()
            output = bootstrap(no_vcs, config, APM_EVAL_BOOTSTRAP='git')
            assert not config.exists() and 'Настройки не созданы' in output
            # Другая VCS и отсутствие VCS обслуживаются после проверки родителем.
            for marker in (None, '.hg'):
                target = no_vcs / ('other' if marker else 'none'); target.mkdir()
                if marker: (target / marker).mkdir()
                POLICY['ensure_private_output'](target / 'private.toml', False, storage_verified=True)
                run_id = str(uuid.uuid4())
                directory = STORAGE['create_run_directory'](target / 'out', run_id, storage_verified=True)
                assert not (directory / '.gitignore').exists()
                finish(directory, run_id)
            packages = EVALS['prepare_trial'](no_vcs / 'trial', [], input_files=[
                {'path': 'note.txt', 'content': 'Вход проекта без VCS'}], vcs='none')
            assert packages == {} and not (no_vcs / 'trial/.git').exists()

        # Свидетельство реального индекса различает политики добавления.
        trial = base / 'Git trial'
        EVALS['prepare_trial'](trial, [], input_files=[{'path': 'note.txt', 'content': 'Прежние изменения'}])
        assert EVALS['git_index_snapshot'](trial) == ''
        git(trial, 'add', 'note.txt')
        assert 'note.txt' in EVALS['git_index_snapshot'](trial)
        assert EVALS['git_index_snapshot'](no_vcs) is None

        repo = base / 'Git проект'; repo.mkdir(); git(repo, 'init', '-q')
        private = repo / 'private.toml'
        refused(POLICY['ensure_private_output'], private, False, git_storage=True)
        exclude = repo / '.git/info/exclude'
        exclude.write_text(exclude.read_text() + '\n/private.toml\n', encoding='utf-8')
        POLICY['ensure_private_output'](private, False, git_storage=True)
        private.write_text('Только тестовые данные', encoding='utf-8')
        git(repo, 'add', '-f', 'private.toml')
        refused(POLICY['ensure_private_output'], private, False, git_storage=True)
        git(repo, 'rm', '--cached', 'private.toml')
        before = git(repo, 'ls-files', '--stage')
        run_id = str(uuid.uuid4())
        directory = STORAGE['create_run_directory'](repo / 'out', run_id, git_storage=True)
        assert (directory / '.gitignore').read_text() == '*\n'
        assert git(repo, 'ls-files', '--stage') == before
        finish(directory, run_id)

        # Git worktree имеет файл .git. Путь исключений определяется самой VCS.
        git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
            'commit', '--allow-empty', '-qm', 'Fixture')
        worktree = base / 'Связанное дерево'
        git(repo, 'worktree', 'add', '-q', '-b', 'fixture-worktree', str(worktree))
        (worktree / 'evals.sample.yml').write_text('models: []\n', encoding='utf-8')
        config = worktree / 'evals.local.yml'
        assert (worktree / '.git').is_file()
        output = bootstrap(worktree, config, APM_EVAL_BOOTSTRAP='git')
        assert config.exists() and 'подтверждено средствами Git' in output, output
        git(worktree, 'check-ignore', '-q', str(config))
        git(worktree, 'check-ignore', '-q', str(worktree / 'eval-results/report.json'))
        with patch.dict(os.environ, {'APM_EVAL_BOOTSTRAP': 'git'}, clear=True):
            EVALS['verify_evaluation_storage'](worktree, config, worktree / 'eval-results')
            other_output = worktree / 'other-results'
            refused(EVALS['verify_evaluation_storage'], worktree, config, other_output)
            assert not other_output.exists()
        with patch.dict(os.environ, {}, clear=True):
            refused(EVALS['verify_evaluation_storage'], no_vcs, no_vcs / 'evals.local.yml', no_vcs / 'reports')
        with patch.dict(os.environ, {'APM_EVAL_STORAGE_VERIFIED': '1'}, clear=True), \
                patch('subprocess.run', side_effect=FileNotFoundError('git absent')):
            EVALS['verify_evaluation_storage'](no_vcs, no_vcs / 'evals.local.yml', no_vcs / 'reports')

        # Уже отслеживаемые файлы нельзя скрыть новым исключением.
        config.unlink()
        config.write_text('models: []\n', encoding='utf-8'); git(worktree, 'add', '-f', str(config))
        config.unlink()
        output = bootstrap(worktree, config, APM_EVAL_BOOTSTRAP='git')
        assert not config.exists() and 'уже отслеживается' in output

    print('Проверены: неизвестная VCS, отсутствие Git, подтверждённое хранение, Git worktree и отслеживаемые приватные пути.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

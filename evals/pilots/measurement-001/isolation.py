#!/usr/bin/env python3
"""Локальный стенд проверки изоляции. Не запускает модели и не принимает команды."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch


PILOT = Path(__file__).resolve().parent
ROOT = PILOT.parents[2]


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def command(workspace: Path) -> list[str]:
    """Явный список доступных файлов. Домашние каталоги не подключаются."""
    require(Path('/usr/bin/bwrap').is_file(), 'Не найден /usr/bin/bwrap, запуск без изоляции запрещён')
    args = ['/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--unshare-pid',
            '--unshare-net', '--disable-userns', '--die-with-parent', '--new-session',
            '--cap-drop', 'ALL', '--clearenv', '--setenv', 'PATH', '/usr/bin',
            '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
            '--ro-bind', '/usr', '/usr']
    for name in ('bin', 'lib', 'lib64'):
        path = Path('/') / name
        if path.is_symlink():
            args += ['--symlink', os.readlink(path), str(path)]
        elif path.is_dir():
            args += ['--ro-bind', str(path), str(path)]
    args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
             '--dir', '/home', '--dir', '/run', '--bind', str(workspace), '/work',
             '--ro-bind', str(PILOT / 'isolation-probe.py'), '/probe.py']
    for mount in ('.agents', '.claude'):
        if (workspace / mount).exists():
            args += ['--ro-bind', str(workspace / mount), '/work/' + mount]
    return args + ['--remount-ro', '/', '--chdir', '/work', '--',
                   '/usr/bin/python3', '-I', '-B', '/probe.py']


def invoke(workspace: Path, request: dict, timeout: float = 15) -> dict:
    process = subprocess.Popen(command(workspace), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env={}, close_fds=True, start_new_session=True)
    try:
        output, error = process.communicate(json.dumps(request), timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise RuntimeError('Истёк срок проверки, группа процессов остановлена') from None
    require(process.returncode == 0, 'Изоляция не прошла проверку: ' + error[-2000:])
    return json.loads(output)


def prepare_workspace(runner: dict, workspace: Path, fixture: Path, skills: list[Path]) -> dict:
    runner['check_input_tree'](fixture)
    require(not any((fixture / mount).exists() for mount in ('.agents', '.claude')),
            'Фикстура содержит посторонние инструкции')
    shutil.copytree(fixture, workspace, ignore=shutil.ignore_patterns('.git'))
    subprocess.run(['/usr/bin/git', 'init', '--quiet', '--template=',
                    '--initial-branch=pilot', str(workspace)], check=True,
                   env={'PATH': '/usr/bin', 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_GLOBAL': '/dev/null'}, capture_output=True, text=True)
    require(not (workspace / '.git/hooks').exists(), 'Git получил посторонние хуки')
    return runner['install_trial_skills'](workspace, skills)


def check_git_background(runner: dict, base: Path) -> None:
    template = base / 'injected-template'
    template.mkdir()
    (template / 'unexpected-file').write_text('synthetic-user-template')
    fixture = base / 'empty-fixture'
    fixture.mkdir()
    # Воспроизводим старый канал на синтетических данных внутри проекта.
    with patch.dict(os.environ, {'PATH': '/usr/bin', 'GIT_CONFIG_NOSYSTEM': '1',
                                 'GIT_CONFIG_GLOBAL': '/dev/null',
                                 'GIT_TEMPLATE_DIR': str(template)}, clear=True):
        old = base / 'old-preparation'
        runner['prepare_trial'](old, [], fixture=fixture)
        require((old / '.git/unexpected-file').is_file(), 'Контрольный канал Git не воспроизведён')
        clean = base / 'clean-preparation'
        prepare_workspace(runner, clean, fixture, [])
        require(not (clean / '.git/unexpected-file').exists(), 'Git унаследовал шаблон')
        require((clean / '.git/HEAD').read_text().strip() == 'ref: refs/heads/pilot',
                'Git унаследовал имя ветки')


def main() -> None:
    require(len(sys.argv) == 1, 'Стенд не принимает команды или параметры модельного запуска')
    sys.dont_write_bytecode = True
    runner = runpy.run_path(str(ROOT / 'tools/run-skill-evals.py'))
    registry = json.loads((PILOT / 'registry.json').read_text())
    minimal = (PILOT / 'minimal-instructions.md').read_text()
    skills = sorted(path.parent for path in (ROOT / '.apm/skills').glob('*/SKILL.md'))
    scratch = ROOT / 'eval-results'
    scratch.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='isolation-', dir=scratch) as temporary:
        base = Path(temporary)
        check_git_background(runner, base)
        canary = base / 'outside-secret.txt'
        canary.write_text('Синтетический контрольный файл вне рабочей копии')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            for case in registry['cases']:
                case = {**case, 'fixture_dir': PILOT / case['fixture']}
                for condition in ('ordinary', 'minimal', 'collection'):
                    workspace = base / (case['id'] + '-' + condition)
                    packages = prepare_workspace(runner, workspace, PILOT / case['fixture'],
                                                 skills if condition == 'collection' else [])
                    prompt = runner['comparison_candidate_prompt'](case, condition, minimal)
                    (workspace / 'pilot-prompt.txt').write_text(prompt)
                    before = {p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in workspace.rglob('*') if p.is_file()}
                    request = {'hidden': [str(ROOT / 'AGENTS.md'), str(PILOT / case['oracle']),
                                          str(canary), str(Path.home() / '.codex/config.toml'),
                                          str(Path.home() / '.claude/settings.json')],
                               'host_pid': os.getpid(), 'host_net': os.readlink('/proc/self/ns/net'),
                               'host_port': listener.getsockname()[1],
                               'expected_files': before, 'collection': condition == 'collection'}
                    result = invoke(workspace, request)
                    require((workspace / 'probe-result.txt').read_text() == 'written', 'Запись результата не сохранена')
                    require(not (workspace / 'escape-link').exists(), 'Осталась ссылка проверки')
                    for name, digest in before.items():
                        require(hashlib.sha256((workspace / name).read_bytes()).hexdigest() == digest,
                                'Проверка изменила вход: ' + name)
                    require(runner['trial_skill_manifest'](workspace) == packages, 'Изменился состав навыков')
                    results.append({'case': case['id'], 'condition': condition, **result})
            # Повторный запуск не получает предыдущий /tmp.
            invoke(workspace, request)
            require(canary.read_text() == 'Синтетический контрольный файл вне рабочей копии', 'Изменён внешний файл')
            try:
                invoke(workspace, {**request, 'sleep': True}, timeout=0.2)
            except RuntimeError as error:
                require('Истёк срок' in str(error), str(error))
            else:
                raise RuntimeError('Не сработала остановка по времени')
    print(json.dumps({'status': 'offline_isolation_checked', 'model_calls': 0,
                      'trials': results, 'timeout_checked': True, 'git_background_checked': True,
                      'runtime': subprocess.check_output(['/usr/bin/bwrap', '--version'], text=True).strip(),
                      'live_adapter_connected': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Детерминированная проба внутри стенда, без обращения к моделям."""

import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


data = json.load(sys.stdin)
if data.get('sleep'):
    time.sleep(60)
require(set(os.environ) <= {'PATH', 'LANG', 'PYTHONDONTWRITEBYTECODE', 'PWD', 'LC_CTYPE'},
        'Унаследованы посторонние переменные среды')
require(not list(Path('/home').iterdir()), 'Домашняя папка не пуста')
require(not list(Path('/run').iterdir()), 'Доступны сокеты внешней среды')
require(not Path('/tmp/previous-attempt').exists(), 'Состояние /tmp перешло между попытками')
Path('/tmp/previous-attempt').write_text('private')
for name in data['hidden']:
    try:
        Path(name).read_bytes()
    except (FileNotFoundError, PermissionError):
        pass
    else:
        raise RuntimeError('Доступен внешний файл: ' + name)
link = Path('/work/escape-link')
link.symlink_to(data['hidden'][2])
require(not link.exists(), 'Ссылка открыла внешний файл')
link.unlink()
require(os.readlink('/proc/self/ns/net') != data['host_net'], 'Сеть не изолирована')
with socket.socket() as connection:
    connection.settimeout(0.5)
    require(connection.connect_ex(('127.0.0.1', data['host_port'])) != 0, 'Доступен порт внешней среды')
require(not Path('/proc/' + str(data['host_pid']) + '/root' + data['hidden'][2]).exists(),
        'Доступен корень внешнего процесса')
for name, digest in data['expected_files'].items():
    require(hashlib.sha256((Path('/work') / name).read_bytes()).hexdigest() == digest,
            'Изменён или недоступен вход: ' + name)
for mount in ('.agents', '.claude'):
    path = Path('/work') / mount
    require(path.exists() == data['collection'], 'Неверное условие навыков')
    if path.exists():
        try:
            (path / 'probe-mutation').write_text('forbidden')
        except OSError:
            pass
        else:
            raise RuntimeError('Пакеты навыков доступны для изменения')
Path('/work/probe-result.txt').write_text('written')
print(json.dumps({'filesystem_checked': True, 'network_checked': True,
                  'environment_checked': True, 'input_files_checked': len(data['expected_files'])}))

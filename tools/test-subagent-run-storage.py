#!/usr/bin/env python3
"""Проверки полного цикла временных данных без запуска модели."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".apm/skills/ai-setup-subagents/scripts"
RUNNER = SCRIPTS / "run-execution-class"
ROLE = SCRIPTS / "run-subagent-role"


def invoke(script: Path, *args: str, cwd: Path, expected: int = 0, task: str = ""):
    completed = subprocess.run(
        [sys.executable, "-B", str(script), *map(str, args)], cwd=cwd,
        input=task, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == expected, (completed.stdout, completed.stderr)
    return completed


def fixture(root: Path) -> Path:
    adapter = root / "adapter.py"
    adapter.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\nfrom pathlib import Path\n"
        "json.loads(sys.stdin.read())\n"
        "Path(os.environ['CODEX_ROLE_LOG']).write_text(json.dumps({'model':'fixture-model','effort':'low'})+'\\n')\n"
        "print(json.dumps({'model':'fixture-model','effort':'low','turn_completed':True,"
        "'model_evidence':{'source':'journal','line':1,'field':['model']},"
        "'effort_evidence':{'source':'journal','line':1,'field':['effort']}}))\n"
        "print('Ответ для родительской проверки')\n",
        encoding="utf-8",
    )
    adapter.chmod(0o755)
    config = root / "policy.toml"
    config.write_text(
        "[execution_classes.review]\nwrites = false\n"
        "[targets.fixture.execution_classes.review]\n"
        "model = 'fixture-model'\neffort = 'low'\nsandbox = 'read-only'\n"
        f"adapter = [{json.dumps(str(adapter))}]\n"
        "[roles.review]\nmodel = 'fixture-model'\neffort = 'low'\nsandbox = 'read-only'\n"
        f"adapter = {json.dumps(str(adapter))}\n",
        encoding="utf-8",
    )
    return config


def launch(root: Path, config: Path, *, script=RUNNER, extra=(), expected=0) -> dict:
    args = ["review", "--git-storage", "--config", str(config)]
    if script == RUNNER:
        args += ["--target", "fixture"]
    completed = invoke(script, *args, *extra, cwd=root, expected=expected, task="Проверь ответ.")
    return json.loads(completed.stdout if expected == 0 else completed.stderr)


def accept(root: Path, record: dict, *, script=RUNNER, rejected=False):
    invoke(script, "--record-acceptance", record["record_path"], "--run-id", record["run_id"],
           "--status", "rejected" if rejected else "accepted",
           "--criterion", "Ответ проверен", "--evidence", "Проверка управляемого исполнителя",
           "--quality", "failed" if rejected else "passed", "--summary", "Проверка завершена",
           "--scope", "Полный ответ", cwd=root)
    invoke(script, "--check-acceptance", record["record_path"], "--run-id", record["run_id"],
           cwd=root, expected=1 if rejected else 0)


def finish(root: Path, record: dict, *, script=RUNNER, extra=(), expected=0):
    return invoke(script, "--finish-task", record["record_path"], "--run-id", record["run_id"],
                  *extra, cwd=root, expected=expected)


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = fixture(root)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        roles = root / ".codex/agents"
        roles.mkdir(parents=True)
        product_role = roles / "review.toml"
        product_role.write_text("Продуктовая роль")
        old = root / ".codex/subagents/old.json"
        old.parent.mkdir()
        old.write_text("Прежний журнал")
        subprocess.run(["git", "add", ".codex"], cwd=root, check=True)
        index_before = subprocess.check_output(["git", "ls-files", "-s"], cwd=root)

        # Основной цикл для обоих запускателей, без поля каталога в политике.
        for script in (RUNNER, ROLE):
            record = launch(root, config, script=script)
            path = Path(record["record_path"])
            assert path.parent.parent == root / ".local/subagents"
            assert Path(record["result_path"]).read_text().strip() == "Ответ для родительской проверки"
            assert record["client_route_status"] == "confirmed"
            subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=root, check=True)
            # Незавершённая приёмка сохраняет данные для проверки.
            finish(root, record, script=script, expected=2)
            assert path.exists()
            accept(root, record, script=script)
            assert path.exists() and Path(record["result_path"]).exists()
            finished = finish(root, record, script=script)
            assert json.loads(finished.stdout)["storage"] == "removed"
            assert not path.parent.exists()
        assert subprocess.check_output(["git", "ls-files", "-s"], cwd=root) == index_before
        assert old.read_text() == "Прежний журнал"
        assert product_role.read_text() == "Продуктовая роль"

        # Другая VCS и отсутствие VCS: неподтверждённое место блокирует запуск,
        # после проверки родителя доступны тот же результат, приёмка и очистка.
        with tempfile.TemporaryDirectory() as outside:
            no_git = Path(outside)
            no_git_config = fixture(no_git)
            for marker in (None, ".hg"):
                if marker:
                    (no_git / marker).mkdir()
                for script in (RUNNER, ROLE):
                    arguments = ["review", "--config", str(no_git_config)]
                    if script == RUNNER:
                        arguments += ["--target", "fixture"]
                    stopped = invoke(script, *arguments, cwd=no_git, expected=2,
                                     task="Не запускай без проверки места.")
                    assert "VCS не проверена" in stopped.stderr
                    assert not list((no_git / ".local/subagents").glob("*/run.json"))
                    record = launch(no_git, no_git_config, script=script,
                                    extra=("--storage-verified",))
                    path = Path(record["record_path"])
                    assert not (path.parent / ".gitignore").exists()
                    accept(no_git, record, script=script)
                    finish(no_git, record, script=script)
                    assert not path.parent.exists()

        # Явный путь и путь из политики также защищены от обычного git add.
        config.write_text(config.read_text() + "\n[policy_runtime]\nrun_records_dir = 'configured'\n")
        for script in (RUNNER, ROLE):
            configured = launch(root, config, script=script)
            assert Path(configured["record_path"]).parent.parent == root / "configured"
            explicit = launch(root, config, script=script, extra=("--out", ".codex/subagents"))
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            tracked = subprocess.check_output(["git", "ls-files"], cwd=root, text=True)
            assert configured["run_id"] not in tracked and explicit["run_id"] not in tracked
            accept(root, configured, script=script)
            accept(root, explicit, script=script)
            finish(root, configured, script=script)
            finish(root, explicit, script=script)
            assert old.exists()

        # Хранение по запросу и последующее завершение согласованного разбора.
        retained = launch(root, config, extra=("--retain-for", "Запрошенный разбор ошибки"))
        accept(root, retained)
        assert json.loads(finish(root, retained).stdout)["storage"] == "retained"
        assert Path(retained["result_path"]).exists()
        finish(root, retained, extra=("--release-retained",))
        assert not Path(retained["record_path"]).parent.exists()

        # Отказ в приёмке и неуспешный запуск тоже удаляются при завершении задачи.
        rejected = launch(root, config)
        accept(root, rejected, rejected=True)
        finish(root, rejected)
        adapter = root / "adapter.py"
        adapter.write_text(adapter.read_text() + "raise SystemExit(1)\n")
        for script in (RUNNER, ROLE):
            failed = launch(root, config, script=script, expected=2 if script == RUNNER else 1)
            assert failed["status"] == "failed"
            finish(root, failed, script=script)
        config.write_text(config.read_text().replace(str(adapter), str(root / "missing-adapter")))
        for script in (RUNNER, ROLE):
            failed = launch(root, config, script=script, expected=2)
            assert failed["stop_reason"] == "launch_error"
            finish(root, failed, script=script)

        # Ошибочный, активный или подменённый каталог никогда не очищается.
        invoke(RUNNER, "--finish-task", str(old), "--run-id", "old-run", cwd=root, expected=2)
        assert old.exists()
        config = fixture(root)
        for script in (RUNNER, ROLE):
            args = ["review", "--config", str(config), "--retain-for", " "]
            if script == RUNNER:
                args += ["--target", "fixture"]
            invoke(script, *args, cwd=root, expected=2, task="Не запускай модель.")
        adapter = root / "adapter.py"
        adapter.write_text(adapter.read_text() + "import time; time.sleep(2)\n")
        timed_out = launch(root, config, extra=("--timeout-seconds", "0.1"), expected=2)
        assert timed_out["status"] == "timed_out"
        finish(root, timed_out)
        config = fixture(root)
        protected = launch(root, config)
        path = Path(protected["record_path"])
        original = path.read_bytes()
        path.write_text(original.decode().replace('"status": "completed"', '"status": "started"'))
        finish(root, protected, expected=2)
        path.write_bytes(original)
        accept(root, protected)
        outside = root / "do-not-delete.txt"
        outside.write_text("Чужие данные")
        intruder = path.parent / "unexpected.txt"
        intruder.write_text("Посторонний файл")
        finish(root, protected, expected=2)
        assert intruder.exists() and path.exists()
        intruder.unlink()
        result = Path(protected["result_path"])
        result_content = result.read_bytes()
        result.unlink()
        result.symlink_to(outside)
        finish(root, protected, expected=2)
        assert outside.read_text() == "Чужие данные"
        result.unlink()
        result.write_bytes(result_content)
        lock = path.with_name(path.name + ".acceptance.lock")
        lock.write_text("Другая операция")
        finish(root, protected, expected=2)
        assert lock.read_text() == "Другая операция"
        lock.unlink()
        accepted_record = path.read_bytes()
        altered = json.loads(accepted_record)
        altered["result_path"] = str(outside)
        path.write_text(json.dumps(altered))
        finish(root, protected, expected=2)
        assert outside.read_text() == "Чужие данные" and path.exists()
        path.write_bytes(accepted_record)
        # Символьная ссылка на весь каталог также не разрешает очистку.
        link = root / protected["run_id"]
        link.symlink_to(path.parent, target_is_directory=True)
        linked = {**protected, "record_path": str(link / "run.json")}
        finish(root, linked, expected=2)
        assert path.exists()
        link.unlink()
        # Подмена run_id и сведений о завершении процесса не разрешает удаление.
        wrong = {**protected, "run_id": "00000000-0000-0000-0000-000000000000"}
        finish(root, wrong, expected=2)
        finish(root, protected)
        assert not path.parent.exists() and old.exists() and outside.exists()
    print("Временное хранение, приёмка, исключение Git и безопасная очистка проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

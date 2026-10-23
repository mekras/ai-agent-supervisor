#!/usr/bin/env python3
"""Выполнить механическую очередь корпуса без смысловых решений."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parent.parent
NEGATIVE = {"rejected", "irrelevant", "excluded", "not_selected"}
MEDIA = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm", ".flac"}


class QueueError(RuntimeError):
    """Операция не может завершиться без потери проверяемости."""


def inside(root: Path, raw: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise QueueError("Путь должен оставаться внутри разрешённой папки.")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise QueueError("Символические ссылки в путях корпуса не поддерживаются.")
    return path


def load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueueError("В файле YAML нужен объект.")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(path: Path, data: bytes, expected: bytes | None = None, *, absent: bool = False) -> None:
    if path.is_symlink():
        raise QueueError("Запись через символическую ссылку запрещена.")
    if expected is not None and path.read_bytes() != expected:
        raise QueueError("Файл изменён другим исполнителем. Повторите проверку.")
    if absent and path.exists():
        raise QueueError("Файл уже создан другим исполнителем. Перезапись запрещена.")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix="queue.tmp.", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            if expected is not None:
                os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if expected is not None and path.read_bytes() != expected:
            raise QueueError("Файл изменён другим исполнителем. Повторите проверку.")
        if absent and path.exists():
            raise QueueError("Файл уже создан другим исполнителем. Перезапись запрещена.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def encoded(value: dict) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


@contextmanager
def locked(corpus: Path):
    path = inside(corpus, "queues.local.lock")
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise QueueError("Другой исполнитель уже обрабатывает этот корпус.") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def rejected(record: dict) -> bool:
    return record.get("rejected") is True or any(
        isinstance(record.get(key), str) and record[key].lower() in NEGATIVE
        for key in ("status", "selection", "selection_status", "selection_result", "relevance")
    )


def units(corpus: Path):
    seen_ids, seen_paths, seen_sources = set(), set(), set()
    for source_path in sorted(inside(corpus, "data").glob("*/source.yml")):
        source_path = inside(corpus, str(source_path.relative_to(corpus)))
        source = load(source_path)
        if not isinstance(source.get("id"), str) or not source["id"] or source["id"] in seen_sources:
            raise QueueError("Идентификаторы источников должны быть непустыми и уникальными.")
        seen_sources.add(source["id"])
        index = load(inside(source_path.parent, "items.yml"))
        entries = index.get("items")
        if not isinstance(entries, list):
            raise QueueError("В индексе источника нужен список items.")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise QueueError("В записи индекса нужен относительный путь единицы.")
            directory = inside(source_path.parent, entry["path"])
            card_path = inside(directory, "item.yml")
            original = card_path.read_bytes() if card_path.exists() else None
            card = load(card_path) if original is not None else {}
            merged = {**entry, **card}
            identifier = merged.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen_ids or directory in seen_paths:
                raise QueueError("Идентификаторы и пути единиц должны быть уникальными.")
            if merged.get("source_id") != source.get("id"):
                raise QueueError("Единица ссылается на другой источник.")
            seen_ids.add(identifier)
            seen_paths.add(directory)
            if not rejected(source) and not rejected(merged):
                yield source, merged, card_path, original


def update_card(card_path: Path, original: bytes | None, unit: dict, stage: str, names: list[str]) -> None:
    value = yaml.safe_load(original) if original is not None else dict(unit)
    files = value.setdefault("files", {})
    if not isinstance(files, dict) or not isinstance(files.get("local", []), list):
        raise QueueError("Поле files.local должно быть списком.")
    files["local"] = list(dict.fromkeys([*files.get("local", []), *names]))
    value["workflow_stage"] = stage
    write(card_path, encoded(value), original, absent=original is None)


def public_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise QueueError("Нужен публичный URL HTTP(S) без учётных данных.")
    keys = {key.lower() for key, _ in urllib.parse.parse_qsl(parsed.query)}
    if keys & {"token", "access_token", "api_key", "apikey", "password", "secret", "signature", "sig", "key"}:
        raise QueueError("URL с секретными параметрами не поддерживается.")
    return url


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        public_url(newurl)
        if urllib.parse.urlsplit(request.full_url).scheme == "https" and urllib.parse.urlsplit(newurl).scheme != "https":
            raise QueueError("Переход с HTTPS на HTTP запрещён.")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url: str, maximum: int) -> tuple[bytes, str]:
    # Источник задаёт адрес. Cookies, браузерная сессия и секреты не передаются.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicRedirect())
    request = urllib.request.Request(public_url(url), headers={"User-Agent": "ai-agent-supervisor-corpus/1"})
    try:
        with opener.open(request, timeout=30) as response:
            data = response.read(maximum + 1)
            media_type = response.headers.get_content_type()
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise QueueError("Материал не получен. Стадия сохранена, доступ можно проверить повторно.") from exc
    if not data or len(data) > maximum:
        raise QueueError("Получен пустой материал или превышен допустимый размер.")
    return data, media_type


def fetch(source: dict, unit: dict, card: Path, original: bytes | None, args) -> None:
    if source.get("copy_policy") not in {"local_only", "full", "full_copy"}:
        raise QueueError("Политика источника не разрешает этот способ локального получения.")
    url = unit.get("locator") or unit.get("url")
    if not isinstance(url, str):
        raise QueueError("В выбранной единице отсутствует собственный URL.")
    public_url(url)
    receipt_path = inside(card.parent, "acquisition.local.yml")
    if receipt_path.exists():
        receipt = load(receipt_path)
        blob = inside(card.parent, receipt["artifact"])
        if receipt.get("locator") != url or file_digest(blob) != receipt.get("sha256"):
            raise QueueError("Существующий снимок не совпадает с паспортом. Перезапись запрещена.")
    else:
        data, media_type = download(url, args.max_bytes)
        suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
        if suffix not in MEDIA | {".html", ".txt", ".md", ".pdf", ".xml", ".json"}:
            suffix = ".bin"
        if media_type == "text/html":
            suffix = ".html"
        blob = inside(card.parent, f"snapshot-{digest(data)}.local{suffix}")
        if blob.exists():
            if blob.read_bytes() != data:
                raise QueueError("Снимок с тем же именем имеет другое содержимое.")
        else:
            write(blob, data, absent=True)
        receipt = {"locator": url, "artifact": blob.name, "sha256": digest(data),
                   "size": len(data), "media_type": media_type, "retrieved_at": stamp()}
        write(receipt_path, encoded(receipt), absent=True)
    media = receipt["media_type"].startswith(("audio/", "video/")) or blob.suffix in MEDIA
    update_card(card, original, unit, "needs_transcript" if media else "fetched", [blob.name, receipt_path.name])


def resources(directory: Path, media: Path, model: Path) -> None:
    if shutil.disk_usage(directory).free < max(2 * 1024**3, media.stat().st_size * 2):
        raise QueueError("Недостаточно свободного места для расшифровки.")
    available = None
    memory = Path("/proc/meminfo")
    if memory.is_file():
        for line in memory.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
    if available is None or available < max(8 * 1024**3, model.stat().st_size * 3):
        raise QueueError("Недостаточно доступной памяти для выбранной модели либо её объём не определён.")


def transcribe(source: dict, unit: dict, card: Path, original: bytes | None, args) -> None:
    if source.get("copy_policy") not in {"local_only", "full", "full_copy"}:
        raise QueueError("Политика источника не разрешает сохранение полной сырой расшифровки.")
    receipt_path = inside(card.parent, "transcription.local.yml")
    transcript = inside(card.parent, "transcript.local.txt")
    media_name = unit.get("input_media")
    acquisition = inside(card.parent, "acquisition.local.yml")
    if not media_name and acquisition.exists():
        media_name = load(acquisition).get("artifact")
    if not isinstance(media_name, str):
        raise QueueError("В карточке нужно имя локального медиа input_media или паспорт получения.")
    media = inside(card.parent, media_name)
    if not media.is_file() or not media.stat().st_size:
        raise QueueError("Локальное медиа отсутствует или пусто.")
    media_hash = file_digest(media)
    if transcript.exists():
        if not receipt_path.exists():
            raise QueueError("Существующая расшифровка не имеет паспорта. Перезапись запрещена.")
        receipt = load(receipt_path)
        if (receipt.get("input_sha256") != media_hash or
                receipt.get("transcript_sha256") != digest(transcript.read_bytes()) or
                not transcript.read_text(encoding="utf-8").strip()):
            raise QueueError("Расшифровка не совпадает с паспортом. Перезапись запрещена.")
    else:
        receipt_before = receipt_path.read_bytes() if receipt_path.exists() else None
        engine = shutil.which(args.whisper_program)
        model = args.whisper_model.expanduser().resolve()
        if not engine or not shutil.which("ffmpeg") or not model.is_file():
            raise QueueError("Нужны Whisper, ffmpeg и локальный файл модели. Загрузка модели автоматически не выполняется.")
        resources(card.parent, media, model)
        with tempfile.TemporaryDirectory(prefix="whisper.tmp.", dir=card.parent) as temporary:
            command = [engine, str(media), "--model", str(model), "--device", "cpu", "--threads", "2",
                       "--fp16", "False", "--output_format", "txt", "--output_dir", temporary]
            if shutil.which("ionice"):
                command = ["ionice", "-c3", *command]
            if shutil.which("nice"):
                command = ["nice", "-n19", *command]
            environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "2",
                           "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
            result = subprocess.run(command, env=environment, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=43200, check=False)
            output = Path(temporary) / (media.stem + ".txt")
            if result.returncode or not output.is_file() or not output.read_text(encoding="utf-8").strip():
                raise QueueError("Движок не создал непустую расшифровку. Стадия сохранена.")
            data = output.read_bytes()
            receipt = {"engine": "whisper", "program": Path(engine).name,
                       "model": model.name, "model_sha256": file_digest(model),
                       "input_media": media_name, "input_sha256": media_hash, "transcript": transcript.name,
                       "transcript_sha256": digest(data), "created_at": stamp(), "threads": 2,
                       "limitations": ["Сырая расшифровка, нужна редактура. Диаризация не выполнялась."]}
            # Паспорт готов до появления результата. Прерывание допускает повтор.
            write(receipt_path, encoded(receipt), receipt_before, absent=receipt_before is None)
            write(transcript, data, absent=True)
    update_card(card, original, unit, "raw_transcribed", [transcript.name, receipt_path.name])


def traceability(source: dict, unit: dict, card: Path, original: bytes | None, args) -> int:
    path = inside(card.parent, "statements.yml")
    before = path.read_bytes()
    document = load(path)
    if document.get("statement_contract_version", 1) != 2:
        return 0
    statements = document.get("statements")
    if not isinstance(statements, list):
        raise QueueError("В файле утверждений нужен список statements.")
    checked, checked_processing = [], []
    for statement in statements:
        processing = statement.get("processing_status")
        if isinstance(processing, dict) and "blocked" in processing.values():
            continue
        if isinstance(processing, dict) and processing.get("extraction") == "complete" and processing.get("traceability") == "passed":
            continue
        if not isinstance(processing, dict) or processing.get("extraction") != "complete":
            raise QueueError("Сначала агент должен завершить извлечение. Проверка связей не присваивает extraction=complete.")
        if statement.get("source_id") != source["id"] or statement.get("item_id") != unit["id"]:
            raise QueueError("Утверждение ссылается на другую единицу или источник.")
        excerpt, artifact = statement.get("excerpt"), statement.get("artifact")
        if not isinstance(excerpt, str) or not excerpt.strip() or not isinstance(artifact, str):
            raise QueueError("У утверждения отсутствует цитата или путь к материалу.")
        artifact_path = inside(card.parent, artifact)
        data = artifact_path.read_bytes()
        if " ".join(excerpt.split()) not in " ".join(data.decode("utf-8").split()):
            raise QueueError("Цитата не найдена непрерывно в указанном материале.")
        checked.append({"id": statement["id"], "artifact": artifact, "sha256": digest(data)})
        checked_processing.append(processing)
    if checked:
        for processing in checked_processing:
            processing["traceability"] = "passed"
        write(inside(card.parent, "traceability.local.yml"), encoded({"checked_at": stamp(), "statements": checked}))
        write(path, encoded(document), before)
    return len(checked)


def pending(operation: str, unit: dict, directory: Path) -> bool:
    stage = unit.get("workflow_stage")
    if stage in {"blocked", "rejected"}:
        return False
    if operation == "fetch":
        return stage == "needs_fetch" or (stage == "indexed" and unit.get("processing_scope") in {"selected_fragments", "full", "full_redacted"})
    if operation == "transcribe":
        return stage == "needs_transcript" and not any(
            inside(directory, name).exists() for name in ("statements.yml", "normalized.md", "message.md", "stenogram.txt", "transcript.txt")
        )
    statements = inside(directory, "statements.yml")
    if not statements.is_file():
        return False
    document = load(statements)
    if document.get("statement_contract_version", 1) != 2:
        return False
    return any(
        not isinstance(s.get("processing_status"), dict) or (
            "blocked" not in s["processing_status"].values() and (
                s["processing_status"].get("extraction") != "complete" or
                s["processing_status"].get("traceability") != "passed"
            )
        ) for s in document.get("statements", [])
    )


def admission(corpus: Path) -> None:
    if "source_admission" not in load(corpus / "corpus.yml"):
        return
    validator = ROOT / ".agents/skills/kc-inventory/scripts/validate-corpus-layout.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(corpus), "--admission-only", "--project-root", str(ROOT), "--output", "json"],
        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, check=False,
    )
    if result.returncode:
        raise QueueError("Допуск источников не прошёл проверку. Очередь не запущена.")


def unique_statements(candidates: list) -> None:
    seen = set()
    for _, _, card, _ in candidates:
        path = inside(card.parent, "statements.yml")
        if not path.exists():
            continue
        for statement in load(path).get("statements", []):
            if not isinstance(statement, dict):
                raise QueueError("Утверждение должно быть объектом.")
            identifier = statement.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise QueueError("Идентификаторы утверждений должны быть непустыми и уникальными.")
            seen.add(identifier)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["fetch", "transcribe", "traceability"])
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--item", help="Обработать только указанную выбранную единицу.")
    parser.add_argument("--limit", type=int, default=1, help="Максимум изменяемых единиц за запуск, по умолчанию 1.")
    parser.add_argument("--max-bytes", type=int, default=64 * 1024**2, help="Предел размера одного получаемого материала.")
    parser.add_argument("--whisper-model", type=Path, default=Path.home() / ".cache/whisper/large-v3.pt", help="Локальный файл модели Whisper. Автоматическая загрузка отключена.")
    parser.add_argument("--whisper-program", default="whisper", help="Команда установленного Whisper.")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.max_bytes < 1:
        parser.error("Пределы должны быть положительными.")
    corpus = inside(ROOT, str(args.corpus))
    load(inside(corpus, "corpus.yml"))
    admission(corpus)
    results, changed, attempted = [], 0, 0
    with locked(corpus):
        candidates = list(units(corpus))
        if args.item and not any(unit["id"] == args.item for _, unit, _, _ in candidates):
            raise QueueError("Выбранная единица не найдена или исключена из обработки.")
        if args.operation == "traceability":
            unique_statements(candidates)
        for source, unit, card, original in candidates:
            if (args.item and unit["id"] != args.item) or not pending(args.operation, unit, card.parent):
                continue
            if attempted >= args.limit:
                break
            attempted += 1
            try:
                card.parent.mkdir(parents=True, exist_ok=True)
                if args.operation == "traceability":
                    count = traceability(source, unit, card, original, args)
                    if not count:
                        continue
                else:
                    {"fetch": fetch, "transcribe": transcribe}[args.operation](source, unit, card, original, args)
                changed += 1
                results.append({"id": unit["id"], "status": "completed"})
            except (QueueError, OSError, ValueError, KeyError, TypeError, yaml.YAMLError, subprocess.TimeoutExpired) as exc:
                message = str(exc) if isinstance(exc, QueueError) else "Операция не завершена. Проверьте входные файлы и ресурсы."
                results.append({"id": unit["id"], "status": "failed", "message": message})
    print(json.dumps({"operation": args.operation, "changed": changed, "results": results}, ensure_ascii=False))
    return 2 if any(result["status"] == "failed" for result in results) else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main())
    except (QueueError, OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        print(str(exc) if isinstance(exc, QueueError) else "Не удалось прочитать корпус. Проверьте файлы и права доступа.", file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
"""Подготовить изолированный CODEX_HOME для внутреннего стенда."""

from __future__ import annotations

import argparse
import errno
import os
import re
import stat
import sys
from pathlib import Path


AUTH_FILENAME = "auth.json"
CONFIG_FILENAME = "config.toml"
CODEX_STORE_CONFIG = 'cli_auth_credentials_store = "file"\n'
OTEL_SECTION = "otel"
SECTION_PATTERN = re.compile(r"^\s*(\[\[?)([^\]]+)(\]\]?)\s*(?:#.*)?$")


def paths_overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def regular_file_bytes(path: Path, label: str) -> bytes:
    try:
        path_type = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValueError(f"Не найден {label}: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Не удалось проверить {label}") from exc
    if stat.S_ISLNK(path_type) or not stat.S_ISREG(path_type):
        raise ValueError(f"{label} должен быть обычным файлом: {path}")
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"{label} должен быть обычным файлом: {path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            return stream.read()
    except FileNotFoundError as exc:
        raise ValueError(f"Не найден {label}: {path}") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(f"{label} должен быть обычным файлом: {path}") from exc
        raise ValueError(f"Не удалось прочитать {label}: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def section_name(line: str) -> str | None:
    match = SECTION_PATTERN.match(line)
    if match is None:
        return None
    opening, name, closing = match.groups()
    if (opening == "[" and closing != "]") or (
        opening == "[[" and closing != "]]"
    ):
        return None
    return name.strip()


def extract_otel(config: bytes) -> bytes:
    try:
        text = config.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("config.toml не имеет UTF-8-кодировку") from exc

    selected: list[str] = []
    in_otel = False
    found_otel = False
    for line in text.splitlines(keepends=True):
        name = section_name(line)
        if name is not None:
            in_otel = name == OTEL_SECTION or name.startswith(f"{OTEL_SECTION}.")
            if in_otel:
                if name == OTEL_SECTION and line.lstrip().startswith("[["):
                    raise ValueError("Раздел otel не должен быть массивом таблиц")
                found_otel = True
                selected.append(line)
            continue
        if in_otel:
            selected.append(line)

    if not found_otel:
        raise ValueError("В config.toml отсутствует раздел otel")
    result_text = CODEX_STORE_CONFIG + "\n" + "".join(selected)
    required_keys = {
        "environment": r"\benvironment\s*=",
        "metrics_exporter": r"\bmetrics_exporter\s*=",
        "endpoint": r"\bendpoint\s*=",
        "protocol": r"\bprotocol\s*=",
        "headers": r"\bheaders\s*=",
    }
    missing = sorted(key for key, pattern in required_keys.items() if not re.search(pattern, result_text))
    if missing:
        raise ValueError("В разделе otel отсутствуют обязательные параметры")
    return result_text.encode("utf-8")


def create_new_file(path: Path, content: bytes) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
        os.chmod(path, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"Отказ: файл уже существует: {path.name}") from exc
    except OSError as exc:
        raise ValueError(f"Не удалось создать файл {path.name}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def prepare(source: Path, destination: Path) -> None:
    source = Path(os.path.abspath(source))
    destination = Path(os.path.abspath(destination))
    try:
        source_type = source.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValueError(f"Исходный CODEX_HOME не найден: {source}") from exc
    if stat.S_ISLNK(source_type) or not stat.S_ISDIR(source_type):
        raise ValueError("Исходный CODEX_HOME должен быть каталогом без ссылки")
    if paths_overlap(source.resolve(), destination.resolve(strict=False)):
        raise ValueError("Исходный и целевой CODEX_HOME не должны пересекаться")

    auth = regular_file_bytes(source / AUTH_FILENAME, AUTH_FILENAME)
    otel_config = extract_otel(regular_file_bytes(source / CONFIG_FILENAME, CONFIG_FILENAME))

    if os.path.lexists(destination):
        destination_type = destination.lstat().st_mode
        if stat.S_ISLNK(destination_type):
            raise ValueError("Целевой CODEX_HOME не должен быть символической ссылкой")
        if not stat.S_ISDIR(destination_type):
            raise ValueError("Целевой CODEX_HOME уже существует и не является каталогом")
        existing_targets = [
            name for name in (AUTH_FILENAME, CONFIG_FILENAME) if (destination / name).exists()
        ]
        if existing_targets:
            raise ValueError("Отказ: целевые файлы уже существуют")
    else:
        destination.mkdir(mode=0o700)
    os.chmod(destination, 0o700)

    try:
        create_new_file(destination / AUTH_FILENAME, auth)
        create_new_file(destination / CONFIG_FILENAME, otel_config)
    except Exception:
        for path in (destination / AUTH_FILENAME, destination / CONFIG_FILENAME):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        prepare(args.source, args.destination)
    except (OSError, ValueError) as exc:
        print(f"CODEX_HOME не подготовлен: {exc}", file=sys.stderr)
        return 2
    print(f"Подготовлен отдельный CODEX_HOME: {args.destination.resolve()}")
    print("Перенесены только auth.json и раздел otel; секретные значения не выводятся.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

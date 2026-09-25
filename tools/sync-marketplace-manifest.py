#!/usr/bin/env python3
"""Синхронизировать target кандидата пакета с исходным манифестом."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TARGET_HEADER = re.compile(r"^target:\s*$")
TARGET_ITEM = re.compile(r"^\s*-\s+\S.*$")
VERSION = re.compile(r"^version:[^\r\n]*$", re.MULTILINE)
RELEASE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$")


def target_block(text: str, path: Path) -> tuple[list[str], int, int]:
    lines = text.splitlines(keepends=True)
    for start, line in enumerate(lines):
        if not TARGET_HEADER.fullmatch(line.rstrip("\r\n")):
            continue
        end = start + 1
        while end < len(lines) and TARGET_ITEM.fullmatch(lines[end].rstrip("\r\n")):
            end += 1
        if end == start + 1:
            raise ValueError(f"В {path} у target отсутствует список целей")
        return lines[start:end], start, end
    raise ValueError(f"В {path} не найдено поле target в блочном формате")


def sync_manifest(source: Path, package: Path, version: str) -> None:
    if not RELEASE_VERSION.fullmatch(version):
        raise ValueError("Версия должна иметь формат SemVer")
    source_text = source.read_text(encoding="utf-8")
    package_text = package.read_text(encoding="utf-8")
    source_target, _, _ = target_block(source_text, source)
    _, package_start, package_end = target_block(package_text, package)
    package_lines = package_text.splitlines(keepends=True)
    package_text = "".join(
        package_lines[:package_start]
        + source_target
        + package_lines[package_end:]
    )
    package_text, version_count = VERSION.subn(f"version: {version}", package_text, count=1)
    if version_count != 1:
        raise ValueError(f"В {package} не найдено поле version")
    package.write_text(package_text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--version", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sync_manifest(args.source, args.package, args.version)
    except (OSError, ValueError) as exc:
        print(f"Не удалось синхронизировать манифест: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

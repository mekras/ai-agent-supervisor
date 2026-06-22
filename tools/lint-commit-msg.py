#!/usr/bin/env python3
"""Проверка первой строки сообщения коммита по детерминированным правилам ru-dev.

Назначение: внешний контроль, не зависящий от того, применил ли агент навык
ru-dev. Проверяется только то, что можно проверить без понимания смысла:
язык, прописная буква в начале, форма результата вместо инфинитива и
англоязычные шаблоны выпуска версии.

Запуск:
    lint-commit-msg.py ПУТЬ_К_ФАЙЛУ_СООБЩЕНИЯ   # режим хука commit-msg
    lint-commit-msg.py -                        # читать сообщение из stdin

Код возврата: 0 — нарушений нет, 1 — есть нарушения, 2 — ошибка вызова.
Правила намеренно консервативны: лучше пропустить спорный случай, чем
заблокировать корректный коммит.
"""

from __future__ import annotations

import re
import sys

# Инфинитивы, которые навык ru-dev прямо запрещает в начале первой строки.
# Список ограничен явными примерами навыка, чтобы не давать ложных срабатываний.
INFINITIVE_PREFIXES = (
    "добавить",
    "обновить",
    "исправить",
    "удалить",
    "настроить",
)

# Англоязычные шаблоны и действия в начале первой строки.
ENGLISH_ACTION_PREFIXES = (
    "release",
    "bump",
    "version bump",
    "fix",
    "update",
    "add",
    "remove",
    "change",
    "refactor",
)

CYRILLIC_LOWER = re.compile(r"[а-яё]")
CYRILLIC_UPPER = re.compile(r"[А-ЯЁ]")


def first_meaningful_line(message: str) -> str | None:
    """Возвращает первую значимую строку или None, если её нет.

    Пропускает пустые строки и строки-комментарии, которые Git добавляет в
    шаблон сообщения (начинаются с символа комментария, по умолчанию `#`).
    """
    for raw in message.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return None


def is_skippable(subject: str) -> bool:
    """Служебные сообщения, которые правила ru-dev не регламентируют."""
    lowered = subject.lower()
    skip_prefixes = (
        "merge ",
        "revert ",
        "fixup!",
        "squash!",
        "amend!",
    )
    return lowered.startswith(skip_prefixes)


def check_subject(subject: str) -> list[str]:
    """Возвращает список нарушений первой строки сообщения."""
    problems: list[str] = []
    lowered = subject.lower()
    first_char = subject[0]

    # Англоязычное действие в начале строки.
    for prefix in ENGLISH_ACTION_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + " ") or lowered.startswith(prefix + ":"):
            problems.append(
                f"первая строка начинается с английского действия «{prefix}»; "
                "сформулируй результат по-русски, например «Выпущена версия 0.1.0»"
            )
            break

    # Инфинитив в начале строки вместо формы результата.
    for prefix in INFINITIVE_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + " ") or lowered.startswith(prefix + ":"):
            problems.append(
                f"первая строка начинается с инфинитива «{prefix}»; "
                "используй форму результата: «Добавлена», «Обновлена», «Исправлено»"
            )
            break

    # Прописная буква в начале (только для русского текста).
    if CYRILLIC_LOWER.match(first_char):
        problems.append("первая строка должна начинаться с прописной буквы")

    # Сообщение должно быть на русском, если в нём вообще есть буквы кириллицы
    # ожидаемо. Не требуем кириллицу жёстко, но предупреждаем, если первая
    # строка целиком на латинице и не была опознана как идентификатор.
    if not CYRILLIC_LOWER.search(subject) and not CYRILLIC_UPPER.search(subject):
        problems.append(
            "первая строка не содержит русского текста; пиши сообщение по-русски, "
            "если правила проекта не требуют другого языка"
        )

    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("Использование: lint-commit-msg.py ПУТЬ | -\n")
        return 2

    source = argv[1]
    if source == "-":
        message = sys.stdin.read()
    else:
        try:
            with open(source, encoding="utf-8") as handle:
                message = handle.read()
        except OSError as error:
            sys.stderr.write(f"Не удалось прочитать файл сообщения: {error}\n")
            return 2

    subject = first_meaningful_line(message)
    if subject is None:
        # Пустое сообщение Git отклонит сам; линтер не вмешивается.
        return 0

    if is_skippable(subject):
        return 0

    problems = check_subject(subject)
    if not problems:
        return 0

    sys.stderr.write("Сообщение коммита не прошло проверку ru-dev:\n")
    sys.stderr.write(f"  первая строка: {subject}\n")
    for problem in problems:
        sys.stderr.write(f"  - {problem}\n")
    sys.stderr.write(
        "\nИсправь первую строку и повтори коммит. "
        "При необходимости примени навык ru-dev.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

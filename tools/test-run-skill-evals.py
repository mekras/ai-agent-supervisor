#!/usr/bin/env python3
"""Проверки разбора длинного ответа модельного прогона."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


RUNNER = Path(__file__).with_name("run-skill-evals.py")
runner = runpy.run_path(str(RUNNER))
extract_answer_text = runner["extract_answer_text"]
PROMPT = 'Сценарий: {"id": "example-result-case"}'


def main() -> int:
    assert runner["russian_count"](1, "сценарий", "сценария", "сценариев") == "1 сценарий"
    assert runner["russian_count"](2, "сценарий", "сценария", "сценариев") == "2 сценария"
    assert runner["russian_count"](5, "сценарий", "сценария", "сценариев") == "5 сценариев"
    assert runner["russian_count"](11, "сценарий", "сценария", "сценариев") == "11 сценариев"
    assert runner["russian_count"](21, "сценарий", "сценария", "сценариев") == "21 сценарий"

    answer = extract_answer_text(
        """<<ANSWER>>
Текст с \"кавычками\", списком и {\"фрагментом\": \"JSON\"}.
</ANSWER>""",
        PROMPT,
    )
    assert answer == {
        "answers": [{
            "id": "example-result-case",
            "answer": 'Текст с "кавычками", списком и {"фрагментом": "JSON"}.',
        }],
    }

    unterminated_answer = extract_answer_text(
        """<<ANSWER>>
Ответ модели без закрывающего маркера.

```md
# AGENTS.md
```""",
        PROMPT,
    )
    assert unterminated_answer["answers"][0]["answer"] == (
        "Ответ модели без закрывающего маркера.\n\n```md\n# AGENTS.md\n```"
    )

    plain_answer = extract_answer_text(
        "Обычный текст без служебной оболочки.",
        PROMPT,
    )
    assert plain_answer["answers"][0]["answer"] == (
        "Обычный текст без служебной оболочки."
    )

    json_answer = extract_answer_text(
        '{"answers":[{"id":"example-result-case","answer":"Прежний JSON."}]}',
        PROMPT,
    )
    assert json_answer["answers"][0]["answer"] == "Прежний JSON."

    legacy_answer = extract_answer_text(
        """<<ANSWER>>
Ответ в прежней оболочке.
<</ANSWER>>""",
        PROMPT,
    )
    assert legacy_answer["answers"][0]["answer"] == "Ответ в прежней оболочке."

    adapter_output = """<<ANSWER>>
Ответ через адаптер без закрывающего маркера.

```md
# AGENTS.md
```
"""
    adapter_code = (
        "import sys; "
        "prompt = sys.stdin.read(); "
        "assert 'Верни только обычный текст ответа.' in prompt; "
        f"print({adapter_output!r})"
    )
    call = runner["make_model_call"](
        [sys.executable, "-c", adapter_code],
        "test-model",
        10,
    )
    adapter_answer = call(PROMPT, runner["ANSWER_SCHEMA"])
    assert adapter_answer["answers"][0]["answer"] == (
        "Ответ через адаптер без закрывающего маркера.\n\n"
        "```md\n# AGENTS.md\n```"
    )

    print("Проверки разбора длинных ответов модельного прогона пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

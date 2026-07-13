"""Read claim blocks from Markdown and YAML statement files."""

from __future__ import annotations

import re


MARKDOWN_CLAIM_RE = re.compile(r"^### ([A-Z0-9]+-\d+)\s*$", re.MULTILINE)
YAML_CLAIM_RE = re.compile(
    r"^\s*-\s+id:\s*[\"']?([A-Z0-9]+-\d+)[\"']?\s*(?:#.*)?$",
    re.MULTILINE,
)
PATH_SEGMENT_RE = r"[a-z0-9][a-z0-9._-]*"
PORTABLE_STATEMENT_PATH_RE = re.compile(
    rf"^knowledge/data/[a-z0-9][a-z0-9-]*/{PATH_SEGMENT_RE}/"
    rf"(?:{PATH_SEGMENT_RE}/)+statements\.yml$"
)


def collect_claim_ids(statement_text: str) -> set[str]:
    """Return every claim identifier declared in a supported statement file."""
    return set(MARKDOWN_CLAIM_RE.findall(statement_text)) | set(
        YAML_CLAIM_RE.findall(statement_text),
    )


def extract_claim_block(statement_text: str, claim_id: str) -> str:
    """Return one Markdown section or YAML list item, including its evidence."""
    for claim_re in (MARKDOWN_CLAIM_RE, YAML_CLAIM_RE):
        matches = list(claim_re.finditer(statement_text))
        for index, match in enumerate(matches):
            if match.group(1) != claim_id:
                continue
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(statement_text)
            return statement_text[start:end].strip()
    return ""

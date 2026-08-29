#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
import unicodedata
from pathlib import Path
from typing import Any


def safe_slug(phrase: str) -> str:
    normalized = unicodedata.normalize("NFKC", phrase or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_]+", "", re.sub(r"\s+", "_", normalized)).strip("_")
    if slug:
        return slug
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"wakeword_{digest}"


def parse_request(event: Any) -> dict[str, str]:
    issue: dict[str, Any] = {}
    if isinstance(event, dict):
        nested_issue = event.get("issue")
        if isinstance(nested_issue, dict):
            issue = nested_issue
        elif "title" in event and "number" in event:
            issue = event

    title = str(issue.get("title") or "")
    number = str(issue.get("number") or "")
    match = re.match(r"^\s*mww:\s*(.+?)\s*$", title, flags=re.I)
    values = {
        "SHOULD_TRAIN": "0",
        "ISSUE_NUMBER": number,
        "RAW_PHRASE": "",
        "SAFE_WORD": "",
        "REQUEST_ERROR": "",
    }

    if not match or issue.get("pull_request"):
        return values

    phrase = match.group(1).strip()
    safe = safe_slug(phrase)
    values.update({"SHOULD_TRAIN": "1", "RAW_PHRASE": phrase, "SAFE_WORD": safe})
    if len(safe) < 2:
        values["REQUEST_ERROR"] = "The wake-word request is too short."
    elif len(safe) > 64:
        values["REQUEST_ERROR"] = (
            "The wake-word request is too long. Keep it under 64 slug characters."
        )
    return values


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: parse_wake_word_request.py EVENT_JSON OUTPUT_ENV")
    event_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    values = parse_request(event)
    output_path.write_text(
        "".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items()),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

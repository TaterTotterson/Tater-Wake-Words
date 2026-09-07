#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any


ACTIVE_RUN_STATES = {"pending", "queued", "requested", "waiting", "in_progress"}
RUN_TITLE = re.compile(r"^mww #(\d+)$", flags=re.I)
REQUEST_TITLE = re.compile(r"^\s*mww\s*:", flags=re.I)
SKIP_LABELS = {"mww-added", "mww-failed"}


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def retry_issue_numbers(
    issues: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    refresh_after: timedelta = timedelta(hours=20),
) -> list[int]:
    current_time = now or datetime.now(timezone.utc)
    protected: set[int] = set()
    for run in runs:
        if str(run.get("status") or "") not in ACTIVE_RUN_STATES:
            continue
        match = RUN_TITLE.match(str(run.get("displayTitle") or ""))
        if not match:
            continue
        created_at = parse_time(run.get("createdAt"))
        if created_at is None or current_time - created_at < refresh_after:
            protected.add(int(match.group(1)))

    retries: list[int] = []
    for issue in issues:
        title = str(issue.get("title") or "")
        if not REQUEST_TITLE.match(title):
            continue
        labels = {
            str(label.get("name") or "")
            for label in issue.get("labels") or []
            if isinstance(label, dict)
        }
        number = int(issue.get("number") or 0)
        if number and not labels.intersection(SKIP_LABELS) and number not in protected:
            retries.append(number)
    return sorted(retries)


def gh_json(*args: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("GitHub CLI returned an unexpected response")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Requeue open wake-word issues that have no fresh active run."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--ref", default=os.environ.get("WAKE_WORD_REF", "main"))
    parser.add_argument("--workflow", default="train-wake-word.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")

    issues = gh_json(
        "issue",
        "list",
        "--repo",
        args.repo,
        "--state",
        "open",
        "--limit",
        "1000",
        "--json",
        "number,title,labels",
    )
    runs = gh_json(
        "run",
        "list",
        "--repo",
        args.repo,
        "--workflow",
        args.workflow,
        "--limit",
        "1000",
        "--json",
        "status,displayTitle,createdAt",
    )
    retries = retry_issue_numbers(issues, runs)
    if not retries:
        print("All open wake-word requests already have a fresh active run.")
        return

    for issue_number in retries:
        if args.dry_run:
            print(f"Would requeue wake-word issue #{issue_number}")
            continue
        subprocess.run(
            [
                "gh",
                "workflow",
                "run",
                args.workflow,
                "--repo",
                args.repo,
                "--ref",
                args.ref,
                "-f",
                f"issue_number={issue_number}",
            ],
            check=True,
        )
        print(f"Requeued wake-word issue #{issue_number}")


if __name__ == "__main__":
    main()

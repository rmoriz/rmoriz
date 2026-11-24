#!/usr/bin/env python3
"""Render the newest releases of a fixed repo list into README.md."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOS = ("git-time", "microwave-development", "ai-classification-milter", "vagrant-registry")
FEED = "https://github.com/rmoriz/{repo}/releases.atom"
MAX_AGE = timedelta(days=120)
MAX_ENTRIES = 5
MAX_PER_REPO = 2
START = "<!-- recent:start -->"
END = "<!-- recent:end -->"
README = Path(__file__).resolve().parent.parent / "README.md"
NS = {"a": "http://www.w3.org/2005/Atom"}
ESCAPE = ("\\", "[", "]", "*", "_", "`")


def escape(text: str) -> str:
    for char in ESCAPE:
        text = text.replace(char, "\\" + char)
    return " ".join(text.split())


def parse(feed: bytes, repo: str) -> list[tuple[datetime, str]]:
    """Yield (updated, rendered line) for every usable entry in one feed."""
    try:
        root = ET.fromstring(feed)
    except ET.ParseError:
        return []

    entries = []
    for entry in root.findall("a:entry", NS):
        title = (entry.findtext("a:title", namespaces=NS) or "").strip()
        updated = entry.findtext("a:updated", namespaces=NS) or ""
        link = ""
        for candidate in entry.findall("a:link", NS):
            if candidate.get("rel", "alternate") == "alternate" and candidate.get("href"):
                link = candidate.get("href", "")
                break
        try:
            when = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            continue
        if not title or not link:
            continue
        entry_line = f"- **[{repo}]({link})** — {escape(title)} ({when:%Y-%m-%d})"
        entries.append((when, entry_line))
    return entries


def render(feeds: dict[str, bytes], now: datetime) -> str:
    """Return the block body, newest first, or "" when nothing is fresh."""
    entries = []
    for repo, feed in feeds.items():
        per_repo = sorted(parse(feed, repo), reverse=True)[:MAX_PER_REPO]
        entries.extend(per_repo)
    fresh = [line for when, line in sorted(entries, reverse=True) if now - when <= MAX_AGE]
    return "\n".join(fresh[:MAX_ENTRIES])


def splice(readme: str, block: str) -> str:
    """Put block between the markers; empty block leaves the readme alone."""
    if not block or START not in readme or END not in readme:
        return readme
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def fetch(repo: str) -> bytes:
    request = urllib.request.Request(
        FEED.format(repo=repo), headers={"User-Agent": "rmoriz-profile-readme"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(500_000)


def main(argv: list[str]) -> int:
    feeds = {}
    for repo in REPOS:
        try:
            feeds[repo] = fetch(repo)
        except (urllib.error.URLError, OSError):
            continue

    block = render(feeds, datetime.now(timezone.utc))
    if "--dry-run" in argv:
        print(block or "(empty)")
        return 0

    current = README.read_text()
    updated = splice(current, block)
    if updated != current:
        README.write_text(updated)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

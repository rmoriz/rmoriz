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

REPOS = ("git-time", "microwave-development", "vagrant-registry", "bird-mcp")
FEED = "https://github.com/rmoriz/{repo}/releases.atom"
COMMITS = "https://github.com/rmoriz/{repo}/commits/main.atom"
MAX_AGE = timedelta(days=120)
MAX_ENTRIES = 5
MAX_PER_REPO = 2
SKIP_PREFIX = re.compile(r"^(chore|docs|test|ci|build|style)(\([^)]*\))?!?:\s*")
KEEP_PREFIX = re.compile(r"^(feat|fix|perf|refactor|revert|data)(\([^)]*\))?!?:\s*")
SKIP_TITLE = ("Merge pull request", "Merge branch")
SKIP_TAGS = ("latest", "continuous", "nightly", "snapshot")
SKIP_RELEASE_TITLE = re.compile(r"^Latest build\b")
START = "<!-- recent:start -->"
END = "<!-- recent:end -->"
README = Path(__file__).resolve().parent.parent / "README.md"
NS = {"a": "http://www.w3.org/2005/Atom"}
ESCAPE = ("\\", "[", "]", "*", "_", "`")


def escape(text: str) -> str:
    for char in ESCAPE:
        text = text.replace(char, "\\" + char)
    return " ".join(text.split())


def parse(feed: bytes, repo: str, kind: str = "release") -> list[tuple[datetime, str]]:
    """Yield (updated, rendered line) for every usable entry in one feed."""
    try:
        root = ET.fromstring(feed)
    except ET.ParseError:
        return []

    entries = []
    for entry in root.findall("a:entry", NS):
        title = (entry.findtext("a:title", namespaces=NS) or "").strip()
        if kind == "commit":
            if title.startswith(SKIP_TITLE) or SKIP_PREFIX.match(title):
                continue
            title = KEEP_PREFIX.sub("", title)
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
        if kind == "release" and (
            link.rstrip("/").rsplit("/", 1)[-1] in SKIP_TAGS
            or SKIP_RELEASE_TITLE.match(title)
        ):
            continue
        entry_line = f"- **[{repo}]({link})** — {escape(title)} ({when:%Y-%m-%d})"
        entries.append((when, entry_line))
    return entries


def render(feeds: dict[str, bytes], now: datetime, commits: dict[str, bytes] | None = None) -> str:
    """Return the block body, newest first, or "" when nothing is fresh.

    A repo without a fresh release falls back to its newest real commit.
    """
    commits = commits or {}
    entries = []
    for repo, feed in feeds.items():
        fresh = sorted(
            (entry for entry in parse(feed, repo) if now - entry[0] <= MAX_AGE), reverse=True
        )
        if not fresh and repo in commits:
            fresh = sorted(
                (
                    entry
                    for entry in parse(commits[repo], repo, "commit")
                    if now - entry[0] <= MAX_AGE
                ),
                reverse=True,
            )[:1]
        entries.extend(fresh[:MAX_PER_REPO])
    return "\n".join(line for _, line in sorted(entries, reverse=True)[:MAX_ENTRIES])


def splice(readme: str, block: str) -> str:
    """Put block between the markers; empty block leaves the readme alone."""
    if not block or START not in readme or END not in readme:
        return readme
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "rmoriz-profile-readme"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(500_000)


def main(argv: list[str]) -> int:
    feeds: dict[str, bytes] = {}
    commits: dict[str, bytes] = {}
    for repo in REPOS:
        for url, into in ((FEED, feeds), (COMMITS, commits)):
            try:
                into[repo] = fetch(url.format(repo=repo))
            except (urllib.error.URLError, OSError):
                into.setdefault(repo, b"")

    block = render(feeds, datetime.now(timezone.utc), commits)
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

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import recent  # noqa: E402

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
FIXTURE = (ROOT / "tests" / "fixtures" / "releases.atom").read_bytes()
COMMITS = (ROOT / "tests" / "fixtures" / "commits.atom").read_bytes()
README = "intro\n<!-- recent:start -->\n<!-- recent:end -->\noutro\n"


def feed(*entries: tuple[str, str]) -> bytes:
    body = "".join(
        f'<entry><title>{title}</title><updated>{when}</updated>'
        f'<link rel="alternate" href="https://example.test/{title}"/></entry>'
        for title, when in entries
    )
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


def rolling_feed(*extra: tuple[str, str]) -> bytes:
    """A feed whose newest release is a rolling 'latest' build, plus optional normal ones."""
    entries = [
        '<entry><title>Latest build (abc1234)</title>'
        "<updated>2026-11-22T00:00:00Z</updated>"
        '<link rel="alternate" href="https://github.com/rmoriz/bird-mcp/releases/tag/latest"/>'
        "</entry>"
    ] + [
        f'<entry><title>{title}</title><updated>{when}</updated>'
        f'<link rel="alternate" href="https://github.com/rmoriz/bird-mcp/releases/tag/{title}"/>'
        "</entry>"
        for title, when in extra
    ]
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{"".join(entries)}</feed>'.encode()


class RenderTest(unittest.TestCase):
    def test_renders_newest_first_and_escapes_titles(self):
        self.assertEqual(
            recent.render({"git-time": FIXTURE}, now=NOW),
            "- **[git-time](https://github.com/rmoriz/git-time/releases/tag/v1.2.1)**"
            " — Fix \\`x\\` \\[again\\] (2026-11-21)\n"
            "- **[git-time](https://github.com/rmoriz/git-time/releases/tag/v1.2.0)**"
            " — v1.2.0 (2026-11-20)",
        )

    def test_drops_entries_older_than_max_age(self):
        self.assertNotIn("v0.1.0", recent.render({"git-time": FIXTURE}, now=NOW))

    def test_caps_at_five_entries(self):
        feeds = {
            repo: feed(
                *[(f"{repo}{i}", f"2026-11-{10 + i:02d}T00:00:00Z") for i in range(4)]
            )
            for repo in ("a", "b", "c")
        }
        block = recent.render(feeds, now=NOW)
        self.assertEqual(len(block.splitlines()), recent.MAX_ENTRIES)

    def test_caps_at_two_entries_per_repo(self):
        busy = feed(
            *[(f"v{i}", f"2026-11-{10 + i:02d}T00:00:00Z") for i in range(4)]
        )
        quiet = feed(("q1", "2026-11-01T00:00:00Z"))
        block = recent.render({"busy": busy, "quiet": quiet}, now=NOW)
        self.assertEqual(block.count("[busy]"), recent.MAX_PER_REPO)
        self.assertIn("[quiet]", block)

    def test_empty_input_gives_empty_block(self):
        self.assertEqual(recent.render({}, now=NOW), "")

    def test_broken_feed_does_not_raise(self):
        self.assertEqual(recent.render({"git-time": b"<html>404</html>"}, now=NOW), "")

    def test_skips_rolling_latest_release(self):
        rolling = rolling_feed(("v1.0.0", "2026-11-20T00:00:00Z"))
        block = recent.render({"bird-mcp": rolling}, now=NOW)
        self.assertIn("v1.0.0", block)
        self.assertNotIn("Latest build", block)

    def test_output_is_stable(self):
        self.assertEqual(
            recent.render({"git-time": FIXTURE}, now=NOW),
            recent.render({"git-time": FIXTURE}, now=NOW),
        )


class CommitFallbackTest(unittest.TestCase):
    def test_falls_back_to_newest_real_commit_without_release(self):
        commits = {"vagrant-registry": COMMITS}
        self.assertEqual(
            recent.render({"vagrant-registry": b""}, now=NOW, commits=commits),
            "- **[vagrant-registry](https://github.com/rmoriz/vagrant-registry/commit/bbb)**"
            " — cache catalogs at the edge, not in the browser (2026-11-24)",
        )

    def test_fresh_release_wins_over_commit(self):
        block = recent.render(
            {"git-time": FIXTURE}, now=NOW, commits={"git-time": COMMITS}
        )
        self.assertNotIn("/commit/", block)

    def test_rolling_release_falls_back_to_commit(self):
        block = recent.render(
            {"vagrant-registry": rolling_feed()},
            now=NOW,
            commits={"vagrant-registry": COMMITS},
        )
        self.assertIn("/commit/", block)
        self.assertNotIn("Latest build", block)

    def test_stale_commit_is_dropped(self):
        stale = feed(("docs: old entry", "2023-01-01T00:00:00Z"))
        self.assertEqual(
            recent.render({"repo": b""}, now=NOW, commits={"repo": stale}), ""
        )


class SpliceTest(unittest.TestCase):
    def test_empty_block_keeps_readme(self):
        self.assertEqual(recent.splice(README, ""), README)

    def test_replaces_block_between_markers(self):
        self.assertEqual(
            recent.splice(README, "- a\n- b"),
            "intro\n<!-- recent:start -->\n- a\n- b\n<!-- recent:end -->\noutro\n",
        )

    def test_missing_markers_keep_readme(self):
        self.assertEqual(recent.splice("no markers\n", "- a"), "no markers\n")


if __name__ == "__main__":
    unittest.main()

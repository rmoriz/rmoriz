# GitHub profile README Implementation Plan

> **For agentic workers:** use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish `rmoriz/rmoriz` with an English profile README that works for two audiences (contract clients and OSS peers) and one self-maintaining "Recently shipped" block from GitHub release feeds.

**Architecture:** Static Markdown, one curated list per section. A daily GitHub Actions job fetches `releases.atom` for four fixed repos, renders the five newest entries between `<!-- recent:start -->` and `<!-- recent:end -->`, and commits only when the rendered block changes.

**Tech Stack:** Markdown, GitHub Actions, Python 3.13 stdlib (`urllib`, `xml.etree`).

**Spec:** this document (design agreed in chat 2026-11-24).

## Global Constraints

- Language: English. Tone: plain, no buzzwords, no emoji, no "available for hire" cliché — one `Contract work:` line.
- Contact: `roland@moriz.de` (taken from public commit signatures).
- No stats cards, badges, skill icons, snake, WakaTime.
- Dynamic content limited to the `recent` block. Feed repos: `git-time`, `microwave-development`, `vagrant-registry`.
- Repos without a fresh release contribute their newest non-chore commit instead (feat/fix/perf/refactor/data), stripped of the conventional prefix.
- At most 5 entries, newest first, each `- **[repo](link)** — title (YYYY-MM-DD)`.
- Workflow: daily 06:17 UTC + `workflow_dispatch`, `permissions: contents: write`, no third-party actions.

## Review Focus

- Feed repo returns 404/HTML/empty → script must exit 0 and leave the block untouched, never write an error into the README.
- Entries older than 120 days → dropped, so a dead project cannot pin the block.
- Title containing Markdown specials (`[`, `]`, `*`, backticks) → escaped so links stay intact.
- Commit loop → second run with unchanged feeds must produce no commit.
- README > 8 KB → profile page truncates; check size.

---

### Task 1: README

**Files:** Create `README.md`

**Interfaces:** Produces the two markers `<!-- recent:start -->` / `<!-- recent:end -->` that Task 2 fills.

- [ ] **Step 1: Write `README.md` with exactly this content**

```markdown
### Rust and Ruby, infrastructure, SRE

Verifiable git timestamps, ACME challenges that survive a restart, Chef infra in Rust, a mail milter that asks several models at once. Small tools, self-hosted, no vendor in the middle.

**Contract work:** scoped projects on Rust, Ruby, ACME/PKI, Chef/Cinc migrations, SRE and hardened self-hosted setups → [roland@moriz.de](mailto:roland@moriz.de)

## Now

- **[git-time](https://github.com/rmoriz/git-time)** — git with verifiable RFC 3161 timestamps
- **[dns-persist-01-example-rust](https://github.com/rmoriz/dns-persist-01-example-rust)** — ACME dns-persist-01 challenge; the validation record derives from account, domain and CA instead of a per-order token
- **[microwave-development](https://github.com/rmoriz/microwave-development)** — a Chef Infra server implementation in Rust

## Selected work

- **[vagrant-registry](https://github.com/rmoriz/vagrant-registry)** — read-only Vagrant box registry, one handler serving catalog JSON as Cloudflare Worker and as a container
- **[netbird-embed-rs](https://github.com/rmoriz/netbird-embed-rs)** — a WireGuard mesh node embedded into a Rust application through Go c-shared FFI

## Recently shipped

<!-- recent:start -->
<!-- recent:end -->

## Stack

Rust · Ruby · Chef/Cinc · ACME/PKI · Postfix · Linux · DNS · self-hosted everything

## Elsewhere

GitHub [@rmoriz](https://github.com/rmoriz) · [roland@moriz.de](mailto:roland@moriz.de)
```

- [ ] **Step 2: Check size and markers**

Run: `wc -c README.md && grep -c 'recent:\(start\|end\)' README.md`
Expected: under 3000 bytes, `2`.

- [ ] **Step 3: Commit**

```bash
git add README.md && git commit -m "Add profile README"
```

### Task 2: Recent-releases renderer

**Files:** Create `scripts/recent.py`, `tests/fixtures/releases.atom`, `tests/test_recent.py`, `.github/workflows/recent.yml`

**Interfaces:** Produces `render(feeds: dict[str, bytes], now: datetime) -> str` (the block body, `""` when nothing to show) and `splice(readme: str, block: str) -> str`, used by `main()`.

- [ ] **Step 1: Write `tests/fixtures/releases.atom`** — one valid Atom feed with two `<entry>` elements (titles `v1.2.0` and `Fix \`x\` [again]`) and `<updated>` values 2026-11-20T10:00:00Z and 2024-01-01T00:00:00Z, plus one entry with a `<link rel="alternate" href="...">`.
- [ ] **Step 2: Write `tests/test_recent.py`** with `unittest` cases asserting `render` output:

```python
block = recent.render({"git-time": FIXTURE}, now=NOW)
assert block == "- **[git-time](https://github.com/rmoriz/git-time/releases/tag/v1.2.0)** — v1.2.0 (2026-11-20)"
```
plus: stale entry dropped, `render({}, now=NOW) == ""`, title with brackets escaped, `splice` leaves README unchanged when block is `""`, and `render` output stable across two calls (no timestamps).

- [ ] **Step 3: Run tests, expect ImportError**

Run: `python3 -m unittest discover -s tests -v`

- [ ] **Step 4: Implement `scripts/recent.py`** (stdlib only): `REPOS` tuple with the four repos, `FEED = "https://github.com/rmoriz/{repo}/releases.atom"`, `MAX_AGE = timedelta(days=120)`; `render` parses `<entry>/<title|updated|link>` with `xml.etree.ElementTree`, skips parse errors, escapes `\ ` `[` `]` `*` `_` in titles, holds `release/tag` URL for the link (fall back to repo releases page), sorts by `updated` desc, takes 5; `splice` replaces text between markers, returns input unchanged for empty block; `main` fetches each feed with `urllib.request` (`timeout=20`, `User-Agent` set, 404/HTTPError/HTML body → skip), reads/writes `README.md`, exits 0 always.

- [ ] **Step 5: Run tests, expect PASS**

- [ ] **Step 6: Live check without writing**

Run: `python3 scripts/recent.py --dry-run`
Expected: exit 0, at least one real entry printed from the four feeds.

- [ ] **Step 7: Write `.github/workflows/recent.yml`** — `on: schedule: - cron: "17 6 * * *"` and `workflow_dispatch:`, `permissions: contents: write`, `concurrency: recent`, steps: `actions/checkout@v4`, `python3 scripts/recent.py`, `git diff --quiet || (git config user.name github-actions[bot] && git add README.md && git commit -m "chore: update recently shipped" && git push)`.

- [ ] **Step 8: Commit**

### Task 3: Publish and verify

- [ ] **Step 1:** `gh repo create rmoriz --public --description "profile" --source . --push`
- [ ] **Step 2:** `gh workflow run recent.yml` → wait → `gh run list --workflow recent.yml -L1` shows success; `git pull` and confirm the block has entries
- [ ] **Step 3:** Re-run: `git diff --quiet && echo no-change`
- [ ] **Step 4:** `gh api repos/rmoriz/rmoriz --jq .name` and fetch the public profile to confirm the README renders above pinned repos

# gitstat 📊

Quick git repository health overview. See status, uncommitted changes, stale branches, and unpushed commits across all your repos at a glance.

## Features

- **Multi-repo scanning** — check one repo or scan a directory tree
- **Health indicators** — dirty/clean status, staged/modified/untracked counts
- **Upstream tracking** — ahead/behind remote
- **Stale branch detection** — branches with no activity >30 days
- **Stash awareness** — reminds you about forgotten stashes
- **JSON output** — pipe to other tools
- **Zero deps** — pure Python 3.10+

## Usage

```bash
# Single repo
python3 gitstat.py .

# All repos in a directory
python3 gitstat.py ~/projects --recursive

# Multiple specific repos
python3 gitstat.py repo1 repo2 repo3

# JSON output
python3 gitstat.py ~/projects -r --json

# Custom recursion depth
python3 gitstat.py ~/code -r --depth 3
```

## Output

```
my-project  ●  main
  +2 staged  ~1 modified  ?3 untracked  ↑1
  142 commits · 2h ago · fix: resolve race condition in worker pool
  ⬆ 1 unpushed commit(s)
  ⚠ Uncommitted changes

utils  ○  main
  28 commits · 5d ago · docs: update API reference

old-experiment  ○  develop
  12 commits · 45d ago · initial prototype
  🪵 1 stale branch(es)

────────────────────────────────────────
3 repos: 2 clean, 1 dirty
```

## Warnings

| Warning | Meaning |
|---------|---------|
| ⬆ unpushed | Local commits not pushed to remote |
| ⬇ behind | Remote has commits you haven't pulled |
| 📦 stashes | Forgotten stash entries |
| 🪵 stale branches | Branches inactive >30 days |
| ⚠ uncommitted | Working tree has changes |

## Options

| Flag | Description |
|------|-------------|
| `--recursive, -r` | Find repos recursively in given paths |
| `--depth, -d` | Max recursion depth (default: 2) |
| `--json, -j` | JSON output |

## License

MIT

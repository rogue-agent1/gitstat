#!/usr/bin/env python3
"""gitstat — Quick git repository health overview.

Usage:
    gitstat [PATH...] [--json] [--recursive] [--depth N]

Examples:
    gitstat .
    gitstat ~/projects --recursive
    gitstat repo1 repo2 --json
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RepoStat:
    path: str = ""
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    modified: int = 0
    untracked: int = 0
    stashes: int = 0
    last_commit_date: str = ""
    last_commit_msg: str = ""
    last_commit_age: str = ""
    total_commits: int = 0
    contributors: int = 0
    branches_local: int = 0
    branches_stale: list = field(default_factory=list)  # branches with no activity >30d
    remotes: list = field(default_factory=list)
    dirty: bool = False
    warnings: list = field(default_factory=list)


def run_git(repo_path: str, *args) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + list(args),
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_repo_stat(repo_path: str) -> RepoStat:
    """Gather stats for a single git repo."""
    stat = RepoStat(path=str(repo_path))

    # Branch
    stat.branch = run_git(repo_path, "branch", "--show-current") or run_git(repo_path, "rev-parse", "--short", "HEAD")

    # Ahead/behind
    upstream = run_git(repo_path, "rev-parse", "--abbrev-ref", f"{stat.branch}@{{upstream}}")
    if upstream:
        ab = run_git(repo_path, "rev-list", "--left-right", "--count", f"{stat.branch}...{upstream}")
        if ab and "\t" in ab:
            parts = ab.split("\t")
            stat.ahead = int(parts[0])
            stat.behind = int(parts[1])

    # Status
    status = run_git(repo_path, "status", "--porcelain")
    if status:
        for line in status.split("\n"):
            if not line:
                continue
            idx, wt = line[0], line[1]
            if idx in "MADRC":
                stat.staged += 1
            if wt in "MD":
                stat.modified += 1
            if line.startswith("??"):
                stat.untracked += 1

    stat.dirty = (stat.staged + stat.modified + stat.untracked) > 0

    # Stashes
    stash_list = run_git(repo_path, "stash", "list")
    stat.stashes = len(stash_list.split("\n")) if stash_list else 0

    # Last commit
    log = run_git(repo_path, "log", "-1", "--format=%aI|%s")
    if log and "|" in log:
        date_str, msg = log.split("|", 1)
        stat.last_commit_date = date_str
        stat.last_commit_msg = msg[:80]
        try:
            dt = datetime.fromisoformat(date_str)
            now = datetime.now(timezone.utc)
            delta = now - dt.astimezone(timezone.utc)
            if delta.days > 0:
                stat.last_commit_age = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                stat.last_commit_age = f"{delta.seconds // 3600}h ago"
            else:
                stat.last_commit_age = f"{delta.seconds // 60}m ago"
        except (ValueError, TypeError):
            pass

    # Total commits
    count = run_git(repo_path, "rev-list", "--count", "HEAD")
    stat.total_commits = int(count) if count.isdigit() else 0

    # Contributors
    shortlog = run_git(repo_path, "shortlog", "-sn", "--all")
    stat.contributors = len([l for l in shortlog.split("\n") if l.strip()]) if shortlog else 0

    # Branches
    branches = run_git(repo_path, "branch", "--format=%(refname:short)")
    branch_list = [b.strip() for b in branches.split("\n") if b.strip()] if branches else []
    stat.branches_local = len(branch_list)

    # Stale branches (>30 days no activity)
    for b in branch_list:
        if b == stat.branch:
            continue
        last = run_git(repo_path, "log", "-1", "--format=%aI", b)
        if last:
            try:
                dt = datetime.fromisoformat(last)
                delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
                if delta.days > 30:
                    stat.branches_stale.append(f"{b} ({delta.days}d)")
            except (ValueError, TypeError):
                pass

    # Remotes
    remotes = run_git(repo_path, "remote", "-v")
    seen = set()
    for line in remotes.split("\n"):
        if line and "(fetch)" in line:
            parts = line.split()
            if len(parts) >= 2 and parts[0] not in seen:
                seen.add(parts[0])
                stat.remotes.append(parts[0])

    # Warnings
    if stat.ahead > 0:
        stat.warnings.append(f"⬆ {stat.ahead} unpushed commit(s)")
    if stat.behind > 0:
        stat.warnings.append(f"⬇ {stat.behind} commits behind upstream")
    if stat.stashes > 0:
        stat.warnings.append(f"📦 {stat.stashes} stash(es)")
    if stat.branches_stale:
        stat.warnings.append(f"🪵 {len(stat.branches_stale)} stale branch(es)")
    if stat.dirty:
        stat.warnings.append("⚠ Uncommitted changes")

    return stat


def find_repos(paths: list[str], recursive: bool = False, depth: int = 2) -> list[str]:
    """Find git repos in given paths."""
    repos = []
    for p in paths:
        path = Path(p).resolve()
        if (path / ".git").exists():
            repos.append(str(path))
        elif recursive:
            for root, dirs, files in os.walk(path):
                rel_depth = str(root).count(os.sep) - str(path).count(os.sep)
                if rel_depth >= depth:
                    dirs.clear()
                    continue
                if ".git" in dirs:
                    repos.append(root)
                    dirs.remove(".git")
    return sorted(repos)


# Colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"


def format_text(stats: list[RepoStat]) -> str:
    lines = []
    for s in stats:
        name = Path(s.path).name
        status_color = RED if s.dirty else GREEN
        status_icon = "●" if s.dirty else "○"

        lines.append(f"{BOLD}{name}{RESET}  {status_color}{status_icon}{RESET}  {DIM}{s.branch}{RESET}")

        detail = []
        if s.staged:
            detail.append(f"{GREEN}+{s.staged} staged{RESET}")
        if s.modified:
            detail.append(f"{YELLOW}~{s.modified} modified{RESET}")
        if s.untracked:
            detail.append(f"{RED}?{s.untracked} untracked{RESET}")
        if s.ahead:
            detail.append(f"{CYAN}↑{s.ahead}{RESET}")
        if s.behind:
            detail.append(f"{YELLOW}↓{s.behind}{RESET}")

        if detail:
            lines.append(f"  {' '.join(detail)}")

        lines.append(f"  {DIM}{s.total_commits} commits · {s.last_commit_age} · {s.last_commit_msg}{RESET}")

        for w in s.warnings:
            lines.append(f"  {YELLOW}{w}{RESET}")

        lines.append("")

    # Summary
    total = len(stats)
    dirty = sum(1 for s in stats if s.dirty)
    clean = total - dirty
    lines.append(f"{DIM}{'─' * 40}{RESET}")
    lines.append(f"{total} repos: {GREEN}{clean} clean{RESET}, {RED}{dirty} dirty{RESET}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(prog="gitstat", description="Quick git repo health overview")
    parser.add_argument("paths", nargs="*", default=["."], help="Paths to check")
    parser.add_argument("--recursive", "-r", action="store_true", help="Find repos recursively")
    parser.add_argument("--depth", "-d", type=int, default=2, help="Max recursion depth")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    repos = find_repos(args.paths, args.recursive, args.depth)
    if not repos:
        print("No git repositories found.", file=sys.stderr)
        sys.exit(1)

    stats = [get_repo_stat(r) for r in repos]

    if args.json:
        print(json.dumps([asdict(s) for s in stats], indent=2))
    else:
        print(format_text(stats))


if __name__ == "__main__":
    main()

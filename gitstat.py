#!/usr/bin/env python3
"""gitstat - git repository statistics (commits, authors, files, activity, churn)."""

import argparse, subprocess, sys, os, re, time
from collections import Counter, defaultdict
from datetime import datetime

def git(args, repo="."):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=repo)
    return r.stdout.strip()

def cmd_summary(args):
    repo = args.repo
    print(f"\n  Git Summary: {os.path.basename(os.path.abspath(repo))}")
    print("  " + "─" * 45)

    # Branch
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    total = int(git(["rev-list", "--count", "HEAD"], repo) or 0)
    first = git(["log", "--reverse", "--format=%ai", "-1"], repo)
    latest = git(["log", "--format=%ai", "-1"], repo)
    remotes = git(["remote", "-v"], repo)

    print(f"  Branch:       {branch}")
    print(f"  Commits:      {total}")
    print(f"  First commit: {first[:10] if first else '?'}")
    print(f"  Last commit:  {latest[:10] if latest else '?'}")

    # Authors
    authors = git(["shortlog", "-sn", "--no-merges", "HEAD"], repo)
    author_list = []
    for line in authors.splitlines():
        m = re.match(r'\s*(\d+)\s+(.*)', line)
        if m:
            author_list.append((int(m.group(1)), m.group(2)))
    print(f"  Authors:      {len(author_list)}")

    # Files
    files = git(["ls-files"], repo).splitlines()
    print(f"  Files:        {len(files)}")

    # Extensions
    exts = Counter()
    for f in files:
        _, ext = os.path.splitext(f)
        exts[ext or "(none)"] += 1
    print(f"\n  Top file types:")
    for ext, cnt in exts.most_common(8):
        print(f"    {ext:<12} {cnt:>5}")

    # Top authors
    if author_list:
        print(f"\n  Top authors:")
        for cnt, name in author_list[:8]:
            pct = cnt * 100 / total if total else 0
            bar = "█" * int(pct / 3) + "░" * (20 - int(pct / 3))
            print(f"    {name:<25} {cnt:>5} ({pct:>4.1f}%) {bar}")
    print()

def cmd_activity(args):
    repo = args.repo
    days = args.days
    since = f"--since={days} days ago" if days else ""
    log_args = ["log", "--format=%ai", "--no-merges"]
    if since:
        log_args.append(since)
    raw = git(log_args, repo)
    if not raw:
        print("  No commits found")
        return

    by_hour = Counter()
    by_dow = Counter()
    by_date = Counter()
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for line in raw.splitlines():
        try:
            dt = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
            by_hour[dt.hour] += 1
            by_dow[dt.weekday()] += 1
            by_date[dt.strftime("%Y-%m-%d")] += 1
        except ValueError:
            pass

    total = sum(by_hour.values())
    period = f"last {days} days" if days else "all time"
    print(f"\n  Activity ({period}, {total} commits)")
    print("  " + "─" * 45)

    # By hour
    print(f"\n  By hour:")
    mx = max(by_hour.values()) if by_hour else 1
    for h in range(24):
        c = by_hour.get(h, 0)
        bar = "█" * int(c * 30 / mx) if mx else ""
        print(f"    {h:02d}:00  {bar} {c}")

    # By day of week
    print(f"\n  By day:")
    mx = max(by_dow.values()) if by_dow else 1
    for d in range(7):
        c = by_dow.get(d, 0)
        bar = "█" * int(c * 20 / mx) if mx else ""
        print(f"    {dow_names[d]}  {bar} {c}")

    # Most active days
    if by_date:
        print(f"\n  Most active days:")
        for date, cnt in by_date.most_common(5):
            print(f"    {date}  {cnt} commits")
    print()

def cmd_churn(args):
    repo = args.repo
    n = args.top
    log = git(["log", "--format=", "--numstat", "--no-merges", "-200"], repo)
    file_churn = defaultdict(lambda: {"add": 0, "del": 0, "commits": 0})
    seen_files = set()

    for line in log.splitlines():
        parts = line.split('\t')
        if len(parts) == 3:
            add, delete, path = parts
            if add == '-' or delete == '-':
                continue
            file_churn[path]["add"] += int(add)
            file_churn[path]["del"] += int(delete)
            if path not in seen_files:
                file_churn[path]["commits"] += 1

    if not file_churn:
        print("  No churn data")
        return

    # Sort by total changes
    ranked = sorted(file_churn.items(), key=lambda x: x[1]["add"] + x[1]["del"], reverse=True)

    print(f"\n  File Churn (top {n}, last 200 commits)")
    print("  " + "─" * 60)
    print(f"  {'FILE':<40} {'ADDED':>7} {'DELETED':>7} {'TOTAL':>7}")
    for path, stats in ranked[:n]:
        total = stats["add"] + stats["del"]
        name = path if len(path) <= 39 else "…" + path[-38:]
        print(f"  {name:<40} {'+' + str(stats['add']):>7} {'-' + str(stats['del']):>7} {total:>7}")
    print()

def cmd_blame(args):
    repo = args.repo
    f = args.file
    raw = git(["blame", "--line-porcelain", f], repo)
    if not raw:
        print(f"  Cannot blame {f}")
        return
    authors = Counter()
    for line in raw.splitlines():
        if line.startswith("author "):
            authors[line[7:]] += 1

    total = sum(authors.values())
    print(f"\n  Blame: {f} ({total} lines)")
    print("  " + "─" * 45)
    for name, cnt in authors.most_common(10):
        pct = cnt * 100 / total
        bar = "█" * int(pct / 3)
        print(f"    {name:<25} {cnt:>5} ({pct:>4.1f}%) {bar}")
    print()

def main():
    p = argparse.ArgumentParser(description="Git repository statistics")
    sp = p.add_subparsers(dest="cmd")

    s = sp.add_parser("summary", help="Repository summary")
    s.add_argument("repo", nargs="?", default=".")
    s.set_defaults(func=cmd_summary)

    a = sp.add_parser("activity", help="Commit activity patterns")
    a.add_argument("repo", nargs="?", default=".")
    a.add_argument("-d", "--days", type=int, help="Last N days")
    a.set_defaults(func=cmd_activity)

    c = sp.add_parser("churn", help="File churn analysis")
    c.add_argument("repo", nargs="?", default=".")
    c.add_argument("-n", "--top", type=int, default=15)
    c.set_defaults(func=cmd_churn)

    b = sp.add_parser("blame", help="Blame summary for a file")
    b.add_argument("file")
    b.add_argument("--repo", default=".")
    b.set_defaults(func=cmd_blame)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Gather work data from git commits and Claude sessions for report generation."""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"
PROJECTS_DIR = CLAUDE_DIR / "projects"
LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_date(s: str) -> datetime:
    """Parse ISO date or relative period like 'today', 'yesterday', 'this-week'."""
    s = s.strip().lower()
    now = datetime.now(LOCAL_TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if s == "today":
        return today
    if s == "yesterday":
        return today - timedelta(days=1)
    if s in ("this-week", "week"):
        return today - timedelta(days=today.weekday())
    if s in ("this-month", "month"):
        return today.replace(day=1)
    if s == "last-week":
        monday = today - timedelta(days=today.weekday())
        return monday - timedelta(days=7)
    if s == "last-month":
        first = today.replace(day=1)
        return (first - timedelta(days=1)).replace(day=1)

    # Try ISO format
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def load_claude_sessions(since: datetime, until: datetime) -> list[dict]:
    """Find Claude sessions within the date range, return list of {project, sessionId, messages}."""
    if not HISTORY_FILE.exists():
        return []

    sessions_by_id: dict[str, dict] = {}

    with open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = entry.get("timestamp")
            if not ts:
                continue
            t = datetime.fromtimestamp(ts / 1000, tz=LOCAL_TZ)
            if t < since or t > until:
                continue

            sid = entry.get("sessionId")
            project = entry.get("project", "")
            display = entry.get("display", "")

            if sid and sid not in sessions_by_id:
                sessions_by_id[sid] = {
                    "sessionId": sid,
                    "project": project,
                    "projectName": os.path.basename(project) if project else "",
                    "messages": [],
                }

            if sid and display:
                sessions_by_id[sid]["messages"].append(display)

    # For each session, try to read the project-level jsonl for richer content
    results = []
    for sid, info in sessions_by_id.items():
        project = info["project"]
        if project:
            safe_name = "-" + re.sub(r"[^a-zA-Z0-9_-]", "-", project.lstrip("/"))
            session_file = PROJECTS_DIR / safe_name / f"{sid}.jsonl"
            if session_file.exists():
                user_messages = extract_user_messages(session_file, since, until)
                info["userMessages"] = user_messages

        info["messageCount"] = len(info.get("userMessages", info["messages"]))
        results.append(info)

    results.sort(key=lambda x: x.get("messageCount", 0), reverse=True)
    return results


def extract_user_messages(filepath: Path, since: datetime, until: datetime) -> list[str]:
    """Extract user messages from a session jsonl file."""
    messages = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "user":
                    continue

                msg = entry.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Content can be a list of content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = " ".join(text_parts)

                if content:
                    # Skip system/command messages
                    if any(skip in content for skip in (
                        "<local-command", "<command-name>", "<command-message>",
                        "<local-command-stdout", "[Request interrupted",
                        "Caveat: The messages below",
                    )):
                        continue
                    # Truncate very long messages
                    if len(content) > 300:
                        content = content[:300] + "..."
                    messages.append(content)
    except Exception:
        pass

    return messages


def gather_git_commits(since: datetime, until: datetime, author: str, scan_dirs: list[str]) -> list[dict]:
    """Gather git commits from specified directories and Claude-tracked projects."""
    git_repos = set()

    # Add scan directories
    for d in scan_dirs:
        p = Path(d).expanduser()
        if p.is_dir():
            find_git_repos(p, git_repos)

    # If no repos found, also scan common locations
    if not git_repos:
        for root in ["~/Project", "~/StudioProjects", "~/Code", "~/Dev", "~/src", "~"]:
            p = Path(root).expanduser()
            if p.is_dir():
                find_git_repos(p, git_repos)

    results = []
    for repo in sorted(git_repos):
        commits = get_commits_from_repo(repo, since, until, author)
        if commits:
            results.append({
                "repo": str(repo),
                "repoName": os.path.basename(repo),
                "commits": commits,
            })

    return results


def find_git_repos(root: Path, results: set[str], max_depth: int = 2):
    """Find git repos under root up to max_depth."""
    git_dir = root / ".git"
    if git_dir.exists():
        results.add(str(root.resolve()))
        return

    if max_depth <= 0:
        return

    try:
        for entry in root.iterdir():
            if entry.is_dir() and not entry.name.startswith(".") and not entry.name == "node_modules":
                find_git_repos(entry, results, max_depth - 1)
    except PermissionError:
        pass


def get_commits_from_repo(repo: str, since: datetime, until: datetime, author: str) -> list[dict]:
    """Get commits from a git repo within date range."""
    try:
        args = [
            "git", "-C", repo, "log",
            f"--since={since.isoformat()}",
            f"--until={until.isoformat()}",
            "--format=%H|%ai|%s",
        ]
        if author:
            args.append(f"--author={author}")

        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0][:8],
                    "date": parts[1],
                    "message": parts[2],
                })
        return commits
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="Gather work data for report generation")
    parser.add_argument("--since", default="today", help="Start date (today/yesterday/YYYY-MM-DD)")
    parser.add_argument("--until", default=None, help="End date (default: now)")
    parser.add_argument("--author", default=None, help="Git author filter (name or email). If not set, lists all commits.")
    parser.add_argument("--project-dirs", default=None, help="Comma-separated directories to scan for git repos")
    parser.add_argument("--no-git", action="store_true", help="Skip git data")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude session data")
    args = parser.parse_args()

    since = parse_date(args.since)
    until = parse_date(args.until) if args.until else datetime.now(LOCAL_TZ)
    scan_dirs = args.project_dirs.split(",") if args.project_dirs else []

    result = {
        "period": {
            "since": since.isoformat(),
            "until": until.isoformat(),
        },
        "claudeSessions": [],
        "gitCommits": [],
    }

    if not args.no_claude:
        result["claudeSessions"] = load_claude_sessions(since, until)

    if not args.no_git:
        # Use scan_dirs plus projects from claude sessions
        for s in result["claudeSessions"]:
            p = s.get("project")
            if p and Path(p).is_dir():
                scan_dirs.append(p)
        author = args.author
        result["gitCommits"] = gather_git_commits(since, until, author, scan_dirs)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timedelta, timezone
import json

from evoharness.config import load_config
from evoharness.events import append_event
from evoharness.workspace.git import git


def _repo(config_path: Path) -> Path:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve()


def _history(repo: Path) -> list[dict[str, Any]]:
    path = repo / ".evo" / "history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def list_worktrees(config_path: Path) -> list[dict[str, Any]]:
    rows = []
    for record in _history(_repo(config_path)):
        if "candidate" not in record:
            continue
        path = Path(str(record["candidate"]))
        rows.append(
            {
                "cycle": record.get("cycle"),
                "candidate_index": record.get("candidate_index", 1),
                "decision": record.get("decision"),
                "path": str(path),
                "exists": path.exists(),
                "dirty": bool(git(["status", "--porcelain"], cwd=path)) if path.exists() else False,
            }
        )
    return rows


def cleanup_worktrees(
    config_path: Path,
    rejected: bool = False,
    older_than_days: int = 0,
    include_accepted: bool = False,
    force: bool = False,
) -> list[dict[str, Any]]:
    if not rejected and older_than_days <= 0:
        raise ValueError("select cleanup scope with --rejected or --older-than-days")
    repo = _repo(config_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days) if older_than_days > 0 else None
    removed = []
    for record in _history(repo):
        decision = record.get("decision")
        if decision in {"accept", "keep"} and not include_accepted:
            continue
        if rejected and decision != "reject":
            continue
        path = Path(str(record.get("candidate", "")))
        if not path.exists():
            continue
        if cutoff and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > cutoff:
            continue
        dirty = bool(git(["status", "--porcelain"], cwd=path))
        if dirty and not force:
            continue
        args = ["worktree", "remove", str(path)]
        if force:
            args.insert(2, "--force")
        git(args, cwd=repo)
        item = {"cycle": record.get("cycle"), "candidate_index": record.get("candidate_index", 1), "path": str(path)}
        removed.append(item)
        append_event(repo, record.get("run_id", "worktree"), "worktree_removed", 0, 0, "", item)
    return removed

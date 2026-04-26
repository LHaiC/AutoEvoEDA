from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from evoharness.config import load_config
from evoharness.state import append_history
from evoharness.workspace.git import git


def _read_history(repo: Path) -> list[dict[str, Any]]:
    path = repo / ".evo" / "history.jsonl"
    if not path.exists():
        raise ValueError(f"history not found: {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _find_cycle_record(records: list[dict[str, Any]], cycle: int) -> dict[str, Any]:
    for record in reversed(records):
        if record.get("cycle") == cycle and record.get("decision") in {"accept", "keep", "reject"}:
            return record
    raise ValueError(f"cycle not found in history: {cycle}")


def promote_cycle(config_path: Path, cycle: int) -> None:
    cfg = load_config(config_path)
    repo = (config_path.parent / cfg.project.repo).resolve()
    record = _find_cycle_record(_read_history(repo), cycle)
    decision = record["decision"]
    if decision not in {"accept", "keep"}:
        raise ValueError(f"cycle {cycle} cannot be promoted from decision: {decision}")

    branch = record["branch"]
    git(["rev-parse", "--verify", branch], cwd=repo)
    git(["checkout", cfg.project.champion_branch], cwd=repo)
    git(["merge", "--ff-only", branch], cwd=repo)
    append_history(
        repo,
        {
            "event": "promote",
            "cycle": cycle,
            "branch": branch,
            "champion_branch": cfg.project.champion_branch,
            "decision": "promote",
            "reason": "explicit_promote",
        },
    )

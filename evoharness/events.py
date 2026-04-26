from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json


def run_id(cycle: int, candidate_index: int, pool_size: int) -> str:
    if pool_size == 1:
        return f"cycle-{cycle:03d}"
    return f"cycle-{cycle:03d}-cand-{candidate_index:03d}"


def run_dir(repo: Path, run_id_value: str) -> Path:
    return repo / ".evo" / "runs" / run_id_value


def append_event(
    repo: Path,
    run_id_value: str,
    event_type: str,
    cycle: int,
    candidate_index: int,
    branch: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "cycle": cycle,
        "candidate_index": candidate_index,
        "run_id": run_id_value,
        "branch": branch,
        "payload": payload,
    }
    for path in [repo / ".evo" / "events.jsonl", run_dir(repo, run_id_value) / "events.jsonl"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event

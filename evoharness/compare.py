from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from evoharness.config import load_config


def _repo(config_path: Path) -> Path:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve()


def _score(record: dict[str, Any]) -> float | None:
    reward = record.get("evaluator_results", {}).get("reward", {})
    value = reward.get("score") if isinstance(reward, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def compare_cycle(config_path: Path, cycle: int) -> Path:
    repo = _repo(config_path)
    history = repo / ".evo" / "history.jsonl"
    records = [json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    rows = [record for record in records if record.get("cycle") == cycle and "candidate" in record]
    scored = [(record, _score(record)) for record in rows]
    best = max((item for item in scored if item[1] is not None), key=lambda item: item[1], default=None)
    report = repo / ".evo" / "reports" / f"compare-cycle-{cycle:03d}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Candidate Comparison: cycle {cycle:03d}", "", "| Candidate | Decision | Reason | Score | Branch |", "| --- | --- | --- | --- | --- |"]
    for record, score in scored:
        lines.append(
            f"| {record.get('candidate_index', 1)} | {record.get('decision')} | {record.get('reason')} | "
            f"{'' if score is None else score} | `{record.get('branch')}` |"
        )
    if best:
        lines.extend(["", f"Recommended candidate: `{best[0].get('candidate_index', 1)}` with score `{best[1]}`."])
    report.write_text("\n".join(lines) + "\n")
    return report

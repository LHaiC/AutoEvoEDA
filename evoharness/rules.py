from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json

from evoharness.config import load_config
from evoharness.events import append_event


def _repo(config_path: Path) -> tuple[Path, Any]:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve(), cfg


def _history(repo: Path) -> list[dict[str, Any]]:
    path = repo / ".evo" / "history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _proposal_dir(repo: Path) -> Path:
    path = repo / ".evo" / "rules" / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_rule_proposals(config_path: Path) -> list[str]:
    repo, _cfg = _repo(config_path)
    return [path.stem for path in sorted(_proposal_dir(repo).glob("*.md"))]


def propose_rules(config_path: Path) -> Path:
    repo, _cfg = _repo(config_path)
    records = _history(repo)[-10:]
    proposal_id = datetime.now(timezone.utc).strftime("rule-%Y%m%d-%H%M%S")
    path = _proposal_dir(repo) / f"{proposal_id}.md"
    lines = [
        f"# Rule Proposal: {proposal_id}",
        "",
        "## Candidate Rule Updates",
        "",
        "- Keep evaluator scripts, benchmark data, and reward logic outside candidate edit scope.",
        "- Prefer small reversible patches tied to one measured hypothesis.",
        "",
        "## Recent Evidence",
        "",
    ]
    lines.extend(f"- cycle {r.get('cycle')}: {r.get('decision')} / {r.get('reason')}" for r in records)
    lines.extend(["", "## Human Decision", "", "Accept this proposal with `evo rules accept` or reject it with a comment."])
    path.write_text("\n".join(lines) + "\n")
    append_event(repo, "rules", "rule_proposed", 0, 0, "", {"proposal": proposal_id})
    return path


def accept_rule(config_path: Path, proposal_id: str) -> Path:
    repo, cfg = _repo(config_path)
    proposal = _proposal_dir(repo) / f"{proposal_id}.md"
    if not proposal.exists():
        raise ValueError(f"rule proposal not found: {proposal_id}")
    rulebase = repo / cfg.rulebase.path
    rulebase.parent.mkdir(parents=True, exist_ok=True)
    existing = rulebase.read_text() if rulebase.exists() else "# Rulebase\n"
    rulebase.write_text(existing.rstrip() + "\n\n" + proposal.read_text().rstrip() + "\n")
    append_event(repo, "rules", "rule_accepted", 0, 0, "", {"proposal": proposal_id})
    return rulebase


def reject_rule(config_path: Path, proposal_id: str, comment: str) -> Path:
    repo, _cfg = _repo(config_path)
    path = repo / ".evo" / "rules" / "rejections.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(), "proposal": proposal_id, "comment": comment}
    with path.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_event(repo, "rules", "rule_rejected", 0, 0, "", record)
    return path

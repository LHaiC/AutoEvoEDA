from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def _cycle_dir_name(record: dict[str, Any]) -> str:
    branch = str(record["branch"])
    if branch.startswith("evo/"):
        return branch.removeprefix("evo/")
    cycle = int(record["cycle"])
    return f"cycle-{cycle:03d}"


def write_cycle_summary(repo: Path, record: dict[str, Any]) -> Path:
    cycle_dir_name = _cycle_dir_name(record)
    cycle_dir = repo / ".evo" / cycle_dir_name
    cycle_dir.mkdir(parents=True, exist_ok=True)
    evaluator_results = record.get("evaluator_results", {})
    has_results = isinstance(evaluator_results, dict) and bool(evaluator_results)
    result_keys = ", ".join(sorted(evaluator_results)) if has_results else "none"
    path = cycle_dir / "summary.md"
    path.write_text(
        "\n".join(
            [
                f"# {cycle_dir_name} Summary",
                "",
                f"- Branch: `{record['branch']}`",
                f"- Candidate: `{record['candidate']}`",
                f"- Decision: `{record['decision']}`",
                f"- Reason: `{record['reason']}`",
                f"- Changed files: {record['changed_files']}",
                f"- Changed lines: {record['changed_lines']}",
                f"- Evaluator results: {result_keys}",
                "",
                "## Artifacts",
                "",
                f"- Codex stdout: `.evo/{cycle_dir_name}/codex.stdout`",
                f"- Codex stderr: `.evo/{cycle_dir_name}/codex.stderr`",
                f"- Guard result: `.evo/{cycle_dir_name}/guard.json`",
                f"- Build stdout: `.evo/{cycle_dir_name}/build.stdout`",
                f"- Regression stdout: `.evo/{cycle_dir_name}/regression.stdout`",
                f"- Performance stdout: `.evo/{cycle_dir_name}/perf.stdout`",
                f"- Reward stdout: `.evo/{cycle_dir_name}/reward.stdout`",
                f"- Evaluator results: `.evo/runs/{cycle_dir_name}/evaluator_results.json`",
                "",
            ]
        )
    )
    return path


def _history(repo: Path) -> list[dict[str, Any]]:
    path = repo / ".evo" / "history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_project_indexes(repo: Path) -> None:
    evo_dir = repo / ".evo"
    evo_dir.mkdir(parents=True, exist_ok=True)
    records = _history(repo)
    candidate_records = [r for r in records if "branch" in r and r.get("event") != "promote"]
    lines = ["# evo-harness Index", "", "## Recent Candidates", ""]
    for record in candidate_records[-20:]:
        run_id = record.get("run_id", _cycle_dir_name(record))
        lines.append(f"- `{run_id}`: `{record['decision']}` / `{record['reason']}` on `{record['branch']}`")
    lines.append("")
    lines.extend(["## Files", "", "- `history.jsonl`", "- `events.jsonl`", "- `runs/`", "- `session/`", "- `memory/`", ""])
    (evo_dir / "index.md").write_text("\n".join(lines))

    roadmap = evo_dir / "roadmap.md"
    if not roadmap.exists():
        roadmap.write_text(
            "\n".join(
                [
                    "# Evolution Roadmap",
                    "",
                    "## Current Focus",
                    "",
                    "Use `evo session comment` to add steering notes for the next run.",
                    "",
                    "## Active Hypotheses",
                    "",
                    "- Keep candidate patches small and evaluator-driven.",
                    "",
                    "## Rejected Directions",
                    "",
                    "- Weakening guards, scripts, benchmarks, or correctness checks.",
                    "",
                ]
            )
        )

    runs_dir = evo_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs_lines = ["# Runs", ""]
    for run_path in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        runs_lines.append(f"- `{run_path.name}/`")
    runs_lines.append("")
    (runs_dir / "README.md").write_text("\n".join(runs_lines))

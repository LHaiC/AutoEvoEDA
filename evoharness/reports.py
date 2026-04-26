from __future__ import annotations

from pathlib import Path
from typing import Any


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
                "",
            ]
        )
    )
    return path

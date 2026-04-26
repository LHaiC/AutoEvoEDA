from __future__ import annotations

from pathlib import Path
from typing import Any


def write_cycle_summary(repo: Path, record: dict[str, Any]) -> Path:
    cycle = int(record["cycle"])
    cycle_dir = repo / ".evo" / f"cycle-{cycle:03d}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    path = cycle_dir / "summary.md"
    path.write_text(
        "\n".join(
            [
                f"# Cycle {cycle:03d} Summary",
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
                f"- Codex stdout: `.evo/cycle-{cycle:03d}/codex.stdout`",
                f"- Codex stderr: `.evo/cycle-{cycle:03d}/codex.stderr`",
                f"- Guard result: `.evo/cycle-{cycle:03d}/guard.json`",
                f"- Build stdout: `.evo/cycle-{cycle:03d}/build.stdout`",
                f"- Regression stdout: `.evo/cycle-{cycle:03d}/regression.stdout`",
                f"- Performance stdout: `.evo/cycle-{cycle:03d}/perf.stdout`",
                f"- Reward stdout: `.evo/cycle-{cycle:03d}/reward.stdout`",
                "",
            ]
        )
    )
    return path

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class Candidate:
    cycle: int
    branch: str
    path: Path


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    return proc.stdout.strip()


def create_candidate_worktree(
    repo: Path,
    champion_branch: str,
    worktree_root: Path,
    project_name: str,
    cycle: int,
) -> Candidate:
    branch = f"evo/cycle-{cycle:03d}"
    path = worktree_root / f"{project_name}-cycle-{cycle:03d}"
    worktree_root.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "-B", branch, str(path), champion_branch], cwd=repo)
    return Candidate(cycle=cycle, branch=branch, path=path)


def changed_files(repo: Path) -> list[str]:
    out = git(["diff", "--name-only"], cwd=repo)
    return out.splitlines() if out else []


def changed_line_count(repo: Path) -> int:
    out = git(["diff", "--numstat"], cwd=repo)
    total = 0
    for line in out.splitlines():
        added, deleted, _path = line.split("\t", 2)
        if added != "-":
            total += int(added)
        if deleted != "-":
            total += int(deleted)
    return total

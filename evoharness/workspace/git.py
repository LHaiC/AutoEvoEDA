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


def _untracked_files(repo: Path) -> list[str]:
    out = git(["ls-files", "--others", "--exclude-standard"], cwd=repo)
    return out.splitlines() if out else []


def changed_files(repo: Path) -> list[str]:
    tracked = git(["diff", "--name-only"], cwd=repo).splitlines()
    return sorted({*tracked, *_untracked_files(repo)})


def changed_line_count(repo: Path) -> int:
    out = git(["diff", "--numstat"], cwd=repo)
    total = 0
    for line in out.splitlines():
        added, deleted, _path = line.split("\t", 2)
        if added != "-":
            total += int(added)
        if deleted != "-":
            total += int(deleted)
    for path in _untracked_files(repo):
        file_path = repo / path
        if file_path.is_file():
            total += len(file_path.read_bytes().splitlines())
    return total


def has_uncommitted_changes(repo: Path) -> bool:
    return bool(git(["status", "--porcelain"], cwd=repo))


def commit_candidate(repo: Path, cycle: int) -> None:
    if has_uncommitted_changes(repo):
        git(["add", "-A"], cwd=repo)
        git(["commit", "-m", f"evo: candidate cycle {cycle:03d}"], cwd=repo)

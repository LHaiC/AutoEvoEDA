from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess

from autoevoeda.config import WorkspaceConfig


@dataclass(frozen=True)
class RepoWorktree:
    name: str
    source: Path
    path: Path
    branch: str
    champion_branch: str


@dataclass(frozen=True)
class Candidate:
    cycle: int
    branch: str
    path: Path
    index: int = 1
    repos: tuple[RepoWorktree, ...] = field(default_factory=tuple)


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


def _suffix(cycle: int, candidate_index: int, pool_size: int) -> str:
    return f"cycle-{cycle:03d}" if pool_size == 1 else f"cycle-{cycle:03d}-cand-{candidate_index:03d}"


def create_candidate_worktree(
    repo: Path,
    champion_branch: str,
    worktree_root: Path,
    project_name: str,
    cycle: int,
    candidate_index: int = 1,
    pool_size: int = 1,
) -> Candidate:
    suffix = _suffix(cycle, candidate_index, pool_size)
    branch = f"evo/{suffix}"
    path = worktree_root / f"{project_name}-{suffix}"
    worktree_root.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "-B", branch, str(path), champion_branch], cwd=repo)
    return Candidate(cycle=cycle, branch=branch, path=path, index=candidate_index)


def create_candidate_workspace(
    adapter_repo: Path,
    cfg_workspace: WorkspaceConfig,
    project_name: str,
    cycle: int,
    candidate_index: int = 1,
    pool_size: int = 1,
) -> Candidate:
    suffix = _suffix(cycle, candidate_index, pool_size)
    worktree_root = Path(cfg_workspace.worktree_root)
    if not worktree_root.is_absolute():
        worktree_root = adapter_repo / worktree_root
    path = worktree_root.resolve() / f"{project_name}-{suffix}"
    path.mkdir(parents=True, exist_ok=True)
    source_root = Path(cfg_workspace.source_root)
    if not source_root.is_absolute():
        source_root = adapter_repo / source_root
    source_root = source_root.resolve()
    repos = []
    for repo_cfg in cfg_workspace.repos:
        branch = f"{repo_cfg.candidate_branch_prefix}/{suffix}/{repo_cfg.name}"
        source = source_root / repo_cfg.path
        target = path / repo_cfg.name
        git(["worktree", "add", "-B", branch, str(target), repo_cfg.champion_branch], cwd=source)
        repos.append(RepoWorktree(repo_cfg.name, source, target, branch, repo_cfg.champion_branch))
    for rel in cfg_workspace.materialize.copy:
        _copy(source_root / rel, path / rel)
    for rel in cfg_workspace.materialize.symlink:
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).symlink_to(source_root / rel, target_is_directory=(source_root / rel).is_dir())
    return Candidate(cycle=cycle, branch=f"multi/{suffix}", path=path, index=candidate_index, repos=tuple(repos))


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _untracked_files(repo: Path) -> list[str]:
    out = git(["ls-files", "--others", "--exclude-standard"], cwd=repo)
    return out.splitlines() if out else []


def changed_files(repo: Path) -> list[str]:
    tracked = git(["diff", "--name-only"], cwd=repo).splitlines()
    return sorted({*tracked, *_untracked_files(repo)})


def _worktree_diff(repo: Path, files: list[str] | None = None) -> str:
    if files is not None and not files:
        return ""
    args = ["diff"]
    if files is not None:
        args.extend(["--", *files])
    parts = [git(args, cwd=repo)]
    selected = set(files) if files is not None else None
    for file in _untracked_files(repo):
        if selected is not None and file not in selected:
            continue
        if (repo / file).is_file():
            parts.append(git(["diff", "--no-index", "--", "/dev/null", file], cwd=repo, check=False))
    return "\n".join(part for part in parts if part)


def candidate_diff(candidate: Candidate) -> str:
    if not candidate.repos:
        return _worktree_diff(candidate.path)
    parts = []
    for repo in candidate.repos:
        files = changed_files(repo.path)
        diff = _worktree_diff(repo.path, files)
        if diff:
            parts.extend([f"# repo: {repo.name}", diff])
    return "\n".join(parts)


def candidate_changed_files(candidate: Candidate) -> list[str]:
    if not candidate.repos:
        return changed_files(candidate.path)
    rows = []
    for repo in candidate.repos:
        rows.extend(f"{repo.name}/{path}" for path in changed_files(repo.path))
    return rows


def changed_line_count(repo: Path, files: list[str] | None = None) -> int:
    args = ["diff", "--numstat"]
    if files is not None:
        if not files:
            return 0
        args.extend(["--", *files])
    out = git(args, cwd=repo)
    total = 0
    for line in out.splitlines():
        added, deleted, _path = line.split("\t", 2)
        if added != "-":
            total += int(added)
        if deleted != "-":
            total += int(deleted)
    untracked = _untracked_files(repo)
    if files is not None:
        allowed = set(files)
        untracked = [path for path in untracked if path in allowed]
    for path in untracked:
        file_path = repo / path
        if file_path.is_file():
            total += len(file_path.read_bytes().splitlines())
    return total


def has_uncommitted_changes(repo: Path) -> bool:
    return bool(git(["status", "--porcelain"], cwd=repo))


def commit_repo(repo: Path, message: str, files: list[str] | None = None) -> None:
    if has_uncommitted_changes(repo):
        if files is None:
            git(["add", "-A"], cwd=repo)
        elif files:
            git(["add", "--", *files], cwd=repo)
        else:
            return
        git(["commit", "-m", message], cwd=repo)


def commit_candidate(candidate: Candidate, cycle: int) -> None:
    message = f"evo: candidate cycle {cycle:03d}"
    if candidate.repos:
        for repo in candidate.repos:
            commit_repo(repo.path, message, changed_files(repo.path))
    else:
        commit_repo(candidate.path, message)

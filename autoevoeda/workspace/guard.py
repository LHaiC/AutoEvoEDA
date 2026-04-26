from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoevoeda.config import WorkspaceConfig
from autoevoeda.workspace.git import Candidate, changed_files, changed_line_count, git


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str
    changed_files: int
    changed_lines: int


def _matches_prefix(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def _check_files(files: list[str], allowed_paths: list[str], forbidden_paths: list[str]) -> str:
    for file in files:
        if _matches_prefix(file, forbidden_paths):
            return f"forbidden_path:{file}"
        if not _matches_prefix(file, allowed_paths):
            return f"path_not_allowed:{file}"
    return "ok"


def _check_diff(repo: Path) -> str:
    diff = git(["diff"], cwd=repo)
    for token in ["skip", "bypass", "return true", "NDEBUG", "benchmark ==", "design_name =="]:
        if token in diff:
            return f"suspicious_pattern:{token}"
    return "ok"


def check_patch_scope(
    repo: Path,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    max_changed_files: int,
    max_changed_lines: int,
) -> GuardResult:
    files = changed_files(repo)
    lines = changed_line_count(repo)
    return _finish_guard(repo, files, lines, allowed_paths, forbidden_paths, max_changed_files, max_changed_lines)


def check_candidate_scope(
    candidate: Candidate,
    workspace: WorkspaceConfig,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    max_changed_files: int,
    max_changed_lines: int,
) -> GuardResult:
    if not candidate.repos:
        return check_patch_scope(candidate.path, allowed_paths, forbidden_paths, max_changed_files, max_changed_lines)
    files: list[str] = []
    lines = 0
    for repo_cfg, repo in zip(workspace.repos, candidate.repos, strict=True):
        repo_files = changed_files(repo.path)
        reason = _check_files(repo_files, repo_cfg.allowed_paths, [*forbidden_paths, *repo_cfg.forbidden_paths])
        if reason != "ok":
            return GuardResult(False, f"{repo.name}:{reason}", len(files) + len(repo_files), lines)
        diff_reason = _check_diff(repo.path)
        if diff_reason != "ok":
            return GuardResult(False, f"{repo.name}:{diff_reason}", len(files) + len(repo_files), lines)
        files.extend(f"{repo.name}/{file}" for file in repo_files)
        lines += changed_line_count(repo.path)
    reason = _check_files(files, allowed_paths, []) if allowed_paths else "ok"
    if reason != "ok":
        return GuardResult(False, reason, len(files), lines)
    if len(files) > max_changed_files:
        return GuardResult(False, "too_many_changed_files", len(files), lines)
    if lines > max_changed_lines:
        return GuardResult(False, "too_many_changed_lines", len(files), lines)
    return GuardResult(True, "ok", len(files), lines)


def _finish_guard(
    repo: Path,
    files: list[str],
    lines: int,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    max_changed_files: int,
    max_changed_lines: int,
) -> GuardResult:
    if len(files) > max_changed_files:
        return GuardResult(False, "too_many_changed_files", len(files), lines)
    if lines > max_changed_lines:
        return GuardResult(False, "too_many_changed_lines", len(files), lines)
    reason = _check_files(files, allowed_paths, forbidden_paths)
    if reason != "ok":
        return GuardResult(False, reason, len(files), lines)
    diff_reason = _check_diff(repo)
    if diff_reason != "ok":
        return GuardResult(False, diff_reason, len(files), lines)
    return GuardResult(True, "ok", len(files), lines)

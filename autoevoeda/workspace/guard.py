from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from autoevoeda.config import WorkspaceConfig
from autoevoeda.workspace.git import Candidate, changed_files, changed_line_count, git

SUSPICIOUS_PATTERNS = [
    ("skip", re.compile(rb"\b(skip_(correctness|regression|validation|check|checks|test|tests|perf)|--skip)\b")),
    ("bypass", re.compile(rb"\bbypass\b")),
    ("return true", re.compile(rb"\breturn\s+true\b")),
    ("NDEBUG", re.compile(rb"\bNDEBUG\b")),
    ("benchmark ==", re.compile(rb"\bbenchmark\s*==")),
    ("design_name ==", re.compile(rb"\bdesign_name\s*==")),
]


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


def _check_diff(repo: Path, files: list[str] | None = None) -> str:
    args = ["diff", "--unified=0"]
    if files is not None:
        if not files:
            return "ok"
        args.extend(["--", *files])
    diff = git(args, cwd=repo).encode()
    for line in diff.splitlines():
        if not line.startswith(b"+") or line.startswith(b"+++"):
            continue
        for label, pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(line[1:]):
                return f"suspicious_pattern:{label}"
    tracked = set(git(["ls-files"], cwd=repo).splitlines())
    for file in files or []:
        if file in tracked:
            continue
        path = repo / file
        if path.is_file():
            for line in path.read_bytes().splitlines():
                for label, pattern in SUSPICIOUS_PATTERNS:
                    if pattern.search(line):
                        return f"suspicious_pattern:{label}"
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
        lines += changed_line_count(repo.path, repo_files)
        diff_reason = _check_diff(repo.path, repo_files)
        if diff_reason != "ok":
            return GuardResult(False, f"{repo.name}:{diff_reason}", len(files) + len(repo_files), lines)
        files.extend(f"{repo.name}/{file}" for file in repo_files)
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
    diff_reason = _check_diff(repo, files)
    if diff_reason != "ok":
        return GuardResult(False, diff_reason, len(files), lines)
    return GuardResult(True, "ok", len(files), lines)

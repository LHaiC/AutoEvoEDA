from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoevoeda.workspace.git import changed_files, changed_line_count, git


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str
    changed_files: int
    changed_lines: int


def _matches_prefix(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def check_patch_scope(
    repo: Path,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    max_changed_files: int,
    max_changed_lines: int,
) -> GuardResult:
    files = changed_files(repo)
    lines = changed_line_count(repo)

    if len(files) > max_changed_files:
        return GuardResult(False, "too_many_changed_files", len(files), lines)
    if lines > max_changed_lines:
        return GuardResult(False, "too_many_changed_lines", len(files), lines)

    for file in files:
        if _matches_prefix(file, forbidden_paths):
            return GuardResult(False, f"forbidden_path:{file}", len(files), lines)
        if not _matches_prefix(file, allowed_paths):
            return GuardResult(False, f"path_not_allowed:{file}", len(files), lines)

    diff = git(["diff"], cwd=repo)
    for token in ["skip", "bypass", "return true", "NDEBUG", "benchmark ==", "design_name =="]:
        if token in diff:
            return GuardResult(False, f"suspicious_pattern:{token}", len(files), lines)

    return GuardResult(True, "ok", len(files), lines)

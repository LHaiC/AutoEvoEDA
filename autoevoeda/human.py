from __future__ import annotations

from dataclasses import dataclass

from autoevoeda.workspace.git import Candidate
from autoevoeda.workspace.guard import GuardResult


@dataclass(frozen=True)
class HumanDecision:
    decision: str
    reason: str
    comment: str
    next_hint: str


def _read_optional(label: str) -> str:
    print(label)
    return input("> ").strip()


def review_candidate(candidate: Candidate, guard: GuardResult) -> HumanDecision:
    print("Candidate passed all gates.")
    print(f"Cycle: {candidate.cycle}")
    print(f"Branch: {candidate.branch}")
    print(f"Worktree: {candidate.path}")
    print(f"Changed files: {guard.changed_files}")
    print(f"Changed lines: {guard.changed_lines}")
    print("Decision: [a] accept, [r] reject, [k] keep, [d] redirect, [p] pause")
    answer = input("> ").strip().lower()
    choices = {
        "a": ("accept", "human_accepted_all_gates_passed"),
        "r": ("reject", "human_rejected"),
        "k": ("keep", "human_kept_for_later"),
        "d": ("redirect", "human_redirected"),
        "p": ("pause", "human_paused"),
    }
    if answer not in choices:
        raise ValueError(f"invalid human review decision: {answer}")
    decision, reason = choices[answer]
    comment = _read_optional("Optional comment, empty to skip:")
    next_hint = _read_optional("Optional next hint, empty to skip:")
    return HumanDecision(decision, reason, comment, next_hint)

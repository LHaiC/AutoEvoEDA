from __future__ import annotations

from dataclasses import dataclass

from evoharness.workspace.git import Candidate
from evoharness.workspace.guard import GuardResult


@dataclass(frozen=True)
class HumanDecision:
    decision: str
    reason: str


def review_candidate(candidate: Candidate, guard: GuardResult) -> HumanDecision:
    print("Candidate passed all gates.")
    print(f"Cycle: {candidate.cycle}")
    print(f"Branch: {candidate.branch}")
    print(f"Worktree: {candidate.path}")
    print(f"Changed files: {guard.changed_files}")
    print(f"Changed lines: {guard.changed_lines}")
    print("Decision: [a] accept, [r] reject, [k] keep for later")
    answer = input("> ").strip().lower()
    if answer == "a":
        return HumanDecision("accept", "human_accepted_all_gates_passed")
    if answer == "r":
        return HumanDecision("reject", "human_rejected")
    if answer == "k":
        return HumanDecision("keep", "human_kept_for_later")
    raise ValueError(f"invalid human review decision: {answer}")

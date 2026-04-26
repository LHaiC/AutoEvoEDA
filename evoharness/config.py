from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    repo: str
    champion_branch: str


@dataclass(frozen=True)
class AgentConfig:
    prompt_file: str
    timeout_s: int
    sandbox: str


@dataclass(frozen=True)
class WorkspaceConfig:
    worktree_root: str


@dataclass(frozen=True)
class GuardConfig:
    max_changed_files: int
    max_changed_lines: int
    allowed_paths: list[str]
    forbidden_paths: list[str]


@dataclass(frozen=True)
class PipelineConfig:
    build: str
    regression: str
    compare_regression: str
    perf: str
    reward: str


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool
    project_memory: str
    lessons: str
    rejected_ideas: str
    accepted_patterns: str
    inject_recent_cycles: int


@dataclass(frozen=True)
class HumanConfig:
    review_on_accept: bool
    stop_after_consecutive_rejects: int


@dataclass(frozen=True)
class RepairConfig:
    enabled: bool
    max_attempts: int
    prompt_file: str


@dataclass(frozen=True)
class RolesConfig:
    planner_prompt: str
    coder_prompt: str
    reviewer_prompt: str


@dataclass(frozen=True)
class RulebaseConfig:
    path: str


@dataclass(frozen=True)
class PoolConfig:
    enabled: bool
    size: int


@dataclass(frozen=True)
class BudgetConfig:
    max_cycles: int
    max_candidates: int


@dataclass(frozen=True)
class EvoConfig:
    project: ProjectConfig
    agent: AgentConfig
    workspace: WorkspaceConfig
    guards: GuardConfig
    pipeline: PipelineConfig
    memory: MemoryConfig
    human: HumanConfig
    repair: RepairConfig
    roles: RolesConfig
    rulebase: RulebaseConfig
    pool: PoolConfig
    budget: BudgetConfig


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"missing config section: {name}")
    return value


def _optional_section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"config section must be a mapping: {name}")
    return value


def load_config(path: Path) -> EvoConfig:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")

    agent = {"timeout_s": 3600, "sandbox": "workspace-write", **_section(data, "agent")}
    memory = {
        "enabled": False,
        "project_memory": ".evo/memory/project.md",
        "lessons": ".evo/memory/lessons.jsonl",
        "rejected_ideas": ".evo/memory/rejected_ideas.jsonl",
        "accepted_patterns": ".evo/memory/accepted_patterns.md",
        "inject_recent_cycles": 5,
        **_optional_section(data, "memory"),
    }
    human = {"review_on_accept": False, "stop_after_consecutive_rejects": 0, **_optional_section(data, "human")}
    repair = {"enabled": False, "max_attempts": 1, "prompt_file": "prompts/repair.md", **_optional_section(data, "repair")}
    roles = {"planner_prompt": "", "coder_prompt": "", "reviewer_prompt": "", **_optional_section(data, "roles")}
    rulebase = {"path": ".evo/memory/rulebase.md", **_optional_section(data, "rulebase")}
    pool = {"enabled": False, "size": 1, **_optional_section(data, "pool")}
    budget = {"max_cycles": 0, "max_candidates": 0, **_optional_section(data, "budget")}

    return EvoConfig(
        project=ProjectConfig(**_section(data, "project")),
        agent=AgentConfig(**agent),
        workspace=WorkspaceConfig(**_section(data, "workspace")),
        guards=GuardConfig(**_section(data, "guards")),
        pipeline=PipelineConfig(**_section(data, "pipeline")),
        memory=MemoryConfig(**memory),
        human=HumanConfig(**human),
        repair=RepairConfig(**repair),
        roles=RolesConfig(**roles),
        rulebase=RulebaseConfig(**rulebase),
        pool=PoolConfig(**pool),
        budget=BudgetConfig(**budget),
    )

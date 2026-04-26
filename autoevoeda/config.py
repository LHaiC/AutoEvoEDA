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
class WorkspaceRepoConfig:
    name: str
    path: str
    champion_branch: str
    candidate_branch_prefix: str
    allowed_paths: list[str]
    forbidden_paths: list[str]


@dataclass(frozen=True)
class WorkspaceMaterializeConfig:
    copy: list[str]
    symlink: list[str]


@dataclass(frozen=True)
class WorkspaceConfig:
    worktree_root: str
    mode: str
    source_root: str
    repos: list[WorkspaceRepoConfig]
    materialize: WorkspaceMaterializeConfig


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
class ResultFilesConfig:
    correctness: str
    qor: str
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
class CodexSessionConfig:
    enabled: bool
    session_file: str


@dataclass(frozen=True)
class AgentRoleConfig:
    session_id: str
    codex_session: CodexSessionConfig


@dataclass(frozen=True)
class DomainAgentConfig:
    name: str
    session_id: str
    prompt_file: str
    allowed_paths: list[str]
    forbidden_paths: list[str]
    codex_session: CodexSessionConfig


@dataclass(frozen=True)
class AgentsConfig:
    planner: AgentRoleConfig
    coder: AgentRoleConfig
    reviewer: AgentRoleConfig
    repair: AgentRoleConfig
    rulebase: AgentRoleConfig
    code_understanding: AgentRoleConfig


@dataclass(frozen=True)
class MultiAgentConfig:
    planner: bool
    reviewer: bool


@dataclass(frozen=True)
class PoolConfig:
    enabled: bool
    size: int


@dataclass(frozen=True)
class BudgetConfig:
    max_cycles: int
    max_candidates: int


@dataclass(frozen=True)
class PromotionConfig:
    require_clean_champion: bool


@dataclass(frozen=True)
class EvoConfig:
    schema_version: str
    project: ProjectConfig
    agent: AgentConfig
    workspace: WorkspaceConfig
    guards: GuardConfig
    pipeline: PipelineConfig
    result_files: ResultFilesConfig
    memory: MemoryConfig
    human: HumanConfig
    repair: RepairConfig
    roles: RolesConfig
    rulebase: RulebaseConfig
    pool: PoolConfig
    budget: BudgetConfig
    agents: AgentsConfig
    domain_agents: list[DomainAgentConfig]
    multi_agent: MultiAgentConfig
    promotion: PromotionConfig


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


def _agent_role(data: dict[str, Any], name: str, default_session_id: str) -> AgentRoleConfig:
    raw = data.get(name, {})
    if not isinstance(raw, dict):
        raise ValueError(f"agent role must be a mapping: {name}")
    session_id = raw.get("session_id", default_session_id)
    codex_data = raw.get("codex_session", {})
    if not isinstance(codex_data, dict):
        raise ValueError(f"codex_session must be a mapping: agents.{name}")
    codex_session = {
        "enabled": False,
        "session_file": f".evo/agents/{session_id}/codex_session.txt",
        **codex_data,
    }
    role = {key: value for key, value in raw.items() if key not in {"session_id", "codex_session"}}
    return AgentRoleConfig(**role, session_id=session_id, codex_session=CodexSessionConfig(**codex_session))


def _domain_agents(data: dict[str, Any]) -> list[DomainAgentConfig]:
    raw = data.get("domain_agents", [])
    if not isinstance(raw, list):
        raise ValueError("domain_agents must be a list")
    agents = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("domain_agents entries must be mappings")
        name = str(item["name"])
        session_id = str(item.get("session_id", f"{name}-main"))
        codex_data = item.get("codex_session", {})
        if not isinstance(codex_data, dict):
            raise ValueError(f"codex_session must be a mapping: domain_agents.{name}")
        if not isinstance(item["allowed_paths"], list):
            raise ValueError(f"allowed_paths must be a list: domain_agents.{name}")
        forbidden_paths = item.get("forbidden_paths", [])
        if not isinstance(forbidden_paths, list):
            raise ValueError(f"forbidden_paths must be a list: domain_agents.{name}")
        agents.append(
            DomainAgentConfig(
                name=name,
                session_id=session_id,
                prompt_file=str(item["prompt_file"]),
                allowed_paths=list(item["allowed_paths"]),
                forbidden_paths=list(forbidden_paths),
                codex_session=CodexSessionConfig(
                    enabled=bool(codex_data.get("enabled", False)),
                    session_file=str(codex_data.get("session_file", f".evo/agents/{session_id}/codex_session.txt")),
                ),
            )
        )
    if len({agent.name for agent in agents}) != len(agents):
        raise ValueError("domain_agents names must be unique")
    return agents


def _workspace(data: dict[str, Any], project: dict[str, Any]) -> WorkspaceConfig:
    raw = {"mode": "single_repo", "source_root": "", "repos": [], "materialize": {}, **_section(data, "workspace")}
    materialize = raw.pop("materialize")
    repos = raw.pop("repos")
    if raw["mode"] not in {"single_repo", "multi_repo"}:
        raise ValueError("workspace.mode must be single_repo or multi_repo")
    if not isinstance(materialize, dict):
        raise ValueError("workspace.materialize must be a mapping")
    if not isinstance(repos, list):
        raise ValueError("workspace.repos must be a list")
    workspace_repos = []
    for item in repos:
        if not isinstance(item, dict):
            raise ValueError("workspace.repos entries must be mappings")
        name = str(item["name"])
        workspace_repos.append(
            WorkspaceRepoConfig(
                name=name,
                path=str(item.get("path", name)),
                champion_branch=str(item.get("champion_branch", project.get("champion_branch", ""))),
                candidate_branch_prefix=str(item.get("candidate_branch_prefix", "evo")),
                allowed_paths=list(item["allowed_paths"]),
                forbidden_paths=list(item.get("forbidden_paths", [])),
            )
        )
    if raw["mode"] == "multi_repo" and not workspace_repos:
        raise ValueError("workspace.repos is required when workspace.mode is multi_repo")
    return WorkspaceConfig(
        **raw,
        repos=workspace_repos,
        materialize=WorkspaceMaterializeConfig(
            copy=list(materialize.get("copy", [])),
            symlink=list(materialize.get("symlink", [])),
        ),
    )


def load_config(path: Path) -> EvoConfig:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")

    project = {"champion_branch": "", **_section(data, "project")}
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
    multi_agent = {"planner": False, "reviewer": False, **_optional_section(data, "multi_agent")}
    promotion = {"require_clean_champion": True, **_optional_section(data, "promotion")}
    result_files = {
        "correctness": "results/correctness.json",
        "qor": "results/qor.json",
        "perf": "results/perf.json",
        "reward": "results/reward.json",
        **_optional_section(data, "result_files"),
    }
    agents_data = _optional_section(data, "agents")
    domain_agents = _domain_agents(data)
    workspace = _workspace(data, project)
    if workspace.mode == "single_repo" and not project["champion_branch"]:
        raise ValueError("project.champion_branch is required when workspace.mode is single_repo")
    if domain_agents and (not multi_agent["planner"] or not roles["planner_prompt"]):
        raise ValueError("domain_agents require multi_agent.planner and roles.planner_prompt")

    return EvoConfig(
        schema_version=str(data.get("schema_version", "1.0")),
        project=ProjectConfig(**project),
        agent=AgentConfig(**agent),
        workspace=workspace,
        guards=GuardConfig(**_section(data, "guards")),
        pipeline=PipelineConfig(**_section(data, "pipeline")),
        result_files=ResultFilesConfig(**result_files),
        memory=MemoryConfig(**memory),
        human=HumanConfig(**human),
        repair=RepairConfig(**repair),
        roles=RolesConfig(**roles),
        rulebase=RulebaseConfig(**rulebase),
        pool=PoolConfig(**pool),
        budget=BudgetConfig(**budget),
        agents=AgentsConfig(
            planner=_agent_role(agents_data, "planner", "planner-main"),
            coder=_agent_role(agents_data, "coder", "coder-main"),
            reviewer=_agent_role(agents_data, "reviewer", "reviewer-main"),
            repair=_agent_role(agents_data, "repair", "repair-main"),
            rulebase=_agent_role(agents_data, "rulebase", "rulebase-main"),
            code_understanding=_agent_role(agents_data, "code_understanding", "understand-main"),
        ),
        domain_agents=domain_agents,
        multi_agent=MultiAgentConfig(**multi_agent),
        promotion=PromotionConfig(**promotion),
    )

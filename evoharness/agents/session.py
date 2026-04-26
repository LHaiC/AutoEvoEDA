from __future__ import annotations

from pathlib import Path

from evoharness.agent_state import (
    read_codex_session,
    write_codex_session,
    write_codex_session_event,
)
from evoharness.agents.codex import AgentResult, CodexBackend
from evoharness.config import AgentRoleConfig


def run_codex_role(
    repo: Path,
    role: AgentRoleConfig,
    agent: CodexBackend,
    prompt: str,
    cwd: Path,
    timeout_s: int,
) -> AgentResult:
    cfg = role.codex_session
    session_id = read_codex_session(repo, role.session_id, cfg.session_file) if cfg.enabled else ""
    if cfg.enabled and not session_id and cfg.on_missing == "fail":
        return AgentResult(False, "", "missing codex session id", session_mode="missing_session")
    result = agent.run(prompt, cwd, timeout_s, session_id, cfg.on_resume_failure)
    if cfg.enabled:
        active_session_id = session_id if result.session_mode == "resume" else result.session_id
        write_codex_session_event(
            repo,
            role.session_id,
            result.session_mode,
            {"ok": result.ok, "session_id": active_session_id, "previous_session_id": session_id},
        )
        if result.session_id:
            write_codex_session(repo, role.session_id, cfg.session_file, result.session_id)
    return result

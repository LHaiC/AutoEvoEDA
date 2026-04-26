from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from autoevoeda.artifacts import read_codex_session, write_codex_session_event
from autoevoeda.config import AgentRoleConfig, DomainAgentConfig


@dataclass(frozen=True)
class AgentResult:
    ok: bool
    stdout: str
    stderr: str
    session_mode: str = "new"


class CodexBackend:
    def __init__(self, sandbox: str = "workspace-write") -> None:
        self.sandbox = sandbox

    def run(self, prompt: str, cwd: Path, timeout_s: int, session_id: str = "") -> AgentResult:
        cmd = ["codex", "exec", "--full-auto", "--sandbox", self.sandbox, prompt]
        mode = "new"
        if session_id:
            cmd = ["codex", "exec", "resume", "--full-auto", session_id, prompt]
            mode = "resume"
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        return AgentResult(ok=proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr, session_mode=mode)


def run_codex_role(
    repo: Path,
    role: AgentRoleConfig | DomainAgentConfig,
    agent: CodexBackend,
    prompt: str,
    cwd: Path,
    timeout_s: int,
) -> AgentResult:
    cfg = role.codex_session
    session_id = read_codex_session(repo, role.session_id, cfg.session_file) if cfg.enabled else ""
    result = agent.run(prompt, cwd, timeout_s, session_id)
    if cfg.enabled:
        write_codex_session_event(repo, role.session_id, result.session_mode, {"ok": result.ok, "session_id": session_id})
    return result

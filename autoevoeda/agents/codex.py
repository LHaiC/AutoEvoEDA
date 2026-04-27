from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
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
    def __init__(self, sandbox: str = "workspace-write", model: str = "", profile: str = "", config: dict[str, Any] | None = None) -> None:
        self.sandbox = sandbox
        self.model = model
        self.profile = profile
        self.config = config or {}

    def run(self, prompt: str, cwd: Path, timeout_s: int, session_id: str = "") -> AgentResult:
        cmd = ["codex", "exec", *self._model_args(include_profile=True, include_add_dirs=True), "--full-auto", "--sandbox", self.sandbox, "--skip-git-repo-check", "-"]
        mode = "new"
        if session_id:
            cmd = ["codex", "exec", "resume", *self._model_args(include_profile=False, include_add_dirs=False), "--full-auto", "--skip-git-repo-check", session_id, "-"]
            mode = "resume"
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        return AgentResult(ok=proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr, session_mode=mode)

    def _model_args(self, include_profile: bool, include_add_dirs: bool) -> list[str]:
        args = []
        if self.model:
            args.extend(["--model", self.model])
        if include_profile and self.profile:
            args.extend(["--profile", self.profile])
        if include_add_dirs:
            for value in self.config.get("add_dirs", []):
                args.extend(["--add-dir", str(value)])
        for key, value in self.config.items():
            if key == "add_dirs":
                continue
            args.extend(["--config", f"{key}={_toml_value(value)}"])
        return args


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported agent.config value type: {type(value).__name__}")


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

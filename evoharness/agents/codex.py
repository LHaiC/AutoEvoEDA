from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class AgentResult:
    ok: bool
    stdout: str
    stderr: str


class CodexBackend:
    def __init__(self, sandbox: str = "workspace-write") -> None:
        self.sandbox = sandbox

    def run(self, prompt: str, cwd: Path, timeout_s: int) -> AgentResult:
        proc = subprocess.run(
            ["codex", "exec", "--full-auto", "--sandbox", self.sandbox, prompt],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        return AgentResult(ok=proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr)

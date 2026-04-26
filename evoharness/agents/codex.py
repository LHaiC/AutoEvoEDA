from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import time


@dataclass(frozen=True)
class AgentResult:
    ok: bool
    stdout: str
    stderr: str
    session_id: str = ""
    session_mode: str = "new"


class CodexBackend:
    def __init__(self, sandbox: str = "workspace-write") -> None:
        self.sandbox = sandbox

    def _run_new(self, prompt: str, cwd: Path, timeout_s: int, since: float) -> AgentResult:
        proc = subprocess.run(
            ["codex", "exec", "--full-auto", "--sandbox", self.sandbox, prompt],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        return AgentResult(
            ok=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            session_id=_latest_session_id(cwd, since),
            session_mode="new",
        )

    def run(
        self,
        prompt: str,
        cwd: Path,
        timeout_s: int,
        session_id: str = "",
        on_resume_failure: str = "new",
    ) -> AgentResult:
        since = time.time()
        if not session_id:
            return self._run_new(prompt, cwd, timeout_s, since)

        proc = subprocess.run(
            ["codex", "exec", "resume", "--full-auto", session_id, prompt],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        if proc.returncode == 0 or on_resume_failure == "fail":
            return AgentResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                session_id=session_id,
                session_mode="resume",
            )
        fresh = self._run_new(prompt, cwd, timeout_s, since)
        return AgentResult(
            ok=fresh.ok,
            stdout=fresh.stdout,
            stderr=(proc.stderr + "\n" + fresh.stderr).strip(),
            session_id=fresh.session_id,
            session_mode="new_after_resume_failure",
        )


def _latest_session_id(cwd: Path, since: float) -> str:
    sessions = Path.home() / ".codex" / "sessions"
    if not sessions.exists():
        return ""
    recent = [path for path in sessions.rglob("*.jsonl") if path.stat().st_mtime >= since - 1]
    files = sorted(recent, key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files[:20]:
        try:
            first = path.read_text().splitlines()[0]
            payload = json.loads(first).get("payload", {})
        except (IndexError, OSError, json.JSONDecodeError):
            continue
        if payload.get("cwd") == str(cwd):
            return str(payload.get("id", ""))
    return ""

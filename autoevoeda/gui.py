from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import json
from urllib.parse import parse_qs

from autoevoeda.config import load_config
from autoevoeda.artifacts import add_session_comment, promote_cycle, set_session_status


def _repo(config_path: Path) -> Path:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _workflow_graph() -> str:
    steps = ["Understand", "Plan", "Propose", "Implement", "Guard", "Build", "Regression", "Benchmark", "Reward", "Human", "Promote"]
    return '<div class="graph">' + ''.join(f'<span>{escape(step)}</span>' for step in steps) + '</div>'


def render_dashboard(repo: Path) -> str:
    evo = repo / ".evo"
    state = _read(evo / "session" / "state.json")
    events = _read_jsonl(evo / "events.jsonl")[-30:]
    history = _read_jsonl(evo / "history.jsonl")[-30:]
    roadmap = _read(evo / "roadmap.md")
    memory_index = _read(evo / "memory" / "code" / "index.md")
    runs_dir = evo / "runs"
    runs = sorted([p.name for p in runs_dir.iterdir() if p.is_dir()]) if runs_dir.exists() else []
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('cycle', '')))}</td>"
        f"<td>{escape(str(item.get('candidate_index', '')))}</td>"
        f"<td>{escape(str(item.get('decision', '')))}</td>"
        f"<td>{escape(str(item.get('reason', '')))}</td>"
        f"<td>{escape(str(item.get('branch', '')))}</td>"
        "</tr>"
        for item in history
    )
    event_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('time', '')))}</td>"
        f"<td>{escape(str(item.get('type', '')))}</td>"
        f"<td>{escape(str(item.get('run_id', '')))}</td>"
        f"<td><code>{escape(json.dumps(item.get('payload', {}), ensure_ascii=False))}</code></td>"
        "</tr>"
        for item in events
    )
    run_links = "".join(
        f'<li><a href="/file/.evo/runs/{escape(name)}/04_decision.md">{escape(name)}</a> '
        f'<a href="/file/.evo/runs/{escape(name)}/events.jsonl">events</a></li>'
        for name in runs
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AutoEvoEDA</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 24px; color: #1d252c; background: #f6f3ee; }}
h1 {{ margin-bottom: 4px; }}
section {{ background: white; border: 1px solid #ddd4c8; border-radius: 12px; padding: 16px; margin: 16px 0; }}
.graph {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.graph span {{ background: #173f35; color: white; padding: 8px 10px; border-radius: 999px; }}
.graph span:not(:last-child)::after {{ content: ' →'; color: #173f35; margin-left: 8px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border-bottom: 1px solid #e6ded4; padding: 6px; text-align: left; vertical-align: top; }}
pre {{ white-space: pre-wrap; background: #f8f8f8; border: 1px solid #eee; padding: 12px; border-radius: 8px; max-height: 360px; overflow: auto; }}
a {{ color: #0f5f8f; }}
</style>
</head>
<body>
<h1>AutoEvoEDA dashboard</h1>
<p>Local control view for <code>{escape(str(repo))}</code></p>
<section><h2>Workflow</h2>{_workflow_graph()}</section>
<section><h2>Controls</h2>
<form method="post" action="/action/comment"><input name="text" placeholder="human steering comment" size="80"> <button>Comment</button></form>
<form method="post" action="/action/pause"><button>Pause</button></form>
<form method="post" action="/action/resume"><button>Resume</button></form>
<form method="post" action="/action/promote"><input name="cycle" placeholder="cycle" size="6"> <input name="candidate" placeholder="candidate" size="8" value="1"> <button>Promote</button></form>
</section>
<section><h2>Session State</h2><pre>{escape(state)}</pre></section>
<section><h2>History</h2><table><tr><th>Cycle</th><th>Candidate</th><th>Decision</th><th>Reason</th><th>Branch</th></tr>{rows}</table></section>
<section><h2>Recent Events</h2><table><tr><th>Time</th><th>Type</th><th>Run</th><th>Payload</th></tr>{event_rows}</table></section>
<section><h2>Runs</h2><ul>{run_links}</ul></section>
<section><h2>Roadmap</h2><pre>{escape(roadmap)}</pre></section>
<section><h2>Code Memory Index</h2><pre>{escape(memory_index)}</pre></section>
</body>
</html>"""


def serve_gui(config_path: Path, host: str, port: int) -> None:
    repo = _repo(config_path)

    class Handler(BaseHTTPRequestHandler):
        def _redirect(self) -> None:
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def do_GET(self) -> None:
            if self.path == "/" or self.path == "/index.html":
                body = render_dashboard(repo).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/file/"):
                rel = self.path.removeprefix("/file/")
                path = (repo / rel).resolve()
                if repo.resolve() in path.parents and path.exists() and path.is_file():
                    body = escape(path.read_text()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<pre>")
                    self.wfile.write(body)
                    self.wfile.write(b"</pre>")
                    return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            data = parse_qs(self.rfile.read(length).decode())
            if self.path == "/action/comment":
                add_session_comment(config_path, data.get("text", [""])[0])
                return self._redirect()
            if self.path == "/action/pause":
                set_session_status(config_path, "paused")
                return self._redirect()
            if self.path == "/action/resume":
                set_session_status(config_path, "running")
                return self._redirect()
            if self.path == "/action/promote":
                cycle = int(data.get("cycle", ["0"])[0])
                candidate = int(data.get("candidate", ["1"])[0])
                promote_cycle(config_path, cycle, candidate)
                return self._redirect()
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving AutoEvoEDA GUI at http://{host}:{port}")
    server.serve_forever()

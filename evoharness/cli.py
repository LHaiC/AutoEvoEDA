from __future__ import annotations

from pathlib import Path
import argparse

from evoharness.gui import serve_gui
from evoharness.pipeline.cycle import run_cycles
from evoharness.promote import promote_cycle
from evoharness.session import add_session_comment, session_status, set_session_status
from evoharness.understand import run_understand


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run local evolution cycles")
    run.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    run.add_argument("--cycles", type=int, default=1)
    run.add_argument("--human-review", action="store_true", help="pause for review after all gates pass")
    promote = subparsers.add_parser("promote", help="promote an accepted or kept cycle")
    promote.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    promote.add_argument("--cycle", type=int, required=True)
    promote.add_argument("--candidate", type=int, default=1)
    session = subparsers.add_parser("session", help="inspect or steer a local evolution session")
    session.add_argument("action", choices=["status", "comment", "pause", "resume"])
    session.add_argument("text", nargs="*")
    session.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand = subparsers.add_parser("understand", help="write deterministic code-understanding memory")
    understand.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand.add_argument("--agent", action="store_true", help="enrich deterministic memory with Codex")
    gui = subparsers.add_parser("gui", help="serve a read-only local dashboard")
    gui.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_cycles(config_path=args.config, cycles=args.cycles, human_review=args.human_review)
    if args.command == "promote":
        promote_cycle(config_path=args.config, cycle=args.cycle, candidate_index=args.candidate)
    if args.command == "session":
        if args.action == "status":
            print(session_status(args.config))
        if args.action == "comment":
            print(add_session_comment(args.config, " ".join(args.text)))
        if args.action == "pause":
            print(set_session_status(args.config, "paused"))
        if args.action == "resume":
            print(set_session_status(args.config, "running"))
    if args.command == "understand":
        run_understand(args.config, use_agent=args.agent)
    if args.command == "gui":
        serve_gui(args.config, args.host, args.port)


if __name__ == "__main__":
    main()

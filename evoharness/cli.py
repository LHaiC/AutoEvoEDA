from __future__ import annotations

from pathlib import Path
import argparse

from evoharness.compare import compare_cycle
from evoharness.config import load_config
from evoharness.daemon import run_daemon
from evoharness.gui import serve_gui
from evoharness.pipeline.cycle import run_cycles
from evoharness.promote import promote_cycle
from evoharness.rules import accept_rule, list_rule_proposals, propose_rules, reject_rule
from evoharness.session import add_session_comment, session_status, set_session_status
from evoharness.understand import run_understand
from evoharness.worktrees import cleanup_worktrees, list_worktrees


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run local evolution cycles")
    run.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    run.add_argument("--cycles", type=int, default=1)
    run.add_argument("--human-review", action="store_true", help="pause for review after all gates pass")
    daemon = subparsers.add_parser("daemon", help="run a file-controlled long-running evolution loop")
    daemon.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    daemon.add_argument("--max-cycles", type=int, default=0, help="0 means run until paused or interrupted")
    daemon.add_argument("--sleep-s", type=float, default=60.0)
    daemon.add_argument("--human-review", action="store_true", help="pause for review after all gates pass")
    promote = subparsers.add_parser("promote", help="promote an accepted or kept cycle")
    promote.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    promote.add_argument("--cycle", type=int, required=True)
    promote.add_argument("--candidate", type=int, default=1)
    worktree = subparsers.add_parser("worktree", help="list or clean candidate worktrees")
    worktree.add_argument("action", choices=["list", "cleanup"])
    worktree.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    worktree.add_argument("--rejected", action="store_true")
    worktree.add_argument("--older-than-days", type=int, default=0)
    worktree.add_argument("--include-accepted", action="store_true")
    worktree.add_argument("--force", action="store_true")
    rules = subparsers.add_parser("rules", help="propose or approve rulebase updates")
    rules.add_argument("action", choices=["list", "propose", "accept", "reject"])
    rules.add_argument("proposal", nargs="?")
    rules.add_argument("comment", nargs="*")
    rules.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    config = subparsers.add_parser("config", help="validate evo.yaml")
    config.add_argument("action", choices=["validate"])
    config.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    compare = subparsers.add_parser("compare", help="summarize candidates from one cycle")
    compare.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    compare.add_argument("--cycle", type=int, required=True)
    session = subparsers.add_parser("session", help="inspect or steer a local evolution session")
    session.add_argument("action", choices=["status", "comment", "pause", "resume"])
    session.add_argument("text", nargs="*")
    session.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand = subparsers.add_parser("understand", help="write deterministic code-understanding memory")
    understand.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand.add_argument("--agent", action="store_true", help="enrich deterministic memory with Codex")
    understand.add_argument("--module", action="append", dest="modules", help="limit understanding to one allowed prefix")
    understand.add_argument("--changed-only", action="store_true", help="index changed files under selected modules")
    gui = subparsers.add_parser("gui", help="serve a read-only local dashboard")
    gui.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_cycles(config_path=args.config, cycles=args.cycles, human_review=args.human_review)
    if args.command == "daemon":
        run_daemon(
            config_path=args.config,
            max_cycles=args.max_cycles,
            sleep_s=args.sleep_s,
            human_review=args.human_review,
        )
    if args.command == "promote":
        promote_cycle(config_path=args.config, cycle=args.cycle, candidate_index=args.candidate)
    if args.command == "worktree":
        if args.action == "list":
            for row in list_worktrees(args.config):
                print(row)
        if args.action == "cleanup":
            for row in cleanup_worktrees(
                args.config,
                rejected=args.rejected,
                older_than_days=args.older_than_days,
                include_accepted=args.include_accepted,
                force=args.force,
            ):
                print(row)
    if args.command == "rules":
        if args.action == "list":
            for proposal in list_rule_proposals(args.config):
                print(proposal)
        if args.action == "propose":
            print(propose_rules(args.config))
        if args.action == "accept":
            if not args.proposal:
                raise SystemExit("rules accept requires a proposal id")
            print(accept_rule(args.config, args.proposal))
        if args.action == "reject":
            if not args.proposal:
                raise SystemExit("rules reject requires a proposal id")
            print(reject_rule(args.config, args.proposal, " ".join(args.comment)))
    if args.command == "config":
        load_config(args.config)
        print(f"ok: {args.config}")
    if args.command == "compare":
        print(compare_cycle(args.config, args.cycle))
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
        run_understand(args.config, use_agent=args.agent, modules=args.modules, changed_only=args.changed_only)
    if args.command == "gui":
        serve_gui(args.config, args.host, args.port)


if __name__ == "__main__":
    main()

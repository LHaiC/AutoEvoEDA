from __future__ import annotations

from pathlib import Path
import argparse

from autoevoeda.artifacts import (
    accept_rule,
    cleanup_worktrees,
    compare_cycle,
    list_rule_proposals,
    list_worktrees,
    promote_cycle,
    propose_rules,
    reject_rule,
    write_reports,
    add_session_comment,
    session_status,
    set_session_status,
)
from autoevoeda.config import load_config
from autoevoeda.daemon import run_daemon
from autoevoeda.gui import serve_gui
from autoevoeda.pipeline.cycle import run_cycles
from autoevoeda.understand import run_understand


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run local evolution cycles")
    run.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    run.add_argument("--cycles", type=int, default=1)
    run.add_argument("--human-review", action="store_true", help="pause for review after all gates pass")
    run.add_argument("--continue", dest="continue_run", action="store_true", help="resume completed, paused, or interrupted sessions for the requested cycles")
    daemon = subparsers.add_parser("daemon", help="run a file-controlled long-running evolution loop")
    daemon.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    daemon.add_argument("--max-cycles", type=int, default=0, help="0 means run until paused or interrupted")
    daemon.add_argument("--sleep-s", type=float, default=60.0)
    daemon.add_argument("--human-review", action="store_true", help="pause for review after all gates pass")
    daemon.add_argument("--non-stop", action="store_true", help="run until manually paused; ignores max cycle and consecutive-reject stops")
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
    report = subparsers.add_parser("report", help="write long-running summary reports")
    report.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    session = subparsers.add_parser("session", help="inspect or steer a local evolution session")
    session.add_argument("action", choices=["status", "comment", "pause", "resume"])
    session.add_argument("text", nargs="*")
    session.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand = subparsers.add_parser("understand", help="run pre-evolution understanding workflow")
    understand.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    understand.add_argument("--phase", choices=["scaffold", "profile", "relationships", "guidance", "role_memory", "review", "all"], default="all")
    understand.add_argument("--module", action="append", dest="modules", help="limit understanding to one allowed prefix")
    understand.add_argument("--changed-only", action="store_true", help="index changed files under selected modules")
    gui = subparsers.add_parser("gui", help="serve a local dashboard")
    gui.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_cycles(config_path=args.config, cycles=args.cycles, human_review=args.human_review, continue_run=args.continue_run)
    elif args.command == "daemon":
        run_daemon(
            config_path=args.config,
            max_cycles=args.max_cycles,
            sleep_s=args.sleep_s,
            human_review=args.human_review,
            non_stop=args.non_stop,
        )
    elif args.command == "promote":
        promote_cycle(config_path=args.config, cycle=args.cycle, candidate_index=args.candidate)
    elif args.command == "worktree":
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
    elif args.command == "rules":
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
    elif args.command == "config":
        load_config(args.config)
        print(f"ok: {args.config}")
    elif args.command == "compare":
        print(compare_cycle(args.config, args.cycle))
    elif args.command == "report":
        cfg = load_config(args.config)
        repo = (args.config.parent / cfg.project.repo).resolve()
        print(write_reports(repo))
    elif args.command == "session":
        if args.action == "status":
            print(session_status(args.config))
        if args.action == "comment":
            print(add_session_comment(args.config, " ".join(args.text)))
        if args.action == "pause":
            print(set_session_status(args.config, "paused"))
        if args.action == "resume":
            print(set_session_status(args.config, "running"))
    elif args.command == "understand":
        run_understand(args.config, phase=args.phase, modules=args.modules, changed_only=args.changed_only)
    elif args.command == "gui":
        serve_gui(args.config, args.host, args.port)


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import argparse

from evoharness.pipeline.cycle import run_cycles
from evoharness.promote import promote_cycle


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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_cycles(config_path=args.config, cycles=args.cycles, human_review=args.human_review)
    if args.command == "promote":
        promote_cycle(config_path=args.config, cycle=args.cycle, candidate_index=args.candidate)


if __name__ == "__main__":
    main()

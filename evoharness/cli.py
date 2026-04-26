from __future__ import annotations

from pathlib import Path
import argparse

from evoharness.pipeline.cycle import run_cycles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run local evolution cycles")
    run.add_argument("--config", "-c", type=Path, default=Path("evo.yaml"))
    run.add_argument("--cycles", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        run_cycles(config_path=args.config, cycles=args.cycles)


if __name__ == "__main__":
    main()

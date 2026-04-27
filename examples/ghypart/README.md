# gHyPart Adapter Example

This example shows how to wire AutoEvoEDA to a real public CUDA EDA repository without putting project-specific logic in the framework.

- Source submodule: `examples/gHyPart_TACO`
- Adapter files: `examples/ghypart`
- Candidate workspace: `examples/.evo-worktrees/<run>/ghypart`
- Run state and history: `examples/ghypart/.evo/`

The adapter uses `workspace.mode: multi_repo` even though it has one child repo. That keeps the adapter, logs, prompts, and evaluator scripts outside the candidate source tree.

## Setup

```bash
git submodule update --init --recursive examples/gHyPart_TACO
pip install -e .
evo config validate --config examples/ghypart/evo.yaml
```

Build requirements follow the upstream project documentation in `examples/gHyPart_TACO/README.md`. If the local checkout contains `BUILD_REPRO_CPU_GPU.md`, use it as the reproduction note for this machine.

## Smoke Run

The included scripts are intentionally conservative:

- `build.sh` configures and builds `gHyPart` in the candidate worktree.
- `run_regression.sh` runs the binary with no arguments and checks the startup usage text.
- `compare_regression.py` checks the JSON produced by the smoke regression.
- `run_perf.sh` records that no public benchmark metric is configured yet.
- `reward.py` fails unless `AUTOEVO_ALLOW_PLACEHOLDER_REWARD=1` is set.

This means the adapter can validate harness plumbing and build/regression wiring, but it is not a real performance-evolution benchmark until a project-owned benchmark set, golden outputs, and reward metric are added.

## Example Commands

```bash
evo understand --config examples/ghypart/evo.yaml --phase scaffold
AUTOEVO_ALLOW_PLACEHOLDER_REWARD=1 evo run --config examples/ghypart/evo.yaml --cycles 1
```

Do not commit generated `examples/ghypart/.evo/`, candidate worktrees, build directories, datasets, or benchmark results.

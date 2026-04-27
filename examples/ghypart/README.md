# gHyPart Weighted Adapter Example

This adapter wires AutoEvoEDA to the public `gHyPart_TACO` CUDA hypergraph partitioner and makes the first real target weighted-hypergraph support.

- Adapter workdir: `examples/ghypart`
- Source submodule: `examples/ghypart/source/gHyPart_TACO`
- Candidate workspace: `examples/ghypart/.evo-worktrees/<run>/ghypart`
- Run state and history: `examples/ghypart/.evo/`
- Adapter-owned benchmarks: `examples/ghypart/benchmarks/`

The adapter uses `workspace.mode: multi_repo` even though it has one child repo. That keeps prompts, scripts, benchmarks, logs, and `.evo/` outside the candidate source tree.

## Setup

```bash
git submodule update --init --recursive examples/ghypart/source/gHyPart_TACO
pip install -e .
evo config validate --config examples/ghypart/evo.yaml
```

Build requirements follow the upstream project documentation in `examples/ghypart/source/gHyPart_TACO/README.md`.

## Target

Convert the current unweighted `.hgr` handling into real hMETIS-style weighted handling:

- unweighted input still works
- hyperedge weights are parsed when `fmt` enables them
- vertex weights are parsed when `fmt` enables them
- weighted cut/balance bookkeeping can use those weights
- evaluator files and benchmark inputs stay immutable

The regression uses two adapter-owned public smoke inputs:

```text
benchmarks/unweighted_smoke.hgr
benchmarks/weighted_smoke.hgr
```

For weighted inputs, the candidate must print a machine-readable summary line whose totals match the input:

```text
AUTOEVO_WEIGHTED_HGR edge_weights=<0-or-1> vertex_weights=<0-or-1> total_edge_weight=<sum> total_vertex_weight=<sum> pins=<pin-count>
```

`run_regression.sh` computes the expected line from `weighted_smoke.hgr` and rejects candidates that do not emit it.

## Commands

```bash
evo understand --config examples/ghypart/evo.yaml --phase scaffold
evo run --config examples/ghypart/evo.yaml --cycles 1
```

The evaluator is CUDA-only. `runner.preflight` checks NVIDIA device visibility before build/regression/perf gates. Candidate code agents remain scoped by guards; evaluator access is recorded with `runner.sandbox: danger-full-access`.

If an agent self-tests before handing off, it must use only its injected `/tmp/autoevo-*` build/output directories. The evaluator also builds under `AUTOEVO_RUNNER_BUILD_ROOT`, while result JSON remains under the candidate workspace `results/` for framework collection. Candidate-local source-repo paths such as `ghypart/build/` are forbidden and will be rejected by guards.

Do not commit generated `.evo/`, `.evo-worktrees/`, source build directories, datasets, or benchmark results.

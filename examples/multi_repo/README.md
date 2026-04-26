# Multi-Repo Adapter Example

Use this shape when the project is a workspace made of several sibling git repositories. AutoEvoEDA keeps a small adapter/control repo for `evo.yaml`, prompts, scripts, and `.evo/` state, then creates one candidate workspace per cycle with one git worktree per child repo.

```text
adapter-repo/
  evo.yaml
  prompts/
  scripts/
  .evo/

source-workspace/
  flow/.git
  mapper/.git
  logic/.git

.evo-worktrees/project-cycle-001/
  flow/      # worktree from source-workspace/flow
  mapper/    # worktree from source-workspace/mapper
  logic/     # worktree from source-workspace/logic
```

Pipeline commands run with:

```text
cwd = AUTOEVO_CANDIDATE_ROOT
AUTOEVO_ADAPTER_ROOT=/path/to/adapter-repo
AUTOEVO_CANDIDATE_ROOT=/path/to/candidate-workspace
```

So adapter-owned scripts should usually be invoked through `$AUTOEVO_ADAPTER_ROOT/scripts/...` and then operate on `$AUTOEVO_CANDIDATE_ROOT`.

## CUDA-Only Evaluators

If a project benchmark is CUDA-only, do not use CPU fallback. Configure `runner.preflight` to call `scripts/cuda_preflight.sh`, and also source `require_cuda` inside golden generation, regression, and performance scripts when those scripts can be run directly. If CUDA is not visible, fail fast and do not generate golden data or reward scores.

Candidate code agents should stay sandboxed and scoped by guards. Only the evaluator process needs access to host NVIDIA devices. `runner.sandbox: danger-full-access` records that requirement but cannot escape a restricted parent process; if the parent runner cannot see `/dev/nvidia*`, launch AutoEvoEDA from a full-access environment rather than widening the code-editing agent.

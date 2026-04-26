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

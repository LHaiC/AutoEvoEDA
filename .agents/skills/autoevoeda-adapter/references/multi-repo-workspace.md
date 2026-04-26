# Multi-Repo Workspace Adapter

Use `workspace.mode: multi_repo` when a project builds as one workspace but source code lives in several sibling git repositories. Do not force those repositories into a new monorepo. Keep a small adapter/control repo for `evo.yaml`, prompts, scripts, and `.evo/` state.

## Layout

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
  flow/
  mapper/
  logic/
```

## Config Pattern

```yaml
workspace:
  mode: multi_repo
  source_root: ../source-workspace
  worktree_root: ../.evo-worktrees
  repos:
    - name: mapper
      path: mapper
      champion_branch: main
      candidate_branch_prefix: evo
      allowed_paths:
        - src/
      forbidden_paths:
        - golden/
  materialize:
    copy: []
    symlink: []

guards:
  allowed_paths:
    - mapper/src/
  forbidden_paths:
    - scripts/
    - results/

pipeline:
  build: bash "$AUTOEVO_ADAPTER_ROOT/scripts/build.sh"
```

`workspace.repos[*].allowed_paths` are local to that child repo. `guards.allowed_paths` are candidate-root paths prefixed by repo name, for example `mapper/src/`.

## Runtime Contract

Pipeline commands run from the candidate workspace root and receive:

```text
AUTOEVO_ADAPTER_ROOT=/path/to/adapter-repo
AUTOEVO_CANDIDATE_ROOT=/path/to/candidate-workspace
```

Scripts should read adapter-owned data from `$AUTOEVO_ADAPTER_ROOT` and run project commands under `$AUTOEVO_CANDIDATE_ROOT`.

## Promotion

Accepted multi-repo candidates are not merged automatically. `evo promote` fast-forwards each child repo candidate branch into that repo's configured `champion_branch`.

# ABC Adapter Example

This directory shows what an open-source project adapter should provide to `evo-harness`. ABC is used as the public example because its build, equivalence checking, and benchmark-evaluation shape matches the long-running EDA evolution loop described in `2604.15082v1`.

The framework does not know ABC internals. ABC-specific behavior lives in this adapter:

```text
evo.yaml
prompts/coder.md
scripts/build.sh
scripts/run_regression.sh
scripts/compare_regression.py
scripts/run_perf.sh
scripts/reward.py
```

## Required Files

### `evo.yaml`

Defines the local evolution contract:

```text
project name
candidate repo path
champion branch
worktree root
allowed and forbidden patch paths
pipeline commands
```

Keep project-specific benchmark paths and commands here or inside scripts. Do not hard-code them in `evo-harness` Python code.

### `prompts/coder.md`

The base prompt for Codex. It should state:

```text
optimization goal
allowed implementation area
correctness constraints
forbidden edits
benchmark semantics that must be preserved
```

For ABC-style logic synthesis work, the prompt should remind the agent to preserve equivalence checking, avoid hard-coded benchmark names, and keep patches small.

### `scripts/build.sh`

Builds the candidate repository.

Contract:

```text
exit 0     build passed
non-zero   build failed
```

Typical contents can include `make`, `cmake`, or project-specific build commands.

### `scripts/run_regression.sh`

Runs correctness checks for the candidate repository.

Contract:

```text
exit 0     regression passed
non-zero   regression failed
```

For ABC, this may run a small public benchmark set and equivalence checks such as CEC or another project-approved correctness oracle.

### `scripts/compare_regression.py`

Compares candidate regression output against golden/reference output if regression generation and comparison are separate.

Contract:

```text
exit 0     candidate matches reference
non-zero   mismatch or missing output
```

This script is an evaluator and should be listed under `forbidden_paths` in `evo.yaml` so candidate agents cannot weaken it.

### `scripts/run_perf.sh`

Runs public performance or QoR benchmarks for the candidate repository.

Contract:

```text
exit 0     benchmark completed and produced usable output
non-zero   benchmark failed
```

Performance scripts should keep correctness and QoR separate. A faster but incorrect candidate must fail regression before reward is considered.

### `scripts/reward.py`

Computes the final accept/reject reward gate from performance or QoR output.

Contract:

```text
exit 0     reward target passed
non-zero   reward target failed
```

This script is also an evaluator and should be forbidden for candidate edits.

## What Not To Put In The Framework

Do not add ABC-specific logic to `evoharness/`:

```text
benchmark names
tolerance values
build-system details
case-specific output paths
reward formulas
regression comparison rules
equivalence-check command lines
```

Those belong in `evo.yaml`, `prompts/`, or `scripts/`.

## Safety Expectations

The adapter should make these files forbidden candidate edit targets:

```text
evo.yaml
scripts/
.github/
benchmarks/
golden/
results/
```

The adapter should keep candidate edits scoped to implementation paths such as:

```text
src/base/
src/map/
src/opt/
src/aig/
```

Adjust these paths for the real ABC checkout.

## Placeholder Scripts

The scripts in this example directory are placeholders. Replace them in a real ABC checkout with commands that actually build, regress, benchmark, compare, and reward the candidate.

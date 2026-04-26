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
schema version
project name
candidate repo path
champion branch
worktree root
allowed and forbidden patch paths
pipeline commands
structured evaluator result files
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

## Structured Result Files

Project scripts may write JSON object files under `results/`. The harness copies their parsed content into `.evo/<run_id>/evaluator_results.json`, `.evo/history.jsonl`, and the cycle summary.

Suggested ABC-shaped files:

```text
results/correctness.json   CEC or approved oracle pass/fail counts
results/qor.json           area, depth, runtime, and delta vectors
results/perf.json          benchmark timing measurements
results/reward.json        final scalar reward or gate explanation
```

Keep these files machine-readable and separate from stdout logs. If a configured result file exists but is not a JSON object, the candidate is rejected after the normal gates finish.

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

## Optional Long-Running Files

### `prompts/planner.md`

Advisory planning guidance. It should narrow the search target before the coding prompt is applied. In this minimal harness it is prompt context, not a separate agent.

### `prompts/reviewer.md`

Advisory review guidance. It should describe risks the coding agent must avoid, such as hard-coded benchmark names, weakened equivalence checks, or scope creep. It cannot accept a patch.

Enable opt-in planner/reviewer Codex calls with:

```yaml
multi_agent:
  planner: true
  reviewer: true
```

The planner output is injected into the coder prompt. The reviewer output is advisory and cannot replace evaluator gates.

### `prompts/repair.md`

Repair guidance used when `repair.enabled` is true and a gate fails. Keep this prompt focused on fixing the failing gate without weakening evaluators.

### `.evo/memory/rulebase.md`

Long-running rule memory. Use it for project-neutral constraints, accepted operating rules, and lessons that should steer future prompts. Do not place private project details in the public ABC example.

## Candidate Pools

The example config keeps pool execution disabled. To run several independent candidates per cycle in a real checkout, set:

```yaml
pool:
  enabled: true
  size: 2
budget:
  max_cycles: 3
  max_candidates: 4
```

Each candidate receives its own branch and worktree, such as `evo/cycle-001-cand-002`.

Compare a pool after evaluation:

```bash
evo compare --config evo.yaml --cycle 1
```

This writes `.evo/reports/compare-cycle-001.md` and does not promote any branch.

Generate summary reports:

```bash
evo report --config evo.yaml
```

## Long-Running Daemon

Use the daemon when you want a local main loop that can be steered from another shell:

```bash
evo daemon --config evo.yaml --max-cycles 10 --sleep-s 30
evo session comment --config evo.yaml "try a smaller mapper-local patch next"
evo session pause --config evo.yaml
```

The daemon still runs the same guard and evaluator contract. It only adds a long-lived loop around the normal cycle runner.
It refuses a second daemon with the same project `.evo/session/daemon.lock` and records heartbeat events.

The local GUI exposes the same controls:

```bash
evo gui --config evo.yaml
```

Use it to add comments, pause or resume the daemon, and explicitly promote accepted candidates.

## Candidate Worktrees

Rejected candidates can be removed after inspection:

```bash
evo worktree list --config evo.yaml
evo worktree cleanup --config evo.yaml --rejected
```

Accepted and kept candidates are skipped unless `--include-accepted` is set.

## Codex Session Resume

Each role can keep a native Codex session id in `.evo/agents/<agent_id>/codex_session.txt`:

```yaml
agents:
  coder:
    session_id: coder-main
    codex_session:
      enabled: true
      session_file: .evo/agents/coder-main/codex_session.txt
      on_missing: new
      on_resume_failure: new
```

The framework-level memory files remain the durable context. Native Codex resume is an optimization for continuity, not a correctness requirement.

## Rulebase Updates

Use rule proposals to turn repeated lessons into durable steering rules:

```bash
evo rules propose --config evo.yaml
evo rules accept rule-YYYYMMDD-HHMMSS --config evo.yaml
```

Accepted rules are appended to `.evo/memory/rulebase.md`; rejected proposals remain in `.evo/rules/` as evidence.

## Code Understanding Memory

Seed or refresh code memory before long daemon runs:

```bash
evo understand --config evo.yaml
evo understand --config evo.yaml --module src/map/ --changed-only
```

This writes module summaries, invariants, extension points, and workflow notes under `.evo/memory/code/`.

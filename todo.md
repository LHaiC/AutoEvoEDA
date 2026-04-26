# Paper-Fidelity TODO

This TODO tracks the remaining work needed to move `evo-harness` from a reusable local evolution harness toward a paper-level reproduction of arXiv:2604.15082v1.

## Status Legend

```text
[ ] not started
[~] partially implemented
[x] done
```

## TODO List

- [x] **ABC adapter scripts**
  - Adapter-owned. Keep framework examples as placeholders; real projects provide build, regression, CEC, QoR, performance, and reward scripts.
  - Expected files: `scripts/build.sh`, `scripts/run_regression.sh`, `scripts/compare_regression.py`, `scripts/run_perf.sh`, `scripts/reward.py`.

- [~] **Cycle-0 knowledge bootstrap**
  - Generate a structured ABC repository profile covering directory hierarchy, build system, module interactions, command registration, and safe extension points.
  - Output should seed `.evo/memory/code/` before autonomous evolution starts.

- [ ] **ABC tutorial memory**
  - Add Markdown guidance for adding commands/functions, updating `module.make`, preserving Makefile conventions, and interacting with ABC APIs.
  - This should be injected into planner/coder prompts as durable project memory.

- [ ] **External prior-study memory**
  - Record structured findings from flow tuning, technology mapping, and logic-optimization prototypes.
  - Use the findings as design guidance without directly copying incompatible implementations.

- [~] **Domain coding agents**
  - Split the single generic coder into Flow Agent, Mapper Agent, and Logic Minimization Agent.
  - Each agent should have a distinct prompt, memory, session id, and output artifact stream.

- [~] **Per-agent edit scopes**
  - Give each domain agent its own allowed paths, forbidden paths, prompt, memory, session id, and patch guard.
  - Prevent cross-subsystem edits unless explicitly approved by the planner/human policy.

- [~] **Planner coordination**
  - Make the planner read previous QoR, failures, hypotheses, and agent outputs.
  - The planner should choose which subsystem and agent should evolve next.

- [~] **Agent proposal protocol**
  - Require each coding agent to emit a structured hypothesis, target files, expected metric impact, and rollback risk before implementation.
  - Store proposals under `.evo/runs/<run_id>/` for later attribution.

- [x] **Formal correctness gate**
  - Adapter-owned. The framework already treats non-zero regression/compare exits and invalid result JSON as rejects.
  - ABC adapters should implement CEC inside regression or compare scripts.

- [x] **Eight-flow QoR evaluation**
  - Adapter-owned. The framework keeps `perf` and `reward` script contracts generic.
  - ABC adapters should run the synthesis-flow suite and write normalized area/depth/runtime metrics into structured result JSON.

- [x] **Benchmark parallelism**
  - Adapter-owned. Keep cluster/local parallelism inside project scripts so the framework remains portable.
  - Project scripts should write deterministic JSON summaries after parallel jobs finish.

- [~] **Metric schema**
  - Framework collects object-shaped `correctness.json`, `qor.json`, `perf.json`, and `reward.json` and rejects invalid JSON.
  - ABC-specific field names remain adapter-owned; define them before paper-level experiments.

- [~] **Conditional keep logic**
  - Support human/planner-reviewed `keep for synergy` decisions for partial improvements.
  - Preserve candidates that may help another subsystem later without auto-promoting them.

- [~] **Self-debugging loop**
  - Make compile/check failures feed back into the responsible coding agent with bounded retries and failure classification.
  - Attribute failures to build, CEC, regression, QoR, reward, or guard categories.

- [ ] **Self-evolving rulebase agent**
  - Replace deterministic rule proposals with evidence-based rule patches proposed from repeated success/failure patterns.
  - Keep human approval before accepted rules enter future prompts.

- [ ] **Rule safety policy**
  - Require human approval for rule relaxations.
  - Enforce global safety constraints before rulebase updates enter future prompts.

- [~] **Long-run intervention policy**
  - Trigger human intervention on safety events or repeated failures.
  - Avoid requiring manual review on every accepted candidate.

- [~] **ABC result reproducibility**
  - Record benchmark versions, libraries, flow definitions, machine metadata, and commit hashes needed to reproduce reported QoR.
  - Store metadata in `.evo/runs/<run_id>/` and summary reports.

- [ ] **Paper-level report**
  - Generate tables and summaries matching the paper's primary and auxiliary metrics, ablations, and per-subsystem attribution.
  - Reports should distinguish Flow, Mapper, and Logic Minimization contributions.

- [~] **Backend fidelity note**
  - Document that this implementation uses Codex/GPT-style local agents, while the paper used Cursor/Claude-style agents.
  - Compare behavior and workflow shape rather than claiming identical agent execution.

## Implementation Order

1. Metric schema and adapter-owned script contract.
2. Cycle-0 knowledge bootstrap and ABC tutorial memory.
3. Domain coding agents with per-agent edit scopes.
4. Planner coordination and proposal protocol.
5. Formal correctness, eight-flow QoR, and benchmark parallelism.
6. Self-debugging, conditional keep, and intervention policy.
7. Self-evolving rulebase and rule safety policy.
8. Reproducibility metadata and paper-level reports.
9. Backend fidelity documentation.

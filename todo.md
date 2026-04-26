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

- [x] **Cycle-0 knowledge bootstrap**
  - Framework done: `evo understand` writes `.evo/memory/code/bootstrap/repo_profile.md` plus subsystem, safety, tutorial, and prior-study skeletons.
  - Adapter content can enrich these files before autonomous evolution starts.

- [x] **ABC tutorial memory**
  - Framework done: `bootstrap/abc_tutorial.md` is generated and injected into prompts when memory is enabled.
  - ABC-specific command/module.make/API details remain adapter-owned content.

- [x] **External prior-study memory**
  - Framework done: `bootstrap/prior_studies.md` is generated and injected into prompts when memory is enabled.
  - Project teams own the actual external-study content.

- [x] **Domain coding agents**
  - Framework done: `domain_agents` supports configurable domain identities with distinct prompt, memory, session id, and artifact stream.
  - ABC adapters can instantiate Flow, Mapper, and Logic Minimization agents.

- [x] **Per-agent edit scopes**
  - Framework done: selected domain agents use their configured allowed/forbidden paths in patch guard.
  - Cross-subsystem edits are rejected by guard unless adapter scopes allow them.

- [x] **Planner coordination**
  - Framework done: planner prompt receives recent outcome context and must emit exactly one `agent: <name>` when domain agents are configured.
  - Invalid, missing, or unknown selections reject the candidate.

- [x] **Agent proposal protocol**
  - Framework done: domain-agent responses must include `hypothesis`, `target_files`, `expected_metric_impact`, and `rollback_risk`.
  - Proposals are stored as `agent_proposal.json` and `agent_proposal.md` under `.evo/runs/<run_id>/`.

- [x] **Formal correctness gate**
  - Adapter-owned. The framework already treats non-zero regression/compare exits and invalid result JSON as rejects.
  - ABC adapters should implement CEC inside regression or compare scripts.

- [x] **Eight-flow QoR evaluation**
  - Adapter-owned. The framework keeps `perf` and `reward` script contracts generic.
  - ABC adapters should run the synthesis-flow suite and write normalized area/depth/runtime metrics into structured result JSON.

- [x] **Benchmark parallelism**
  - Adapter-owned. Keep cluster/local parallelism inside project scripts so the framework remains portable.
  - Project scripts should write deterministic JSON summaries after parallel jobs finish.

- [x] **Metric schema**
  - Framework done: object-shaped `correctness.json`, `qor.json`, `perf.json`, and `reward.json` are collected and invalid JSON is rejected.
  - `reward.json` may include `score`, `decision`, and `reason`; ABC-specific metric fields remain adapter-owned.

- [x] **Conditional keep logic**
  - Framework done: human review can choose `keep`, and adapter reward JSON can return `{"decision":"keep","reason":"..."}`.
  - Kept candidates are preserved without auto-promotion.

- [x] **Self-debugging loop**
  - Framework done: failed gates are classified by gate name and fed into the bounded repair agent when `repair.enabled` is true.
  - Adapter scripts own fine-grained CEC/QoR classifications inside their stdout/stderr and result JSON.

- [x] **Self-evolving rulebase agent**
  - Framework done: `evo rules propose` creates evidence-based proposals from repeated recent outcomes.
  - `evo rules accept` is still explicit human approval before rules enter future prompts.

- [x] **Rule safety policy**
  - Framework done: rule acceptance requires explicit CLI approval, a `Safety: strict` marker, and rejects unsafe proposal tokens.
  - Accepted rules are appended to the configured rulebase only after this check.

- [x] **Long-run intervention policy**
  - Framework done: `human.stop_after_consecutive_rejects` pauses daemon runs after repeated rejects.
  - Accepted candidates still avoid mandatory manual review unless configured.

- [x] **ABC result reproducibility**
  - Framework done: each run writes `reproducibility.json` with config, project, branch, and commit metadata.
  - Adapter scripts own benchmark/library/flow metadata inside result JSON.

- [x] **Paper-level report**
  - Framework done: `evo report` writes `paper_fidelity.md` with per-agent attribution and metric-file contracts.
  - Exact paper tables depend on adapter-owned ABC metrics.

- [x] **Backend fidelity note**
  - Framework done: README states this is Codex/GPT-style local-agent infrastructure inspired by the paper, not identical backend execution.
  - Backend differences are documented as workflow-shape comparison rather than exact reproduction.

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

# AutoEvoEDA Details


AutoEvoEDA (Autonomous Evolutive EDA) is a minimal local evolution harness for EDA projects, inspired by *Autonomous Evolution of EDA Tools: Multi-Agent Self-Evolved ABC* (arXiv:2604.15082v1). The design is intended for Codex + GPT-5.5 high-reasoning style local coding agents.

```text
Codex proposes patches.
Project scripts judge correctness and performance.
The harness manages worktrees, guards, logs, and accept/reject history.
```

## MVP Usage

```bash
pip install -e .
evo run --config examples/abc/evo.yaml --cycles 1
```

## Project Contract

A project provides `evo.yaml`, a prompt, and scripts for build, regression, performance, and reward gates. Each script uses exit code `0` for pass and non-zero for fail.

Use `schema_version: "1.0"` for the stable local schema.

`AutoEvoEDA` never trusts the agent to decide correctness or performance.

Project scripts may also write structured evaluator result files. The harness records any existing JSON object files in each cycle summary and history:

```yaml
result_files:
  correctness: results/correctness.json
  qor: results/qor.json
  perf: results/perf.json
  reward: results/reward.json
```

These files are adapter-owned. For ABC-style work, `correctness.json` can summarize equivalence checks, `qor.json` can store area/depth/runtime deltas, and `reward.json` can store the final scalar or gate decision.

## Paper Fidelity Status

`AutoEvoEDA` implements the reusable outer loop from arXiv:2604.15082v1: Codex invocation, candidate worktrees, patch guards, event logs, run directories, phase documents, human comments, memory injection, local GUI inspection/control, rule proposals, and explicit promotion.

It does not yet reproduce the full paper system. The paper is an ABC-specific multi-agent self-evolution system with cycle-0 knowledge bootstrapping, a global planning agent, three domain-specialized coding agents, formal equivalence checking, large-scale QoR evaluation, and a self-evolving rulebase. This repository is currently the framework shell that an ABC adapter can use to build toward that system.

## Current Agent Model

The current framework defines six role identities:

```text
planner
coder
reviewer
repair
rulebase
code_understanding
```

Their current behavior is:

```text
planner:
  Optional. Runs before coder when multi_agent.planner is true.
  Writes planner.stdout and appends planner notes into the coder prompt.

coder:
  Required for each candidate. Calls Codex to edit the candidate worktree.

reviewer:
  Optional. Runs after patch guard and before evaluator gates when multi_agent.reviewer is true.
  Advisory only; project scripts still decide correctness and performance.

repair:
  Optional. Runs after a failed gate when repair.enabled is true.
  Receives the failed gate stdout/stderr and attempts a bounded fix.

rulebase:
  Evidence-based rule proposal identity.
  Proposals are file-backed, safety-checked, and require explicit human approval.

code_understanding:
  Optional. Runs through evo understand --agent to enrich deterministic code memory.
```

This differs from the paper. The paper uses a global planning agent plus three ABC domain coding agents: Flow Agent, Mapper Agent, and Logic Minimization Agent. Those agents operate on distinct ABC subsystems and are coordinated through a shared evolving rulebase and a unified correctness/QoR pipeline. `AutoEvoEDA` now supports configurable domain-agent identities, but it does not ship ABC-specific Flow/Mapper/Logic prompts, scopes, or adapter scripts.

## Paper-Fidelity Scope

ABC build, CEC, benchmark, QoR, and reward scripts are adapter-owned. The framework keeps placeholders in `examples/abc/` and focuses on reusable orchestration, agent roles, guards, memory, events, run artifacts, and rulebase contracts.

Framework-level paper-alignment scaffolding is implemented for domain agents, per-agent guard scopes, planner-selected agents, structured proposal artifacts, cycle-0 bootstrap memory, reward-driven keep/reject decisions, rule proposals with safety checks, reproducibility metadata, and paper-fidelity reports. Full experimental reproduction still requires a real ABC adapter and benchmark environment.

## Long-Running Controls

Enable memory in `evo.yaml` to inject project memory, recent lessons, rejected ideas, accepted patterns, and patch scope into the Codex prompt. Lessons are appended to `.evo/memory/lessons.jsonl` after each cycle.

Use human review when accepted candidates should pause for manual steering:

```bash
evo run --config examples/abc/evo.yaml --cycles 5 --human-review
```

Human review can accept, reject, keep, redirect, or pause an all-gates-passed candidate. Every option can include an optional comment and next hint. It does not bypass build, regression, performance, reward, or patch guards.

For a long-running local loop, start the file-controlled daemon:

```bash
evo daemon --config examples/abc/evo.yaml --max-cycles 10 --sleep-s 30
evo session comment --config examples/abc/evo.yaml "focus on mapper cleanup before new heuristics"
evo session pause --config examples/abc/evo.yaml
evo session resume --config examples/abc/evo.yaml
```

The daemon reloads `evo.yaml` between cycles, checks `.evo/session/state.json` before scheduling new work, and injects recent session comments through the normal memory path.
It also writes `.evo/session/daemon.lock`, `.evo/session/active.json`, `.evo/session/active_run.json`, and heartbeat events so long runs are inspectable and a second daemon is refused.

Interrupted runs are detected before new work is scheduled. If a run has an active checkpoint but no final decision, `evo run` and `evo daemon` stop with an error instead of silently starting a new candidate. Inspect `.evo/runs/<run_id>/state.json`, then explicitly abandon the interrupted run if you want to continue:

```bash
evo run --config examples/abc/evo.yaml --abandon-active --cycles 0
```

This writes a deterministic reject decision with reason `abandoned_interrupted_run` and clears `.evo/session/active_run.json`.

Validate configuration before long runs:

```bash
evo config validate --config examples/abc/evo.yaml
```

## Explicit Promotion

Accepted or kept candidates are committed on their candidate branch, but are not promoted automatically. Promote a reviewed cycle explicitly:

```bash
evo promote --config examples/abc/evo.yaml --cycle 1
```

Rejected cycles cannot be promoted. For pooled runs, pass `--candidate N`. Promotion uses a fast-forward merge into the configured champion branch and records a promote event in `.evo/history.jsonl`.
Promotion is manual by default and refuses a tracked dirty project repo when `promotion.require_clean_champion` is true.

Candidate worktrees are kept for inspection. List or clean them explicitly:

```bash
evo worktree list --config examples/abc/evo.yaml
evo worktree cleanup --config examples/abc/evo.yaml --rejected
```

Cleanup uses `git worktree remove`, skips accepted and kept candidates by default, and skips dirty worktrees unless `--force` is provided.

## Repair, Roles, And Candidate Pools

Enable one bounded repair attempt when a gate fails:

```yaml
repair:
  enabled: true
  max_attempts: 1
  prompt_file: prompts/repair.md
```

Role prompt files can align the run with planner/coder/reviewer guidance:

```yaml
multi_agent:
  planner: true
  reviewer: true
roles:
  planner_prompt: prompts/planner.md
  coder_prompt: prompts/coder.md
  reviewer_prompt: prompts/reviewer.md
rulebase:
  path: .evo/memory/rulebase.md
```

When enabled, the planner writes `planner.stdout` before coding and its notes are appended to the coder prompt. The reviewer writes `reviewer.stdout` after patch guards and before evaluator gates; evaluators still decide correctness and performance.

Paper-style domain agents are optional. When `domain_agents` is non-empty, planner must emit exactly one line `agent: <name>`; the selected agent gets its own prompt, session id, memory, allowed paths, forbidden paths, guard scope, and required proposal fields:

```yaml
multi_agent:
  planner: true
roles:
  planner_prompt: prompts/planner.md
domain_agents:
  - name: mapper
    session_id: mapper-main
    prompt_file: prompts/mapper.md
    allowed_paths:
      - src/map/mapper/
    forbidden_paths:
      - src/map/mapper/golden/
```

Domain-agent Codex responses must include `hypothesis:`, `target_files:`, `expected_metric_impact:`, and `rollback_risk:`. The harness stores them as `agent_proposal.json` and `agent_proposal.md` under the run directory.

Run small candidate pools with explicit budgets:

```yaml
pool:
  enabled: true
  size: 2
budget:
  max_cycles: 3
  max_candidates: 4
```

Each candidate still runs the same deterministic guards and project scripts.

Compare pooled candidates without promoting:

```bash
evo compare --config examples/abc/evo.yaml --cycle 1
```

The report is written to `.evo/reports/compare-cycle-001.md` and recommends the highest numeric `evaluator_results.reward.score` when present. `reward.json` may also set `decision` to `accept`, `keep`, or `reject`; `keep` preserves a candidate without auto-promotion.

Write long-running summary reports:

```bash
evo report --config examples/abc/evo.yaml
```

## Run Artifacts

Each candidate writes an event stream and phase documents under `.evo/runs/<run_id>/`:

```text
00_context.md
01_propose.md
02_implement.md
03_benchmark.md
04_decision.md
patch.diff
events.jsonl
evaluator_results.json
state.json
reproducibility.json
```

The repository-level event log is `.evo/events.jsonl`. Human review decisions can include a comment and next hint; those fields are recorded in history, events, and decision documents.

## Code Understanding Memory

Seed hierarchical code memory before long-running evolution:

```bash
evo understand --config examples/abc/evo.yaml
evo understand --config examples/abc/evo.yaml --agent
evo understand --config examples/abc/evo.yaml --module src/map/ --changed-only
```

This writes deterministic memory under `.evo/memory/code/`, including module summaries, invariants, extension points, workflow notes, and cycle-0 bootstrap docs under `.evo/memory/code/bootstrap/`. Bootstrap docs include repository profile, build conventions, command interfaces, subsystem map, safe edit protocol, prior-study notes, and adapter tutorial memory. Use `--agent` to ask Codex to enrich `.evo/memory/code/agent_notes.md` while preserving deterministic memory as the baseline.

## Local GUI

Serve a local dashboard over `.evo` artifacts:

```bash
evo gui --config examples/abc/evo.yaml --host 127.0.0.1 --port 8765
```

The GUI displays workflow state, history, events, run documents, roadmap, and code-memory index. It can also add session comments, pause/resume the daemon, and explicitly promote accepted candidates through the same file-backed APIs as the CLI.

## Agent Session Registry

`AutoEvoEDA` keeps framework-level agent state even when the underlying Codex CLI cannot reliably resume externally supplied sessions:

```text
.evo/agents/<agent_id>/memory.md
.evo/agents/<agent_id>/transcript.jsonl
.evo/agents/<agent_id>/last_prompt.md
.evo/agents/<agent_id>/last_response.md
```

Configure stable role ids in `evo.yaml`:

```yaml
agents:
  planner:
    session_id: planner-main
  coder:
    session_id: coder-main
  reviewer:
    session_id: reviewer-main
  code_understanding:
    session_id: understand-main
```

Role memory is injected into future prompts as a stable framework-level context path for long-running runs.

Optionally enable native Codex session resume for any role:

```yaml
agents:
  coder:
    session_id: coder-main
    codex_session:
      enabled: true
      session_file: .evo/agents/coder-main/codex_session.txt
```

When `session_file` contains a session id, the harness runs `codex exec resume`; otherwise it starts a new Codex invocation. Resume failures are recorded and fail that agent call.

## Rulebase Loop

Long-running runs can propose durable prompt rules from recent evidence, but rulebase changes require explicit human approval:

```bash
evo rules propose --config examples/abc/evo.yaml
evo rules list --config examples/abc/evo.yaml
evo rules accept rule-YYYYMMDD-HHMMSS --config examples/abc/evo.yaml
evo rules reject rule-YYYYMMDD-HHMMSS "not general enough" --config examples/abc/evo.yaml
```

Accepted proposals append to `.evo/memory/rulebase.md` and are injected into future prompts when memory is enabled. Rule acceptance requires a `Safety: strict` marker and rejects unsafe proposal text.

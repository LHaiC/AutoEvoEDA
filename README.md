# evo-harness

Minimal local evolution harness for EDA projects, inspired by *Autonomous Evolution of EDA Tools: Multi-Agent Self-Evolved ABC* (arXiv:2604.15082v1). The design is intended for Codex + GPT-5.5 high-reasoning style local coding agents.

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

`evo-harness` never trusts the agent to decide correctness or performance.

## Long-Running Controls

Enable memory in `evo.yaml` to inject project memory, recent lessons, rejected ideas, accepted patterns, and patch scope into the Codex prompt. Lessons are appended to `.evo/memory/lessons.jsonl` after each cycle.

Use human review when accepted candidates should pause for manual steering:

```bash
evo run --config examples/abc/evo.yaml --cycles 5 --human-review
```

Human review can accept, reject, keep, redirect, or pause an all-gates-passed candidate. Every option can include an optional comment and next hint. It does not bypass build, regression, performance, reward, or patch guards.

## Explicit Promotion

Accepted or kept candidates are committed on their candidate branch, but are not promoted automatically. Promote a reviewed cycle explicitly:

```bash
evo promote --config examples/abc/evo.yaml --cycle 1
```

Rejected cycles cannot be promoted. For pooled runs, pass `--candidate N`. Promotion uses a fast-forward merge into the configured champion branch and records a promote event in `.evo/history.jsonl`.

## Repair, Roles, And Candidate Pools

Enable one bounded repair attempt when a gate fails:

```yaml
repair:
  enabled: true
  max_attempts: 1
  prompt_file: prompts/repair.md
```

Role prompt files can align the run with planner/coder/reviewer guidance without creating multiple agents:

```yaml
roles:
  planner_prompt: prompts/planner.md
  coder_prompt: prompts/coder.md
  reviewer_prompt: prompts/reviewer.md
rulebase:
  path: .evo/memory/rulebase.md
```

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
```

The repository-level event log is `.evo/events.jsonl`. Human review decisions can include a comment and next hint; those fields are recorded in history, events, and decision documents.

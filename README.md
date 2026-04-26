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

Project scripts may also write structured evaluator result files. The harness records any existing JSON object files in each cycle summary and history:

```yaml
result_files:
  correctness: results/correctness.json
  qor: results/qor.json
  perf: results/perf.json
  reward: results/reward.json
```

These files are adapter-owned. For ABC-style work, `correctness.json` can summarize equivalence checks, `qor.json` can store area/depth/runtime deltas, and `reward.json` can store the final scalar or gate decision.

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

## Explicit Promotion

Accepted or kept candidates are committed on their candidate branch, but are not promoted automatically. Promote a reviewed cycle explicitly:

```bash
evo promote --config examples/abc/evo.yaml --cycle 1
```

Rejected cycles cannot be promoted. For pooled runs, pass `--candidate N`. Promotion uses a fast-forward merge into the configured champion branch and records a promote event in `.evo/history.jsonl`.

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
evaluator_results.json
```

The repository-level event log is `.evo/events.jsonl`. Human review decisions can include a comment and next hint; those fields are recorded in history, events, and decision documents.

## Code Understanding Memory

Seed hierarchical code memory before long-running evolution:

```bash
evo understand --config examples/abc/evo.yaml
evo understand --config examples/abc/evo.yaml --agent
```

This writes deterministic memory under `.evo/memory/code/`, including module summaries for allowed paths and workflow notes for build, regression, benchmark, and reward commands. Use `--agent` to ask Codex to enrich `.evo/memory/code/agent_notes.md` while preserving deterministic memory as the baseline.

## Read-Only GUI

Serve a local dashboard over `.evo` artifacts:

```bash
evo gui --config examples/abc/evo.yaml --host 127.0.0.1 --port 8765
```

The GUI displays workflow state, history, events, run documents, roadmap, and code-memory index. It can also add session comments, pause/resume the daemon, and explicitly promote accepted candidates through the same file-backed APIs as the CLI.

## Agent Session Registry

`evo-harness` keeps framework-level agent state even when the underlying Codex CLI cannot reliably resume externally supplied sessions:

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
      on_missing: new
      on_resume_failure: new
```

When a session id exists, the harness tries `codex exec resume`. If it is missing or resume fails and the policy is `new`, the role starts a new Codex invocation and records the event under `.evo/agents/<agent_id>/codex_session_events.jsonl`.

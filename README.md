# evo-harness

Minimal local evolution harness for EDA projects.

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

Human review can accept, reject, or keep an all-gates-passed candidate. It does not bypass build, regression, performance, reward, or patch guards.

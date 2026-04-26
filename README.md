# AutoEvoEDA

## 1. Basic Features

`AutoEvoEDA` (Autonomous Evolutive EDA) is a minimal local evolution harness for EDA projects, inspired by *Autonomous Evolution of EDA Tools: Multi-Agent Self-Evolved ABC* (arXiv:2604.15082v1). It is designed for Codex + GPT-style local coding agents.

Core contract:

```text
Codex proposes patches.
Project scripts judge correctness and performance.
The harness manages worktrees, guards, logs, memory, and accept/reject history.
```

What the framework provides:

- Candidate worktrees and candidate branches, including optional multi-repo workspaces.
- Patch scope guards with allowed/forbidden paths.
- Script-based gates for build, regression, compare, performance, and reward.
- Run artifacts under `.evo/runs/<run_id>/`.
- JSONL history/events, human comments, pause/resume, explicit promotion, and local GUI.
- Optional planner/reviewer/repair/domain-agent scaffolding and code-understanding memory.

What each project provides:

- `evo.yaml`
- prompts under `prompts/`
- adapter scripts under `scripts/`
- project-specific correctness, QoR, performance, and reward logic
- optional Codex model/profile/config overrides in `agent`

`AutoEvoEDA` never trusts the agent to decide correctness or performance.

For the full design, paper-alignment notes, agent model, and advanced commands, see `DETAILS.md`.

Status: alpha. The framework commands and example config have basic local validation, but a real project adapter has not yet been end-to-end tested. Treat the example scripts as placeholders until you provide project-specific build, regression, performance, and reward scripts.

## 2. How To Run

### Recommended:

ask Codex to use the repo-level Skill when adapting a project, installing AutoEvoEDA, or preparing a run:

```text
Use $autoevoeda-adapter to create or update an AutoEvoEDA adapter for this project, then show me the install and run commands.
```

The Skill explains the expected workspace layout, `evo.yaml`, adapter scripts, memory files, single-repo or multi-repo worktrees, runner preflights, and `evo` commands.

### Manual:

Install locally from this repository:

```bash
pip install -e .
```

Validate the example adapter configs:

```bash
evo config validate --config examples/abc/evo.yaml
evo config validate --config examples/multi_repo/evo.yaml
```

Seed code-understanding memory before long runs:

```bash
evo understand --config examples/abc/evo.yaml
```

Run one local evolution cycle:

```bash
evo run --config examples/abc/evo.yaml --cycles 1
```

Inspect generated artifacts:

```bash
ls .evo/runs/
evo report --config examples/abc/evo.yaml
```

If a run is interrupted before a final decision, inspect `.evo/runs/<run_id>/state.json` and explicitly abandon it before scheduling new work:

```bash
evo run --config examples/abc/evo.yaml --abandon-active --cycles 0
```

Optional long-running loop:

```bash
evo daemon --config examples/abc/evo.yaml --max-cycles 10 --sleep-s 30
evo session comment --config examples/abc/evo.yaml "focus on one small safe improvement"
evo session pause --config examples/abc/evo.yaml
evo session resume --config examples/abc/evo.yaml
```

Optional GUI:

```bash
evo gui --config examples/abc/evo.yaml --host 127.0.0.1 --port 8765
```

Important: `examples/abc/` uses placeholder adapter scripts. A real project must provide its own build, regression/CEC, QoR/performance, comparison, and reward scripts.

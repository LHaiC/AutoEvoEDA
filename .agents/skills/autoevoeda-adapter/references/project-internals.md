# AutoEvoEDA Project Internals

Read this before editing the AutoEvoEDA framework code. Keep framework changes small: each module has one owner role, and project-specific EDA logic belongs in adapters, not in `autoevoeda/`.

## Package Map

- `autoevoeda/cli.py`: CLI parser and command dispatch. Add new user commands here only after implementing behavior elsewhere.
- `autoevoeda/config.py`: strict `evo.yaml` schema dataclasses and `load_config()`. Add fields here first when changing config shape.
- `autoevoeda/pipeline/cycle.py`: candidate lifecycle and accept/reject control flow. Owns planner, domain-agent selection, coder, guard, reviewer, commit, pipeline gates, repair, evaluator snapshot, human review, checkpoint, and abandon-active sequencing.
- `autoevoeda/artifacts.py`: `.evo/` artifact APIs. Owns run directories, events, history, phase docs, reports, session state, active-run marker, agent registry, rule proposals, promotion, compare, and worktree cleanup helpers.
- `autoevoeda/agents/codex.py`: Codex CLI subprocess backend and optional native resume call path.
- `autoevoeda/memory.py`: prompt assembly and durable lesson injection.
- `autoevoeda/understand.py`: deterministic code-understanding memory and optional understanding-agent enrichment.
- `autoevoeda/daemon.py`: long-running loop, daemon lock, heartbeat, pause/resume checks, and consecutive-reject stop.
- `autoevoeda/human.py`: terminal human checkpoint prompts.
- `autoevoeda/gui.py`: local read/control dashboard over `.evo` files.
- `autoevoeda/workspace/git.py`: git subprocess wrapper, single-repo worktree creation, multi-repo candidate workspace creation, changed-file accounting, candidate commits.
- `autoevoeda/workspace/guard.py`: single-repo and multi-repo patch scope plus suspicious-pattern guard.

## Main Data Flow

```text
evo CLI
  -> load_config(evo.yaml)
  -> create single-repo worktree or multi-repo candidate workspace
  -> optional planner / domain-agent selection
  -> Codex edits candidate worktree
  -> patch guard checks allowed/forbidden paths and size
  -> optional reviewer advisory pass
  -> commit candidate branch
  -> build, regression, compare_regression, perf, reward scripts
  -> collect result_files JSON objects
  -> optional human review
  -> append history/events/phase docs and clear active run
```

Promotion is separate: `evo promote` fast-forwards the configured champion branch after an accepted or kept candidate is reviewed.

## `.evo/` State Model

- `.evo/runs/<run_id>/`: `00_context.md`, `01_propose.md`, `02_implement.md`, `03_benchmark.md`, `04_decision.md`, command stdout/stderr, `patch.diff`, `events.jsonl`, `evaluator_results.json`, `state.json`, `reproducibility.json`.
- `.evo/events.jsonl`: global event stream.
- `.evo/history.jsonl`: final candidate decisions and promotion records.
- `.evo/session/state.json`: `running` or `paused`.
- `.evo/session/active_run.json`: interrupt-safe active checkpoint; new work must refuse to start until abandoned or cleared.
- `.evo/agents/<session_id>/`: role memory, transcript, last prompt, last response, optional Codex session events.
- `.evo/memory/`: project memory, lessons, rejected ideas, accepted patterns, rulebase, and code-understanding docs.

## Config Ownership

`config.py` maps `evo.yaml` into frozen dataclasses. Current schema sections are:

```text
project, agent, workspace, guards, pipeline, result_files, memory, human,
repair, roles, rulebase, pool, budget, agents, domain_agents, multi_agent,
promotion
```

If `domain_agents` is non-empty, config validation requires `multi_agent.planner: true` and `roles.planner_prompt`.

## Agent Model

- `planner`: optional role before coding; its stdout can select a domain agent by exactly one `agent: <name>` line.
- `coder`: default required code-edit role.
- `domain_agents`: optional specialist coders with their own prompt, session id, allowed paths, forbidden paths, and proposal requirements.
- `reviewer`: optional advisory pass after guard and before gates; never replaces evaluator scripts.
- `repair`: optional bounded pass after failed gates.
- `rulebase`: file-backed rule proposal identity with explicit accept/reject commands.
- `code_understanding`: optional role used by `evo understand --agent`.

Domain-agent Codex output must include `hypothesis:`, `target_files:`, `expected_metric_impact:`, and `rollback_risk:` so `cycle.py` can write `agent_proposal.json` and `agent_proposal.md`.

## Safety Invariants

- Do not put ABC-specific or project-specific metric logic in `autoevoeda/`; adapters own scripts and reward formulas.
- Do not let agent output decide correctness or performance; only configured scripts and result files do.
- Keep promotion explicit; accept/keep records do not merge into champion automatically.
- Keep interrupted-run handling explicit; active checkpoints block new scheduling until abandoned.
- Keep evaluator scripts, benchmark data, golden outputs, CI, and config outside candidate edit scope by default.
- Avoid broad fallback behavior. Prefer deterministic failure with a clear reason.

## Verification For Framework Edits

Run the smallest relevant checks, usually:

```bash
python3 -m compileall autoevoeda
python3 -m autoevoeda.cli --help
python3 -m autoevoeda.cli config validate --config examples/abc/evo.yaml
git diff --check
```

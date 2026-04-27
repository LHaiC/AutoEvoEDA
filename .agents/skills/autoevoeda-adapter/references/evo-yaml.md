# evo.yaml Pattern

Use `schema_version: "1.0"`. Keep values concrete and project-owned.

```yaml
schema_version: "1.0"

project:
  name: project.logic
  repo: .
  champion_branch: evo-champion

agent:
  prompt_file: prompts/coder.md
  timeout_s: 3600
  sandbox: workspace-write
  model: ""
  profile: ""
  config: {}

runner:
  sandbox: workspace-write
  preflight: ""

workspace:
  mode: single_repo
  worktree_root: ../.evo-worktrees

guards:
  max_changed_files: 8
  max_changed_lines: 600
  allowed_paths:
    - src/
  forbidden_paths:
    - evo.yaml
    - scripts/
    - .github/
    - benchmarks/
    - golden/
    - results/

pipeline:
  build: bash scripts/build.sh
  regression: bash scripts/run_regression.sh
  compare_regression: python scripts/compare_regression.py
  perf: bash scripts/run_perf.sh
  reward: python scripts/reward.py

result_files:
  correctness: results/correctness.json
  qor: results/qor.json
  perf: results/perf.json
  reward: results/reward.json

memory:
  enabled: true
  project_memory: .evo/memory/project.md
  lessons: .evo/memory/lessons.jsonl
  rejected_ideas: .evo/memory/rejected_ideas.jsonl
  accepted_patterns: .evo/memory/accepted_patterns.md
  inject_recent_cycles: 5

human:
  review_on_accept: false
  stop_after_consecutive_rejects: 0

repair:
  enabled: false
  max_attempts: 1
  prompt_file: prompts/repair.md

roles:
  planner_prompt: prompts/planner.md
  coder_prompt: prompts/coder.md
  reviewer_prompt: prompts/reviewer.md

rulebase:
  path: .evo/memory/rulebase.md

pool:
  enabled: false
  size: 1

multi_agent:
  planner: false
  reviewer: false

budget:
  max_cycles: 0
  max_candidates: 0

promotion:
  require_clean_champion: true

understanding:
  phases: [scaffold, profile, relationships, guidance, role_memory, review]
  mutable_files:
    - .evo/roadmap.md
    - .evo/memory/project.md
    - .evo/memory/accepted_patterns.md
    - .evo/memory/rulebase.md
  read_only_context: []
  profile_docs:
    - .evo/memory/code/profile/repository.md
  relationship_docs:
    - .evo/memory/code/relationships/callgraph.md
    - .evo/memory/code/relationships/dataflow.md
    - .evo/memory/code/relationships/interfaces.md
    - .evo/memory/code/relationships/validation_loop.md
  guidance_docs:
    - .evo/memory/guidance/programming_guidance.md
    - .evo/memory/guidance/forbidden_rules.md
    - .evo/memory/guidance/validation.md
  review_docs:
    - .evo/memory/code/review/understanding_review.md
    - .evo/memory/code/review/coverage.json

agents:
  planner:
    session_id: planner-main
  coder:
    session_id: coder-main
  reviewer:
    session_id: reviewer-main
  repair:
    session_id: repair-main
  rulebase:
    session_id: rulebase-main
  code_understanding:
    session_id: understand-main
```

`scaffold` writes `.evo/memory/code/coverage.json` and `.evo/memory/code/understanding_targets.json` from `understanding`. The target docs themselves are agent-owned and should not exist as scaffold placeholders.

## Multi-Repo Workspaces

For sibling git repositories, use `workspace.mode: multi_repo`; see `multi-repo-workspace.md`. In that mode, `workspace.repos[*].allowed_paths` are local to each child repo and `guards.allowed_paths` should use candidate-root paths such as `mapper/src/`.

## Agent Model Selection

Leave `agent.model`, `agent.profile`, and `agent.config` empty to use the user's Codex defaults. To make an adapter reproducible, set generic Codex CLI overrides without embedding machine-local provider names in public examples:

```yaml
agent:
  model: gpt-5.5
  profile: ""
  config:
    model_reasoning_effort: high
```

`agent.config` maps to repeated `codex exec --config key=value` arguments and should contain scalar or list values. `agent.profile` applies to fresh `codex exec`; native `codex exec resume` does not currently expose `--profile`, so put resume-critical options in `agent.config`. If resume fails, AutoEvoEDA records `resume_failed_new` and starts a fresh invocation using file-backed memory.

## Runner Contract

`agent.sandbox` controls the Codex code-editing agent. `runner.sandbox` describes the expected evaluator/pipeline environment and is recorded in artifacts; it cannot escape a restricted parent process. Use `runner.sandbox: danger-full-access` with a `runner.preflight` command when CUDA-only benchmark scripts need host NVIDIA device access.

## Domain Agents

Use domain agents when one planner should route work to stable specialist identities. If `domain_agents` is non-empty, set `multi_agent.planner: true` and `roles.planner_prompt`.

```yaml
multi_agent:
  planner: true
  reviewer: true

domain_agents:
  - name: flow
    session_id: flow-main
    prompt_file: prompts/flow.md
    allowed_paths:
      - src/flow/
    forbidden_paths:
      - src/flow/golden/
  - name: mapper
    session_id: mapper-main
    prompt_file: prompts/mapper.md
    allowed_paths:
      - src/map/
  - name: logic
    session_id: logic-main
    prompt_file: prompts/logic.md
    allowed_paths:
      - src/logic/
```

Planner prompt requirement: the planner must emit exactly one line `agent: <name>`. Domain-agent responses must include `hypothesis:`, `target_files:`, `expected_metric_impact:`, and `rollback_risk:`.

## Native Codex Resume

Native Codex resume is optional. Only enable it when the local Codex CLI supports the configured resume path.

```yaml
agents:
  coder:
    session_id: coder-main
    codex_session:
      enabled: true
      session_file: .evo/agents/coder-main/codex_session.txt
```

---
name: autoevoeda-adapter
description: >
  Create or update an AutoEvoEDA project adapter. Handles workspace layout,
  required prompts/scripts/memory files, evo.yaml multi-agent configuration,
  and evo CLI usage for long-running EDA evolution workflows. Use when asked
  to adapt a project to AutoEvoEDA, create multi-agent YAML, explain the evo
  workflow, lay out adapter scripts and artifacts, or modify this framework
  codebase.
argument-hint: "<project-repo> [goal-or-domain-agents]"
---

# Create AutoEvoEDA Adapter

You are creating or updating an AutoEvoEDA adapter for: **$ARGUMENTS**.

## 1. Inspect the project

If the task edits the AutoEvoEDA framework itself, read `references/project-internals.md` first.

Identify concrete project facts before writing config:

- whether the project is a single git repo or a multi-repo workspace
- source paths that candidate agents may edit
- immutable evaluator assets, golden data, benchmark definitions, and CI files
- build command, regression/equivalence command, performance/QoR command, and reward rule
- useful domain-agent split, such as flow, mapper, logic, timing, routing, or placer

Do not invent working benchmark logic. Use explicit placeholders when project scripts are not provided.

## 2. Build the adapter layout

Read `references/layout-and-files.md`, then create or update:

```text
evo.yaml
prompts/{planner,coder,reviewer,repair}.md
scripts/{build.sh,run_regression.sh,compare_regression.py,run_perf.sh,reward.py}
```

Optional domain agents get one prompt each, for example `prompts/mapper.md`.

## 3. Write evo.yaml

Read `references/evo-yaml.md`. For sibling-repo workspaces, also read `references/multi-repo-workspace.md`. Keep values concrete and project-owned:

- `guards.allowed_paths` contains implementation scopes only.
- `guards.forbidden_paths` includes evaluator scripts, config, generated results, benchmark/golden assets, and CI.
- Leave `agent.model/profile/config` empty in public examples unless reproducibility requires generic Codex overrides.
- `agent.sandbox` is for Codex code editing; `runner.sandbox` is for evaluator/pipeline requirements and should be paired with `runner.preflight` for CUDA-only runs.
- `domain_agents` requires `multi_agent.planner: true` and `roles.planner_prompt`.
- Stable `session_id` values are framework-level memory identities; native Codex resume is opt-in.

## 4. Explain commands and state

Read `references/commands.md` before explaining how to run, continue, non-stop daemon mode, pause, resume, inspect `.evo/`, or promote candidates.

## 5. Framework edits

When changing framework behavior, keep patches small and update the narrow module that owns the behavior. Use `references/project-internals.md` to find the owner before editing.

## 6. Verify

Run or recommend the narrowest safe verification:

```bash
evo config validate --config evo.yaml
```

If editing the AutoEvoEDA framework itself, also run:

```bash
python3 -m compileall autoevoeda
python3 -m autoevoeda.cli --help
```

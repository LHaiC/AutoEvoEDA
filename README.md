# AutoEvoEDA

**AutoEvoEDA** is an alpha local evolution harness for EDA projects, inspired by the paper:

> **Autonomous Evolution of EDA Tools: Multi-Agent Self-Evolved ABC**
> Cunxi Yu and Haoxing Ren, DAC 2026
> arXiv:2604.15082
> https://arxiv.org/abs/2604.15082

This repository is an unofficial framework-level implementation. It focuses on reusable local orchestration: project adapters, guarded candidate worktrees, agent calls, evaluator gates, run logs, memory, human comments, and explicit promotion.

Status: alpha. It is not a complete reproduction of the paper's ABC experiments or QoR results.

## 1. Basic Features

- Local `evo run` cycles over single-repo or multi-repo candidate worktrees.
- Patch guards for allowed/forbidden paths and patch size.
- Project-owned build, regression, performance, comparison, and reward scripts.
- `.evo/` history, events, run artifacts, agent exchanges, lessons, rule proposals, and reports.
- Optional understanding workflow, planner/reviewer/repair roles, human controls, and local GUI.

Project adapters provide `evo.yaml`, prompts, scripts, and project-specific evaluator logic. AutoEvoEDA never trusts the coding agent to decide correctness or performance.

## 2. How To Run

**Recommended:** ask Codex to use the repo-level Skill when adapting a project, installing AutoEvoEDA, or preparing a run.

```text
Use $autoevoeda-adapter to create or update an AutoEvoEDA adapter for this project, then show me the install and run commands.
```

The Skill covers workspace layout, `evo.yaml`, adapter scripts, memory files, single-repo and multi-repo worktrees, runner preflights, long-running controls, and `evo` commands.

For manual details, see:

- `DETAILS.md` for design, command reference, config examples, and paper-alignment notes.
- `.agents/skills/autoevoeda-adapter/SKILL.md` for the adapter workflow.
- `examples/ghypart/run_understand_2cycles.sh` for a public gHyPart smoke script.

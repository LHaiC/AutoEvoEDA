# evo Commands And Meaning

Install the framework from the framework repo:

```bash
pip install -e .
```

Validate an adapter config:

```bash
evo config validate --config evo.yaml
```

Run pre-evolution understanding:

```bash
evo understand --config evo.yaml
evo understand --config evo.yaml --phase scaffold
evo understand --config evo.yaml --phase profile
evo understand --config evo.yaml --module src/map/ --changed-only
```

`--phase scaffold` only writes manifests, raw file indexes, and `.evo/memory/code/understanding_targets.json`. It must not create fake profile, guidance, relationship, role-memory, or review documents. Those files are Codex-owned and must be created or edited by the non-scaffold phases. For `workspace.mode: multi_repo`, `evo understand` scans child repos from `workspace.source_root/<repo.path>` and scans configured non-repo assets from `workspace.materialize` or non-repo `guards.allowed_paths`.

Run local evolution:

```bash
evo run --config evo.yaml --cycles 1
evo run --config evo.yaml --cycles 5 --human-review
```

After each agent call, inspect concise shared context with:

```bash
cat .evo/brief.md
tail -n 20 .evo/memory/lessons.jsonl
tail -n 20 .evo/agents/interactions.jsonl
```

Run a file-controlled long loop:

```bash
evo daemon --config evo.yaml --max-cycles 10 --sleep-s 30
evo daemon --config evo.yaml --non-stop --sleep-s 60
evo session status --config evo.yaml
evo session comment --config evo.yaml "steering note"
evo session pause --config evo.yaml
evo session resume --config evo.yaml
```

For tmux/system supervision, copy the bundled script and edit only adapter-local paths if needed:

```bash
cp .agents/skills/autoevoeda-adapter/scripts/evo_nonstop_supervisor.sh scripts/
AUTOEVO_ADAPTER_ROOT="$PWD" AUTOEVO_PROJECT_ROOT="$PWD" scripts/evo_nonstop_supervisor.sh
```

Set `AUTOEVO_REQUIRE_CUDA=1` when the adapter has a hard CUDA preflight script. Set `AUTOEVO_UNDERSTAND_PHASES="scaffold profile"` for a short bootstrap, or leave it unset for the full alpha understanding sequence.

Inspect and report:

```bash
evo report --config evo.yaml
evo compare --config evo.yaml --cycle 1
evo gui --config evo.yaml --host 127.0.0.1 --port 8765
```

Promotion is explicit:

```bash
evo promote --config evo.yaml --cycle 1
```

Worktrees are explicit:

```bash
evo worktree list --config evo.yaml
evo worktree cleanup --config evo.yaml --rejected
```

Interrupt handling is explicit. If a run stops with an active checkpoint and no final decision, inspect `.evo/runs/<run_id>/state.json`, then continue for the requested number of cycles:

```bash
evo run --config evo.yaml --continue --cycles 1
```

`--continue` also resumes a paused session before scheduling. `--non-stop` means run until manually paused; it is not an exception-swallowing recovery.

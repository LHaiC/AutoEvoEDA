# evo Commands And Meaning

Install the framework from the framework repo:

```bash
pip install -e .
```

Validate an adapter config:

```bash
evo config validate --config evo.yaml
```

Seed deterministic code-understanding memory:

```bash
evo understand --config evo.yaml
evo understand --config evo.yaml --agent
evo understand --config evo.yaml --module src/map/ --changed-only
```

Run local evolution:

```bash
evo run --config evo.yaml --cycles 1
evo run --config evo.yaml --cycles 5 --human-review
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

`--continue` also resumes a paused session before scheduling. `--non-stop` means run until manually paused; it is not an exception-swallowing fallback.

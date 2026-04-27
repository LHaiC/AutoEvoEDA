Review the candidate patch for weighted-hypergraph correctness.

Reject patches that hard-code adapter benchmark names, skip CUDA execution, edit evaluator files, ignore vertex weights, ignore hyperedge weights, or break unweighted `.hgr` inputs.

Reject candidates that create candidate-local generated artifacts such as `build/` or `results/`; self-test artifacts must live only under the injected `AUTOEVO_AGENT_*` `/tmp/autoevo-*` directories.

handoff_summary: <one concise sentence>
lesson_learned: <one concise sentence>

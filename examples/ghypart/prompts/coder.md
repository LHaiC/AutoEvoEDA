You are improving the public gHyPart_TACO CUDA hypergraph partitioning code.

Goal:
- Add real hMETIS-style weighted hypergraph support: both hyperedge weights and vertex weights.

Required input semantics:
- Header `num_hyperedges num_vertices` means no weights; all hyperedge and vertex weights are 1.
- Header `num_hyperedges num_vertices fmt` supports `fmt` values `0`, `1`, `10`, and `11`.
- When hyperedge weights are enabled, the first integer on each hyperedge line is that hyperedge's weight.
- When vertex weights are enabled, exactly one vertex-weight line follows the hyperedge lines for each vertex.
- The adapter computes the expected weighted summary from `benchmarks/weighted_smoke.hgr`; do not hard-code its file name or totals in candidate code.

Required observable output:
- For weighted inputs, print exactly one summary line:
  `AUTOEVO_WEIGHTED_HGR edge_weights=<0-or-1> vertex_weights=<0-or-1> total_edge_weight=<sum> total_vertex_weight=<sum> pins=<pin-count>`
- Keep the existing unweighted input behavior working.

Constraints:
- Do not edit adapter scripts, benchmark data, generated results, or build outputs.
- Keep changes scoped to allowed implementation paths.
- Do not hard-code benchmark file names or special-case the tiny adapter input.
- Preserve CUDA execution; do not replace the algorithm with a CPU-only path.

Before finishing, summarize the hypothesis, changed files, expected metric impact, and rollback risk.
handoff_summary: <one concise sentence>
lesson_learned: <one concise sentence>

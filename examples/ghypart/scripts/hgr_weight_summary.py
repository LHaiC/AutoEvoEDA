from __future__ import annotations

from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = [line.split() for line in path.read_text().splitlines() if line.strip()]
hedges = int(lines[0][0])
nodes = int(lines[0][1])
fmt = int(lines[0][2]) if len(lines[0]) > 2 else 0
edge_weights = fmt % 10 == 1
vertex_weights = (fmt // 10) % 10 == 1
pin_count = 0
edge_weight_total = 0
for tokens in lines[1 : 1 + hedges]:
    values = [int(token) for token in tokens]
    edge_weight_total += values[0] if edge_weights else 1
    pin_count += len(values) - (1 if edge_weights else 0)
vertex_rows = lines[1 + hedges : 1 + hedges + nodes]
vertex_weight_total = sum(int(row[0]) for row in vertex_rows) if vertex_weights else nodes
print(
    f"AUTOEVO_WEIGHTED_HGR edge_weights={int(edge_weights)} vertex_weights={int(vertex_weights)} "
    f"total_edge_weight={edge_weight_total} total_vertex_weight={vertex_weight_total} pins={pin_count}"
)

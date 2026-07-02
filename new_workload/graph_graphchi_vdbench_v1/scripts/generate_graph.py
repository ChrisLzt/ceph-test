#!/usr/bin/env python3
"""Generate a deterministic directed graph for GraphChi PSW profile derivation.

The graph is not claimed to be a production graph. It is a controlled input
dataset whose edge list is later converted into vdbench skew values by applying
GraphChi's Parallel Sliding Windows read rules.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def emit_edges(intervals: int, vertices_per_interval: int) -> list[tuple[int, int]]:
    total_vertices = intervals * vertices_per_interval
    edges: list[tuple[int, int]] = []

    for src in range(total_vertices):
        src_interval = src // vertices_per_interval
        local_base = src_interval * vertices_per_interval

        # Community-local edges make each interval's memory shard visible.
        for offset in (1, 3, 7, 11, 17, 23, 31, 43):
            dst = local_base + ((src + offset) % vertices_per_interval)
            edges.append((src, dst))

        # Deterministic cross-interval edges create non-zero sliding windows.
        next_interval = (src_interval + 1) % intervals
        prev_interval = (src_interval - 1) % intervals
        far_interval = (src_interval + 2) % intervals

        for offset in (5, 19):
            dst = next_interval * vertices_per_interval + ((src * 3 + offset) % vertices_per_interval)
            edges.append((src, dst))

        dst = prev_interval * vertices_per_interval + ((src * 5 + 13) % vertices_per_interval)
        edges.append((src, dst))

        dst = far_interval * vertices_per_interval + ((src * 7 + 29) % vertices_per_interval)
        edges.append((src, dst))

    return edges


def write_edges(path: Path, intervals: int, vertices_per_interval: int, edges: list[tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# generated graph for graph_graphchi_vdbench_v1\n")
        handle.write("# columns: src_vertex dst_vertex\n")
        handle.write(f"# intervals={intervals}\n")
        handle.write(f"# vertices_per_interval={vertices_per_interval}\n")
        handle.write("# generator=deterministic_community_with_cross_interval_edges\n")
        for src, dst in edges:
            handle.write(f"{src}\t{dst}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="datasets/smoke_edges.tsv")
    parser.add_argument("--intervals", type=int, default=4)
    parser.add_argument("--vertices-per-interval", type=int, default=128)
    args = parser.parse_args()

    if args.intervals < 2:
        raise SystemExit("--intervals must be at least 2")
    if args.vertices_per_interval < 1:
        raise SystemExit("--vertices-per-interval must be positive")

    edges = emit_edges(args.intervals, args.vertices_per_interval)
    write_edges(Path(args.output), args.intervals, args.vertices_per_interval, edges)
    print(
        f"generated {len(edges)} edges: {args.output}; "
        f"intervals={args.intervals}; vertices_per_interval={args.vertices_per_interval}"
    )


if __name__ == "__main__":
    main()

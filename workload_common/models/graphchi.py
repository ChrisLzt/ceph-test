"""GraphChi-inspired shard rotation with shard-local Zipf ranks."""

from __future__ import annotations

from pathlib import Path

from workload_common.layout import Bucket, Layout
from workload_common.models.common import (
    Profile,
    append_profile_rd,
    make_group,
    ranked_profile,
    validate_render_args,
)
from workload_common.vdbench import config_header, render_fsd_lines, render_prepare_config, write_config


WORKLOAD = "graph_graphchi_vdbench_v1"
STAGES = (0, 1, 2, 3)
SHARD_UNITS = 600
RANK_COUNT = 100


def _build(
    layout: Layout,
    anchor_root: str,
) -> tuple[list[Bucket], dict[int, dict[int, list[Bucket]]]]:
    all_buckets: list[Bucket] = []
    grouped: dict[int, dict[int, list[Bucket]]] = {}
    for shard in STAGES:
        group = f"shard_{shard:02d}"
        buckets, ranks = make_group(
            layout=layout,
            anchor_root=anchor_root,
            workload=WORKLOAD,
            group=group,
            prefix=f"s{shard:02d}",
            units=SHARD_UNITS,
            ranks=RANK_COUNT,
            anchor_suffix=group,
        )
        all_buckets.extend(buckets)
        grouped[shard] = ranks
    return all_buckets, grouped


def _run_text(layout: Layout, buckets: list[Bucket], grouped: dict[int, dict[int, list[Bucket]]], *, hd_line: str | None, threads: int, phase_seconds: int, fwdrate: str) -> str:
    lines = config_header("GraphChi shard-local Zipf workload - run only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    rds: list[str] = []
    profiles: list[Profile] = [
        ranked_profile(
            layout,
            grouped[shard],
            SHARD_UNITS,
            RANK_COUNT,
            100,
        )
        for shard in STAGES
    ]
    names = [f"graph_shard_{shard:02d}" for shard in STAGES]
    for name, profile in zip(names, profiles):
        append_profile_rd(
            lines,
            rds,
            name=name,
            profile=profile,
            fileio="sequential",
            threads=threads,
            fwdrate=fwdrate,
            elapsed=phase_seconds,
        )
    lines.extend(rds)
    lines.append("")
    return "\n".join(lines)


def render(*, layout: Layout, anchor_root: str, output_dir: Path, hd_line: str | None = None, threads: int = 1, phase_seconds: int = 150, fwdrate: str = "max") -> None:
    validate_render_args(anchor_root=anchor_root, threads=threads, fwdrate=fwdrate, durations=(phase_seconds,))
    buckets, grouped = _build(layout, anchor_root)
    write_config(output_dir / "prepare_data.vdb", render_prepare_config("GraphChi shard-local Zipf workload", buckets, threads, hd_line=hd_line))
    write_config(output_dir / "run_test.vdb", _run_text(layout, buckets, grouped, hd_line=hd_line, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate))

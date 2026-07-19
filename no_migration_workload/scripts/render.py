#!/usr/bin/env python3
"""Render five run-only workloads whose rank distributions never migrate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from workload_common.layout import Bucket, RankSpans, SINGLE_LAYOUT, make_tail_rank_spans
from workload_common.models.common import (
    Profile,
    append_profile_rd,
    combine_profiles,
    make_group,
    ranked_profile,
    validate_render_args,
)
from workload_common.vdbench import config_header, render_fsd_lines, write_config


@dataclass(frozen=True)
class FixedGroup:
    name: str
    units: int
    weight: Decimal | int
    prefix: str | None = None
    anchor_suffix: str | None = None


@dataclass(frozen=True)
class FixedPhase:
    name: str
    seconds: int
    fileio: str


@dataclass(frozen=True)
class FixedWorkload:
    name: str
    title: str
    source_workload: str
    rank_count: int
    rank_spans: RankSpans
    groups: tuple[FixedGroup, ...]
    phases: tuple[FixedPhase, ...]


SPECS = {
    "bigdata_mapreduce_no_migration_v1": FixedWorkload(
        name="bigdata_mapreduce_no_migration_v1",
        title="MapReduce fixed hot_pool_01 control workload",
        source_workload="bigdata_mapreduce_vdbench_v1",
        rank_count=100,
        rank_spans=make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4),
        groups=(
            FixedGroup("pool_01", 100, Decimal("85.41")),
            FixedGroup("background", 2100, Decimal("14.59")),
        ),
        phases=(FixedPhase("fixed_pool01", 600, "sequential"),),
    ),
    "graph_graphchi_no_migration_v1": FixedWorkload(
        name="graph_graphchi_no_migration_v1",
        title="GraphChi fixed shard_00 control workload",
        source_workload="graph_graphchi_vdbench_v1",
        rank_count=100,
        rank_spans=make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4),
        groups=(FixedGroup("shard_00", 600, 100, prefix="s00"),),
        phases=(FixedPhase("fixed_shard00", 600, "sequential"),),
    ),
    "hpc_wrf_no_migration_v1": FixedWorkload(
        name="hpc_wrf_no_migration_v1",
        title="WRF fixed startup control workload",
        source_workload="hpc_wrf_vdbench_v1",
        rank_count=100,
        rank_spans=make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4),
        groups=(FixedGroup("startup", 800, 100),),
        phases=(FixedPhase("fixed_startup", 600, "sequential"),),
    ),
    "ai_training_no_migration_v1": FixedWorkload(
        name="ai_training_no_migration_v1",
        title="AI training fixed dataset control workload",
        source_workload="ai_training_checkpoint_vdbench_v1",
        rank_count=100,
        rank_spans=make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4),
        groups=(FixedGroup("dataset", 2000, 100),),
        phases=(
            FixedPhase("fixed_dataset_epoch_01", 160, "random"),
            FixedPhase("fixed_dataset_epoch_02", 160, "random"),
            FixedPhase("fixed_dataset_epoch_03", 160, "random"),
            FixedPhase("fixed_dataset_checkpoint_slot", 60, "sequential"),
            FixedPhase("fixed_dataset_recovery_slot", 60, "sequential"),
        ),
    ),
    "ai_inference_no_migration_v1": FixedWorkload(
        name="ai_inference_no_migration_v1",
        title="AI inference fixed kv_active control workload",
        source_workload="ai_inference_kvcache_vdbench_v1",
        rank_count=100,
        rank_spans=make_tail_rank_spans(100, head_rank_count=20, tail_group_size=4),
        groups=(FixedGroup("kv_active", 800, 100),),
        phases=(
            FixedPhase("fixed_active_prefill_01", 100, "sequential"),
            FixedPhase("fixed_active_decode_01", 100, "random"),
            FixedPhase("fixed_active_prefill_02", 100, "sequential"),
            FixedPhase("fixed_active_decode_02", 100, "random"),
            FixedPhase("fixed_active_prefix_01", 100, "random"),
            FixedPhase("fixed_active_prefix_02", 100, "random"),
        ),
    ),
}


def _fixed_profile(spec: FixedWorkload, anchor_root: str) -> tuple[list[Bucket], Profile]:
    buckets: list[Bucket] = []
    profiles: list[Profile] = []
    for group in spec.groups:
        group_buckets, ranks = make_group(
            layout=SINGLE_LAYOUT,
            anchor_root=anchor_root,
            workload=spec.source_workload,
            group=group.name,
            prefix=group.prefix or group.name,
            units=group.units,
            ranks=spec.rank_count,
            rank_spans=spec.rank_spans,
            anchor_suffix=group.anchor_suffix,
        )
        buckets.extend(group_buckets)
        profiles.append(
            ranked_profile(
                SINGLE_LAYOUT,
                ranks,
                group.units,
                spec.rank_count,
                Decimal(group.weight),
                hot_rank=1,
                rank_spans=spec.rank_spans,
            )
        )
    return buckets, combine_profiles(*profiles)


def render(
    *,
    workload: str,
    anchor_root: str,
    output_dir: Path,
    hd_line: str | None,
    threads: int = 1,
    fwdrate: str = "max",
) -> None:
    try:
        spec = SPECS[workload]
    except KeyError as error:
        raise ValueError(f"unknown no-migration workload: {workload}") from error
    validate_render_args(
        anchor_root=anchor_root,
        threads=threads,
        fwdrate=fwdrate,
        durations=tuple(phase.seconds for phase in spec.phases),
    )
    buckets, profile = _fixed_profile(spec, anchor_root)
    lines = config_header(f"{spec.title} - run only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    rds: list[str] = []
    fwd_sets_by_fileio: dict[str, str] = {}
    for phase in spec.phases:
        existing_set = fwd_sets_by_fileio.get(phase.fileio)
        fwd_set_name = existing_set or phase.name
        append_profile_rd(
            lines,
            rds,
            name=phase.name,
            profile=profile,
            fileio=phase.fileio,
            threads=threads,
            fwdrate=fwdrate,
            elapsed=phase.seconds,
            fwd_set_name=fwd_set_name,
            define_fwd=existing_set is None,
        )
        fwd_sets_by_fileio.setdefault(phase.fileio, fwd_set_name)
    lines.extend(rds)
    lines.append("")
    write_config(output_dir / "run_test.vdb", "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render one run-only fixed-hotspot Vdbench workload."
    )
    parser.add_argument("--workload", choices=tuple(SPECS), required=True)
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hd-line")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(**vars(args))


if __name__ == "__main__":
    main()

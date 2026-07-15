"""Paper-derived MapReduce pool model with file-level Zipf ranks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from workload_common.layout import Bucket, Layout
from workload_common.models.common import (
    Profile,
    append_profile_rd,
    combine_profiles,
    make_group,
    ranked_profile,
    validate_render_args,
)
from workload_common.vdbench import config_header, render_fsd_lines, render_prepare_config, write_config


WORKLOAD = "bigdata_mapreduce_vdbench_v1"
GROUP_UNITS = {"pool_01": 96, "pool_02": 96, "pool_03": 96, "background": 2112}
GROUPS = tuple(GROUP_UNITS)
RANK_COUNT = 24


@dataclass(frozen=True)
class Stage:
    name: str
    weights: tuple[int, int, int, int]


STAGES = (
    Stage("hot_pool_01", (85, 1, 1, 13)),
    Stage("hot_pool_02", (1, 85, 1, 13)),
    Stage("hot_pool_03", (1, 1, 85, 13)),
    Stage("reheat_pool_01", (85, 1, 1, 13)),
)


def _build(layout: Layout, anchor_root: str) -> tuple[list[Bucket], dict[str, dict[int, list[Bucket]]]]:
    all_buckets: list[Bucket] = []
    grouped: dict[str, dict[int, list[Bucket]]] = {}
    for group, units in GROUP_UNITS.items():
        buckets, ranks = make_group(
            layout=layout,
            anchor_root=anchor_root,
            workload=WORKLOAD,
            group=group,
            prefix=group,
            units=units,
            ranks=RANK_COUNT,
        )
        all_buckets.extend(buckets)
        grouped[group] = ranks
    return all_buckets, grouped


def _run_text(layout: Layout, buckets: list[Bucket], grouped: dict[str, dict[int, list[Bucket]]], *, hd_line: str | None, threads: int, phase_seconds: int, fwdrate: str) -> str:
    lines = config_header("MapReduce pool-local Zipf workload - run only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    rds: list[str] = []
    profiles: list[Profile] = []
    for stage in STAGES:
        profiles.append(
            combine_profiles(
                *(
                    ranked_profile(
                        layout,
                        grouped[group],
                        GROUP_UNITS[group],
                        RANK_COUNT,
                        Decimal(weight),
                    )
                    for group, weight in zip(GROUPS, stage.weights)
                )
            )
        )
    for stage, profile in zip(STAGES, profiles):
        append_profile_rd(
            lines,
            rds,
            name=stage.name,
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
    write_config(output_dir / "prepare_data.vdb", render_prepare_config("MapReduce pool-local Zipf workload", buckets, threads, hd_line=hd_line))
    write_config(output_dir / "run_test.vdb", _run_text(layout, buckets, grouped, hd_line=hd_line, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate))

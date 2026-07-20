"""Paper-derived MapReduce pool model with file-level Zipf ranks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from workload_common.layout import Bucket, Layout, make_tail_rank_spans
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
GROUP_UNITS = {"pool_01": 100, "pool_02": 100, "pool_03": 100, "background": 2100}
GROUPS = tuple(GROUP_UNITS)
RANK_COUNT = 50
RANK_SPANS = make_tail_rank_spans(
    RANK_COUNT,
    head_rank_count=10,
    tail_group_size=4,
)
BIN_COUNT = len(RANK_SPANS)
HOT_SHARE = Decimal("85.41")
BACKGROUND_SHARE = Decimal("14.59")


@dataclass(frozen=True)
class Stage:
    name: str
    weights: tuple[Decimal, Decimal, Decimal, Decimal]


STAGES = (
    Stage("hot_pool_01", (HOT_SHARE, Decimal("0"), Decimal("0"), BACKGROUND_SHARE)),
    Stage("hot_pool_02", (Decimal("0"), HOT_SHARE, Decimal("0"), BACKGROUND_SHARE)),
    Stage("hot_pool_03", (Decimal("0"), Decimal("0"), HOT_SHARE, BACKGROUND_SHARE)),
    Stage("reheat_pool_01", (HOT_SHARE, Decimal("0"), Decimal("0"), BACKGROUND_SHARE)),
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
            rank_spans=RANK_SPANS,
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
                        rank_spans=RANK_SPANS,
                    )
                    for group, weight in zip(GROUPS, stage.weights)
                    if weight > 0
                )
            )
        )
    for index, (stage, profile) in enumerate(zip(STAGES, profiles)):
        reused_name = STAGES[0].name if index == len(STAGES) - 1 else stage.name
        append_profile_rd(
            lines,
            rds,
            name=stage.name,
            profile=profile,
            fileio="sequential",
            threads=threads,
            fwdrate=fwdrate,
            elapsed=phase_seconds,
            fwd_set_name=reused_name,
            define_fwd=index != len(STAGES) - 1,
        )
    lines.extend(rds)
    lines.append("")
    return "\n".join(lines)


def render(*, layout: Layout, anchor_root: str, output_dir: Path, hd_line: str | None = None, threads: int = 1, phase_seconds: int = 150, fwdrate: str = "max") -> None:
    validate_render_args(anchor_root=anchor_root, threads=threads, fwdrate=fwdrate, durations=(phase_seconds,))
    buckets, grouped = _build(layout, anchor_root)
    write_config(output_dir / "prepare_data.vdb", render_prepare_config("MapReduce pool-local Zipf workload", buckets, threads, hd_line=hd_line))
    write_config(output_dir / "run_test.vdb", _run_text(layout, buckets, grouped, hd_line=hd_line, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate))

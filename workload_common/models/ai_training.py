"""AI training dataset/checkpoint lifecycle with ranked file popularity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workload_common.layout import Bucket, Layout
from workload_common.models.common import (
    append_profile_rd,
    make_group,
    ranked_profile,
    validate_render_args,
)
from workload_common.vdbench import config_header, render_fsd_lines, render_prepare_config, write_config


WORKLOAD = "ai_training_checkpoint_vdbench_v1"
GROUP_UNITS = {"dataset": 2000, "checkpoint_current": 200, "checkpoint_old": 200}
RANK_COUNT = 100


@dataclass(frozen=True)
class Phase:
    name: str
    group: str
    seconds: int
    fileio: str
    hot_rank: int


PHASES = (
    Phase("dataset_epoch_01", "dataset", 160, "random", 1),
    Phase("dataset_epoch_02", "dataset", 160, "random", 2),
    Phase("dataset_epoch_03", "dataset", 160, "random", 3),
    Phase("checkpoint_read_current", "checkpoint_current", 60, "sequential", 1),
    Phase("recovery_read_old_checkpoint", "checkpoint_old", 60, "sequential", 1),
)


def _build(layout: Layout, anchor_root: str) -> tuple[list[Bucket], dict[str, dict[int, list[Bucket]]]]:
    all_buckets: list[Bucket] = []
    grouped: dict[str, dict[int, list[Bucket]]] = {}
    for group, units in GROUP_UNITS.items():
        buckets, ranks = make_group(layout=layout, anchor_root=anchor_root, workload=WORKLOAD, group=group, prefix=group, units=units, ranks=RANK_COUNT)
        all_buckets.extend(buckets)
        grouped[group] = ranks
    return all_buckets, grouped


def _run_text(layout: Layout, buckets: list[Bucket], grouped: dict[str, dict[int, list[Bucket]]], *, hd_line: str | None, threads: int, dataset_phase_seconds: int, checkpoint_phase_seconds: int, fwdrate: str) -> str:
    lines = config_header("AI training dataset/checkpoint Zipf workload - run only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    rds: list[str] = []
    profiles = [
        ranked_profile(
            layout,
            grouped[phase.group],
            GROUP_UNITS[phase.group],
            RANK_COUNT,
            100,
            hot_rank=phase.hot_rank,
        )
        for phase in PHASES
    ]
    for phase, profile in zip(PHASES, profiles):
        nominal = (
            dataset_phase_seconds
            if phase.group == "dataset"
            else checkpoint_phase_seconds
        )
        append_profile_rd(
            lines,
            rds,
            name=phase.name,
            profile=profile,
            fileio=phase.fileio,
            threads=threads,
            fwdrate=fwdrate,
            elapsed=nominal,
        )
    lines.extend(rds)
    lines.append("")
    return "\n".join(lines)


def render(*, layout: Layout, anchor_root: str, output_dir: Path, hd_line: str | None = None, threads: int = 1, dataset_phase_seconds: int = 160, checkpoint_phase_seconds: int = 60, fwdrate: str = "max") -> None:
    validate_render_args(
        anchor_root=anchor_root,
        threads=threads,
        fwdrate=fwdrate,
        durations=(
            dataset_phase_seconds,
            checkpoint_phase_seconds,
        ),
    )
    buckets, grouped = _build(layout, anchor_root)
    write_config(output_dir / "prepare_data.vdb", render_prepare_config("AI training dataset/checkpoint Zipf workload", buckets, threads, hd_line=hd_line))
    write_config(output_dir / "run_test.vdb", _run_text(layout, buckets, grouped, hd_line=hd_line, threads=threads, dataset_phase_seconds=dataset_phase_seconds, checkpoint_phase_seconds=checkpoint_phase_seconds, fwdrate=fwdrate))

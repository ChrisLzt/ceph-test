"""WRF lifecycle model with file-level Zipf ranks."""

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


WORKLOAD = "hpc_wrf_vdbench_v1"
GROUP_UNITS = {"startup": 800, "checkpoint": 800, "history": 800}
RANK_COUNT = 80


@dataclass(frozen=True)
class Phase:
    name: str
    group: str


PHASES = (
    Phase("startup_read", "startup"),
    Phase("checkpoint_read", "checkpoint"),
    Phase("history_read", "history"),
    Phase("checkpoint_reheat", "checkpoint"),
)


def _build(layout: Layout, anchor_root: str) -> tuple[list[Bucket], dict[str, dict[int, list[Bucket]]]]:
    all_buckets: list[Bucket] = []
    grouped: dict[str, dict[int, list[Bucket]]] = {}
    for group, units in GROUP_UNITS.items():
        buckets, ranks = make_group(layout=layout, anchor_root=anchor_root, workload=WORKLOAD, group=group, prefix=group, units=units, ranks=RANK_COUNT)
        all_buckets.extend(buckets)
        grouped[group] = ranks
    return all_buckets, grouped


def _run_text(layout: Layout, buckets: list[Bucket], grouped: dict[str, dict[int, list[Bucket]]], *, hd_line: str | None, threads: int, phase_seconds: int, fwdrate: str) -> str:
    lines = config_header("WRF lifecycle Zipf workload - run only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    rds: list[str] = []
    profiles = [
        ranked_profile(
            layout,
            grouped[phase.group],
            GROUP_UNITS[phase.group],
            RANK_COUNT,
            100,
        )
        for phase in PHASES
    ]
    for phase, profile in zip(PHASES, profiles):
        append_profile_rd(
            lines,
            rds,
            name=phase.name,
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
    write_config(output_dir / "prepare_data.vdb", render_prepare_config("WRF lifecycle Zipf workload", buckets, threads, hd_line=hd_line))
    write_config(output_dir / "run_test.vdb", _run_text(layout, buckets, grouped, hd_line=hd_line, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate))

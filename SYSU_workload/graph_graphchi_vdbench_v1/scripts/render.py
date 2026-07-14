#!/usr/bin/env python3
"""Render the 750 GiB SYSU GraphChi-derived Vdbench workload."""

from __future__ import annotations

import argparse
from pathlib import Path

from SYSU_workload.common.layout import Bucket, make_buckets, split_skew
from SYSU_workload.common.vdbench import (
    config_header,
    fwd_line,
    rd_line,
    render_fsd_lines,
    render_prepare_config,
    write_config,
)


WORKLOAD = "graph_graphchi_vdbench_v1"
SHARDS = tuple(f"shard_{index:02d}" for index in range(4))
STAGES = {
    "iter1_i0": (75, 13, 6, 6),
    "iter1_i1": (6, 75, 13, 6),
    "iter1_i2": (6, 6, 75, 13),
    "iter1_i3": (13, 6, 6, 75),
    "iter2_i0": (75, 13, 6, 6),
}


def build_buckets(anchor_root: str) -> tuple[list[Bucket], dict[str, list[Bucket]]]:
    anchor = f"{anchor_root.rstrip('/')}/{WORKLOAD}"
    grouped = {}
    all_buckets = []
    for shard in SHARDS:
        buckets = make_buckets(
            prefix=shard,
            anchor=f"{anchor}/{shard}",
            units=600,
            group=shard,
        )
        grouped[shard] = buckets
        all_buckets.extend(buckets)
    return all_buckets, grouped


def render_run_config(
    buckets: list[Bucket],
    grouped: dict[str, list[Bucket]],
    *,
    threads: int,
    phase_seconds: int,
    fwdrate: str,
) -> str:
    lines = config_header("SYSU GraphChi PSW mixed-size workload - run only", check_skew=True)
    lines.extend(render_fsd_lines(buckets))
    runs = []
    for phase, weights in STAGES.items():
        names = []
        for shard, weight in zip(SHARDS, weights):
            for bucket, skew in zip(grouped[shard], split_skew(weight)):
                name = f"{phase}_{shard}_s{bucket.size_mib}"
                names.append(name)
                lines.append(
                    fwd_line(
                        name=name,
                        bucket=bucket,
                        operation="read",
                        fileio="sequential",
                        threads=threads,
                        skew=skew,
                    )
                )
        lines.append("")
        runs.append(rd_line(name=phase, fwds=names, rate=fwdrate, elapsed=phase_seconds))
    lines.extend(runs)
    lines.append("")
    return "\n".join(lines)


def render(
    *,
    anchor_root: str,
    output_dir: Path,
    threads: int,
    phase_seconds: int,
    fwdrate: str,
) -> None:
    if not anchor_root.startswith("/"):
        raise ValueError("anchor_root must be an absolute path")
    if threads <= 0 or phase_seconds <= 0:
        raise ValueError("threads and phase_seconds must be positive")
    buckets, grouped = build_buckets(anchor_root)
    write_config(
        output_dir / "prepare_data.vdb",
        render_prepare_config("SYSU GraphChi PSW mixed-size workload", buckets, threads),
    )
    write_config(
        output_dir / "run_test.vdb",
        render_run_config(
            buckets,
            grouped,
            threads=threads,
            phase_seconds=phase_seconds,
            fwdrate=fwdrate,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--phase-seconds", type=int, default=120)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(
        anchor_root=args.anchor_root,
        output_dir=args.output_dir,
        threads=args.threads,
        phase_seconds=args.phase_seconds,
        fwdrate=args.fwdrate,
    )
    print(f"rendered {WORKLOAD}: 750 GiB, 74400 files")


if __name__ == "__main__":
    main()

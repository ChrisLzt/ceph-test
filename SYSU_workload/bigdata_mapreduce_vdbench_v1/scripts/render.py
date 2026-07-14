#!/usr/bin/env python3
"""Render the 750 GiB SYSU MapReduce Vdbench workload."""

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


WORKLOAD = "bigdata_mapreduce_vdbench_v1"
POOL_UNITS = {"pool_01": 96, "pool_02": 96, "pool_03": 96, "pool_04": 2112}
STAGES = {
    "hot_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
    "hot_b": {"pool_01": 1, "pool_02": 85, "pool_03": 1, "pool_04": 13},
    "hot_c": {"pool_01": 1, "pool_02": 1, "pool_03": 85, "pool_04": 13},
    "reheat_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
}


def build_buckets(anchor_root: str) -> tuple[list[Bucket], dict[str, list[Bucket]]]:
    anchor = f"{anchor_root.rstrip('/')}/{WORKLOAD}"
    grouped: dict[str, list[Bucket]] = {}
    all_buckets: list[Bucket] = []
    for pool, units in POOL_UNITS.items():
        buckets = make_buckets(
            prefix=pool,
            anchor=f"{anchor}/{pool}",
            units=units,
            group=pool,
        )
        grouped[pool] = buckets
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
    lines = config_header("SYSU MapReduce mixed-size workload - run only", check_skew=True)
    lines.extend(render_fsd_lines(buckets))
    rd_lines = []
    for phase, pool_weights in STAGES.items():
        phase_fwds = []
        for pool, weight in pool_weights.items():
            for bucket, skew in zip(grouped[pool], split_skew(weight)):
                name = f"{phase}_{pool}_s{bucket.size_mib}"
                phase_fwds.append(name)
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
        rd_lines.append(
            rd_line(name=phase, fwds=phase_fwds, rate=fwdrate, elapsed=phase_seconds)
        )
    lines.extend(rd_lines)
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
        render_prepare_config("SYSU MapReduce mixed-size workload", buckets, threads),
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
    parser.add_argument("--phase-seconds", type=int, default=150)
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

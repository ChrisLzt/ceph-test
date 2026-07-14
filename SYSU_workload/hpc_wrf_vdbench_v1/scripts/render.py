#!/usr/bin/env python3
"""Render the 750 GiB SYSU WRF lifecycle Vdbench workload."""

from __future__ import annotations

import argparse
from pathlib import Path

from SYSU_workload.common.layout import (
    Bucket,
    aggregate_zipf_percentages,
    make_buckets,
    split_skew,
)
from SYSU_workload.common.vdbench import (
    config_header,
    fwd_line,
    rd_line,
    render_fsd_lines,
    render_prepare_config,
    write_config,
)


WORKLOAD = "hpc_wrf_vdbench_v1"
GROUPS = ("startup", "checkpoint", "history")
PHASES = (
    ("startup_read", "startup"),
    ("checkpoint_read", "checkpoint"),
    ("history_read", "history"),
    ("checkpoint_reheat", "checkpoint"),
)
RANK_WEIGHTS = aggregate_zipf_percentages(64000, 20, 0.99)


def build_buckets(anchor_root: str) -> tuple[list[Bucket], dict[tuple[str, int], list[Bucket]]]:
    anchor = f"{anchor_root.rstrip('/')}/{WORKLOAD}"
    grouped = {}
    all_buckets = []
    for group in GROUPS:
        for rank in range(1, 21):
            prefix = f"{group}_r{rank:02d}"
            buckets = make_buckets(
                prefix=prefix,
                anchor=f"{anchor}/{group}/rank_{rank:02d}",
                units=40,
                group=group,
            )
            grouped[(group, rank)] = buckets
            all_buckets.extend(buckets)
    return all_buckets, grouped


def render_run_config(
    buckets: list[Bucket],
    grouped: dict[tuple[str, int], list[Bucket]],
    *,
    threads: int,
    phase_seconds: int,
    fwdrate: str,
) -> str:
    lines = config_header("SYSU WRF lifecycle Zipf mixed-size workload - run only", check_skew=True)
    lines.extend(render_fsd_lines(buckets))
    runs = []
    for phase, group in PHASES:
        names = []
        for rank, weight in enumerate(RANK_WEIGHTS, 1):
            for bucket, skew in zip(grouped[(group, rank)], split_skew(weight)):
                name = f"{phase}_r{rank:02d}_s{bucket.size_mib}"
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
        render_prepare_config("SYSU WRF lifecycle Zipf mixed-size workload", buckets, threads),
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
    print(f"rendered {WORKLOAD}: 750 GiB, 74400 files, Zipf={RANK_WEIGHTS}")


if __name__ == "__main__":
    main()

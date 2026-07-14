#!/usr/bin/env python3
"""Render the 750 GiB SYSU AI training Vdbench workload."""

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


WORKLOAD = "ai_training_checkpoint_vdbench_v1"
RANK_WEIGHTS = aggregate_zipf_percentages(166400, 20, 0.99)
DATASET_PHASES = (
    ("dataset_epoch_01", 1),
    ("dataset_epoch_02", 2),
    ("dataset_epoch_03", 3),
)
CHECKPOINT_PHASES = (
    ("checkpoint_read_current_first", "checkpoint_current"),
    ("checkpoint_read_current_second", "checkpoint_current"),
    ("recovery_read_old_checkpoint", "checkpoint_old"),
)


def build_buckets(anchor_root: str) -> tuple[
    list[Bucket], dict[int, list[Bucket]], dict[str, list[Bucket]]
]:
    anchor = f"{anchor_root.rstrip('/')}/{WORKLOAD}"
    dataset = {}
    checkpoints = {}
    all_buckets = []
    for rank in range(1, 21):
        buckets = make_buckets(
            prefix=f"dataset_r{rank:02d}",
            anchor=f"{anchor}/dataset/rank_{rank:02d}",
            units=104,
            group="dataset",
        )
        dataset[rank] = buckets
        all_buckets.extend(buckets)
    for group in ("checkpoint_current", "checkpoint_old"):
        buckets = make_buckets(
            prefix=group,
            anchor=f"{anchor}/{group}",
            units=160,
            group=group,
        )
        checkpoints[group] = buckets
        all_buckets.extend(buckets)
    return all_buckets, dataset, checkpoints


def render_run_config(
    buckets: list[Bucket],
    dataset: dict[int, list[Bucket]],
    checkpoints: dict[str, list[Bucket]],
    *,
    threads: int,
    dataset_phase_seconds: int,
    checkpoint_phase_seconds: int,
    fwdrate: str,
) -> str:
    lines = config_header("SYSU AI training Zipf mixed-size workload - run only", check_skew=True)
    lines.extend(render_fsd_lines(buckets))
    runs = []
    for phase, hot_rank in DATASET_PHASES:
        names = []
        for offset, weight in enumerate(RANK_WEIGHTS):
            rank = ((hot_rank - 1 + offset) % 20) + 1
            for bucket, skew in zip(dataset[rank], split_skew(weight)):
                name = f"{phase}_r{rank:02d}_s{bucket.size_mib}"
                names.append(name)
                lines.append(
                    fwd_line(
                        name=name,
                        bucket=bucket,
                        operation="read",
                        fileio="random",
                        threads=threads,
                        skew=skew,
                    )
                )
        lines.append("")
        runs.append(
            rd_line(
                name=phase,
                fwds=names,
                rate=fwdrate,
                elapsed=dataset_phase_seconds,
            )
        )
    for phase, group in CHECKPOINT_PHASES:
        names = []
        for bucket, skew in zip(checkpoints[group], split_skew(100)):
            name = f"{phase}_s{bucket.size_mib}"
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
        runs.append(
            rd_line(
                name=phase,
                fwds=names,
                rate=fwdrate,
                elapsed=checkpoint_phase_seconds,
            )
        )
    lines.extend(runs)
    lines.append("")
    return "\n".join(lines)


def render(
    *,
    anchor_root: str,
    output_dir: Path,
    threads: int,
    dataset_phase_seconds: int,
    checkpoint_phase_seconds: int,
    fwdrate: str,
) -> None:
    if not anchor_root.startswith("/"):
        raise ValueError("anchor_root must be an absolute path")
    if min(threads, dataset_phase_seconds, checkpoint_phase_seconds) <= 0:
        raise ValueError("threads and phase durations must be positive")
    buckets, dataset, checkpoints = build_buckets(anchor_root)
    write_config(
        output_dir / "prepare_data.vdb",
        render_prepare_config("SYSU AI training Zipf mixed-size workload", buckets, threads),
    )
    write_config(
        output_dir / "run_test.vdb",
        render_run_config(
            buckets,
            dataset,
            checkpoints,
            threads=threads,
            dataset_phase_seconds=dataset_phase_seconds,
            checkpoint_phase_seconds=checkpoint_phase_seconds,
            fwdrate=fwdrate,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--dataset-phase-seconds", type=int, default=160)
    parser.add_argument("--checkpoint-phase-seconds", type=int, default=40)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(
        anchor_root=args.anchor_root,
        output_dir=args.output_dir,
        threads=args.threads,
        dataset_phase_seconds=args.dataset_phase_seconds,
        checkpoint_phase_seconds=args.checkpoint_phase_seconds,
        fwdrate=args.fwdrate,
    )
    print(f"rendered {WORKLOAD}: 750 GiB, 74400 files, Zipf={RANK_WEIGHTS}")


if __name__ == "__main__":
    main()

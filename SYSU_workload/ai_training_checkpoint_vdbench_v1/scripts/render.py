#!/usr/bin/env python3
"""SYSU wrapper for the shared AI training model."""

import argparse
from pathlib import Path

from SYSU_workload.common.lifecycle_io import rewrite_phase, update_run_config
from workload_common.layout import SYSU_LAYOUT
from workload_common.models.ai_training import render as render_model


def render(*, anchor_root: str, output_dir: Path, threads: int = 1, dataset_phase_seconds: int = 160, checkpoint_phase_seconds: int = 60, fwdrate: str = "max") -> None:
    render_model(layout=SYSU_LAYOUT, anchor_root=anchor_root, output_dir=output_dir, threads=threads, dataset_phase_seconds=dataset_phase_seconds, checkpoint_phase_seconds=checkpoint_phase_seconds, fwdrate=fwdrate)
    update_run_config(
        output_dir / "run_test.vdb",
        lambda text: rewrite_phase(
            text,
            source="checkpoint_read_current",
            target="checkpoint_write_current",
            operation="write",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--dataset-phase-seconds", type=int, default=160)
    parser.add_argument("--checkpoint-phase-seconds", type=int, default=60)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(**vars(args))


if __name__ == "__main__":
    main()

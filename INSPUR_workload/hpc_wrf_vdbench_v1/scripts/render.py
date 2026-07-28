#!/usr/bin/env python3
"""INSPUR wrapper for the shared WRF Vdbench model."""

import argparse
from pathlib import Path

from INSPUR_workload.common.lifecycle_io import (
    clone_fwd_set,
    rewrite_phase,
    set_rd_selector,
    update_run_config,
)
from INSPUR_workload.common.layout import INSPUR_LAYOUT
from workload_common.models.hpc import render as render_model


def render(*, anchor_root: str, output_dir: Path, threads: int = 1, phase_seconds: int = 150, fwdrate: str = "max") -> None:
    render_model(layout=INSPUR_LAYOUT, anchor_root=anchor_root, output_dir=output_dir, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate)

    def add_wrf_writes(text: str) -> str:
        text = rewrite_phase(
            text,
            source="checkpoint_read",
            target="checkpoint_write",
            operation="write",
        )
        text = rewrite_phase(
            text,
            source="history_read",
            target="history_write",
            operation="write",
        )
        text = clone_fwd_set(
            text,
            source="checkpoint_write",
            target="checkpoint_reheat",
            operation="read",
        )
        return set_rd_selector(
            text,
            rd_name="checkpoint_reheat",
            fwd_set="checkpoint_reheat",
        )

    update_run_config(output_dir / "run_test.vdb", add_wrf_writes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--phase-seconds", type=int, default=150)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(**vars(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""INSPUR wrapper for the shared AI inference model."""

import argparse
from pathlib import Path

from INSPUR_workload.common.lifecycle_io import rewrite_phase, update_run_config
from INSPUR_workload.common.layout import INSPUR_LAYOUT
from workload_common.models.ai_inference import render as render_model


def render(*, anchor_root: str, output_dir: Path, threads: int = 1, phase_seconds: int = 100, fwdrate: str = "max") -> None:
    render_model(layout=INSPUR_LAYOUT, anchor_root=anchor_root, output_dir=output_dir, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate)

    def add_prefill_writes(text: str) -> str:
        text = rewrite_phase(
            text,
            source="prefill_active",
            target="prefill_active",
            operation="write",
        )
        return rewrite_phase(
            text,
            source="prefill_next",
            target="prefill_next",
            operation="write",
        )

    update_run_config(output_dir / "run_test.vdb", add_prefill_writes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--phase-seconds", type=int, default=100)
    parser.add_argument("--fwdrate", default="max")
    args = parser.parse_args()
    render(**vars(args))


if __name__ == "__main__":
    main()

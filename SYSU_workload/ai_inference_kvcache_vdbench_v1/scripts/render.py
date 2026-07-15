#!/usr/bin/env python3
"""SYSU wrapper for the shared AI inference model."""

import argparse
from pathlib import Path

from workload_common.layout import SYSU_LAYOUT
from workload_common.models.ai_inference import render as render_model


def render(*, anchor_root: str, output_dir: Path, threads: int = 1, phase_seconds: int = 100, fwdrate: str = "max") -> None:
    render_model(layout=SYSU_LAYOUT, anchor_root=anchor_root, output_dir=output_dir, threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate)


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

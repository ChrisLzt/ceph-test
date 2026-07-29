#!/usr/bin/env python3
"""Single-node wrapper for the shared GraphChi model."""

import argparse
from pathlib import Path

from workload_common.layout import SINGLE_LAYOUT
from workload_common.models.graphchi import render as render_model
from workload_common.single import hd_lines


def render(*, anchor_root: str, output_dir: Path, host: str, remote_user: str, vdbench_home: str, threads: int = 1, phase_seconds: int = 150, fwdrate: str = "max") -> None:
    render_model(layout=SINGLE_LAYOUT, anchor_root=anchor_root, output_dir=output_dir, hd_line=hd_lines(host=host, remote_user=remote_user, vdbench_home=vdbench_home), threads=threads, phase_seconds=phase_seconds, fwdrate=fwdrate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--remote-user", required=True)
    parser.add_argument("--vdbench-home", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--phase-seconds", type=int, default=150)
    parser.add_argument("--fwdrate", default="max")
    render(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()

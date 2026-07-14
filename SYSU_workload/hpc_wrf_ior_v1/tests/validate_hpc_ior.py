#!/usr/bin/env python3
"""Validate rendered SYSU WRF IOR scripts without executing IOR."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def variable(text: str, name: str) -> str:
    match = re.search(rf'^{re.escape(name)}="([^"]*)"$', text, re.M)
    if not match:
        fail(f"missing variable {name}")
    return match.group(1)


def size_mib(value: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)([mMgG])", value)
    if not match:
        fail(f"unsupported IOR size: {value}")
    amount = int(match.group(1))
    return amount if match.group(2).lower() == "m" else amount * 1024


def validate(rendered_dir: Path) -> None:
    prepare_path = rendered_dir / "prepare_data.sh"
    run_path = rendered_dir / "run_test.sh"
    if not prepare_path.is_file() or not run_path.is_file():
        fail(f"missing rendered scripts under {rendered_dir}")

    prepare = prepare_path.read_text(encoding="utf-8")
    run = run_path.read_text(encoding="utf-8")
    for name, text in (("prepare", prepare), ("run", run)):
        if re.search(r"@[A-Z_][A-Z_]*@", text):
            fail(f"{name} contains unresolved template variables")
        for marker in (
            'NP="4"',
            'API="POSIX"',
            'BLOCK_SIZE="64000m"',
            'TRANSFER_SIZE="4m"',
            'SEGMENT_COUNT="1"',
            "--posix.odirect",
            "-F",
            'mpi_args=(-np "$NP")',
            'mpi_args+=(--hostfile "$MPI_HOSTFILE")',
        ):
            if marker not in text:
                fail(f"{name} missing marker: {marker}")

    np = int(variable(prepare, "NP"))
    block_mib = size_mib(variable(prepare, "BLOCK_SIZE"))
    segments = int(variable(prepare, "SEGMENT_COUNT"))
    total_gib = np * block_mib * segments * 3 / 1024
    print(f"Total prepared capacity: {total_gib:.2f} GiB")
    if total_gib != 750:
        fail(f"capacity must be 750 GiB, got {total_gib:.2f}")

    if prepare.count("run_ior_write prepare_") != 3:
        fail("prepare must contain exactly three write calls")
    if re.search(r"(?:^|\s)-r(?:\s|$)", prepare, re.M):
        fail("prepare must not read")
    if "--posix.odirect -F -w -k -e" not in prepare:
        fail("prepare must use Direct I/O file-per-process writes")

    expected_calls = (
        'run_ior_read startup_read "$ANCHOR/startup/wrf_state"',
        'run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"',
        'run_ior_read history_read "$ANCHOR/history/wrfout_current"',
        'run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"',
    )
    positions = []
    for call in expected_calls:
        if call not in run:
            fail(f"formal run missing phase: {call}")
        positions.append(run.index(call))
    if positions != sorted(positions):
        fail("formal phases are out of order")
    if run.count("run_ior_read ") != 4:
        fail("formal run must contain exactly four read calls")
    if re.search(r"(?:^|\s)-w(?:\s|$)", run, re.M):
        fail("formal run must not write")
    for marker in (
        'PHASE_SECONDS="150"',
        "--posix.odirect -F -r -k",
        '-D "$PHASE_SECONDS"',
        '-O "minTimeDuration=$PHASE_SECONDS"',
        "-O stoneWallingWearOut=0",
    ):
        if marker not in run:
            fail(f"formal run missing marker: {marker}")

    print("PASS: SYSU HPC WRF IOR model is 750 GiB, -F, Direct I/O, and read-only.")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} RENDERED_DIR", file=sys.stderr)
        raise SystemExit(2)
    try:
        validate(Path(sys.argv[1]))
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file():
        fail(f"missing required file: {relative}")
    return path


def parse_size_to_gib(value: str) -> float:
    match = re.fullmatch(r"([1-9][0-9]*)([kKmMgGtT])", value)
    if not match:
        fail(f"invalid size: {value}")
    number = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "k":
        return number / 1024 / 1024
    if unit == "m":
        return number / 1024
    if unit == "g":
        return float(number)
    if unit == "t":
        return number * 1024.0
    fail(f"unsupported size unit: {unit}")


def read_text(relative: str) -> str:
    return require_file(relative).read_text(encoding="utf-8")


def validate_rendered() -> None:
    prepare = read_text("rendered/prepare_data.sh")
    run = read_text("rendered/run_test.sh")
    readme = read_text("README.md")
    sources = read_text("SOURCES.md")

    for name, text in [("prepare", prepare), ("run", run)]:
        if re.search(r"@[A-Z_][A-Z_]*@", text):
            fail(f"rendered {name} script has unresolved template variable")
        for marker in [
            "/mnt/cephfs/hpc_wrf_ior_v1",
            "/home/chris/PDSL/ior/src/ior",
            "/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun",
            "API=\"POSIX\"",
            "-a \"$API\"",
            "--posix.odirect",
            "-F",
            "BLOCK_SIZE=\"9600m\"",
            "TRANSFER_SIZE=\"4m\"",
            "tee \"$log\"",
        ]:
            if marker not in text:
                fail(f"rendered {name} script missing marker: {marker}")
        if "/mnt/cephfs/SINGLE_workload" in text:
            fail(f"rendered {name} script still uses old SINGLE_workload path")

    if re.search(r"(?:^|\s)-r(?:\s|$)", prepare):
        fail("prepare script should not contain read phases")
    if prepare.count("run_ior_write prepare_") != 3:
        fail("prepare script should create three WRF semantic file bases")

    expected_calls = [
        'run_ior_read startup_read "$ANCHOR/startup/wrf_state"',
        'run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"',
        'run_ior_read history_read "$ANCHOR/history/wrfout_current"',
        'run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"',
    ]
    for call in expected_calls:
        if call not in run:
            fail(f"run script missing phase call: {call}")

    if run.count("run_ior_read ") != 4:
        fail("rendered run should contain exactly four read phases")
    if "run_ior_write" in run or re.search(r"(?:^|\s)-w(?:\s|$)", run):
        fail("formal run must be read-only")

    for stale in ["wrfinput_d01", "wrfbdy_d01", "wrfrst_initial", "wrfrst_old", "wrfout_old"]:
        if stale in run:
            fail(f"formal run contains stale dataset: {stale}")

    for cleanup in [
        'rm -rf -- "$ANCHOR/input" "$ANCHOR/restart"',
        'rm -f -- "$ANCHOR/checkpoint"/wrfrst_old* "$ANCHOR/history"/wrfout_old*',
    ]:
        if cleanup not in prepare:
            fail(f"prepare script missing legacy cleanup: {cleanup}")

    for marker in [
        'PHASE_SECONDS="150"',
        "--posix.odirect",
        "-i 1",
        '-D "$PHASE_SECONDS"',
        '-O "minTimeDuration=$PHASE_SECONDS"',
        "-O stoneWallingWearOut=0",
    ]:
        if marker not in run:
            fail(f"rendered run missing timing/direct-I/O marker: {marker}")
    if "IOR_ITERATIONS=" in run:
        fail("rendered run should not use repetition-count timing")
    if run.count("--posix.odirect") != 1:
        fail("rendered run should use direct I/O in its read helper")
    if prepare.count("--posix.odirect") != 1:
        fail("rendered prepare should use direct I/O for dataset writes")

    for marker in ["ground_truth.csv", "/mnt/cephfs/SINGLE_workload"]:
        if marker in readme or marker in sources:
            fail(f"docs should not reference stale marker: {marker}")

    for marker in [
        "WRF",
        "checkpoint",
        "restart",
        "history",
        "IOR",
        "https://github.com/hpc/ior",
        "https://ior.readthedocs.io/",
    ]:
        if marker not in readme and marker not in sources:
            fail(f"docs missing source/workload marker: {marker}")


def validate_capacity() -> None:
    rendered = read_text("rendered/prepare_data.sh")
    np_match = re.search(r'^NP="(?P<np>[0-9]+)"$', rendered, re.M)
    block_match = re.search(r'^BLOCK_SIZE="(?P<block>[0-9]+[kKmMgGtT])"$', rendered, re.M)
    segment_match = re.search(r'^SEGMENT_COUNT="(?P<segments>[0-9]+)"$', rendered, re.M)
    if not np_match or not block_match or not segment_match:
        fail("rendered prepare script missing NP/BLOCK_SIZE/SEGMENT_COUNT")

    np = int(np_match.group("np"))
    block_gib = parse_size_to_gib(block_match.group("block"))
    segments = int(segment_match.group("segments"))
    file_bases = 3
    total_gib = np * block_gib * segments * file_bases
    print(f"Total prepared capacity: {total_gib:.2f} GiB")
    if total_gib != 112.5:
        fail(f"total prepared capacity should be exactly 112.5 GiB, got {total_gib:.2f}")


def main() -> None:
    for path in [
        "configs/prepare_data.sh.in",
        "configs/run_test.sh.in",
        "render_config.sh",
        "prepare_data.sh",
        "run_test.sh",
        "rendered/prepare_data.sh",
        "rendered/run_test.sh",
        "README.md",
        "SOURCES.md",
    ]:
        require_file(path)
    validate_rendered()
    validate_capacity()
    print("PASS: HPC WRF IOR workload is split into prepare-only and run-only scripts.")


if __name__ == "__main__":
    main()

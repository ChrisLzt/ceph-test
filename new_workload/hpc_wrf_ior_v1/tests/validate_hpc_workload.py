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
            "-F",
            "BLOCK_SIZE=\"4g\"",
            "TRANSFER_SIZE=\"1m\"",
            "tee \"$log\"",
        ]:
            if marker not in text:
                fail(f"rendered {name} script missing marker: {marker}")
        if "/mnt/cephfs/new_workload" in text:
            fail(f"rendered {name} script still uses old new_workload path")

    if "-r" in prepare:
        fail("prepare script should not contain read phases")
    if prepare.count("run_ior_write prepare_") != 7:
        fail("prepare script should create seven WRF semantic file bases")

    for marker in [
        "startup_read_wrfinput",
        "startup_read_wrfbdy",
        "startup_read_restart",
        "checkpoint_write_current",
        "checkpoint_hot_read_current",
        "history_write_current",
        "history_hot_read_current",
        "recovery_reheat_read_old_checkpoint",
    ]:
        if marker not in run:
            fail(f"run script missing phase: {marker}")

    if 'PHASE_SECONDS="75"' not in run:
        fail("rendered run should default to 75s per IOR phase for a roughly 10min test")
    if run.count('-D "$PHASE_SECONDS"') != 2:
        fail("rendered run should apply IOR stonewalling to both read and write helpers")

    for marker in ["ground_truth.csv", "/mnt/cephfs/new_workload"]:
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
    file_bases = 7
    total_gib = np * block_gib * segments * file_bases
    print(f"Total prepared capacity: {total_gib:.2f} GiB")
    if not (100 <= total_gib <= 120):
        fail("total prepared capacity should stay within 100-120 GiB")


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

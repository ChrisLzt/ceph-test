#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("startup", "checkpoint", "history")
PHASES = (
    ("startup_read", "startup"),
    ("checkpoint_read", "checkpoint"),
    ("history_read", "history"),
    ("checkpoint_reheat", "checkpoint"),
)
EXPECTED_WEIGHTS = [68, 7, 4, 3, 2, 2] + [1] * 14


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file():
        fail(f"missing required file: {relative}")
    return path


def read(relative: str) -> str:
    return require_file(relative).read_text(encoding="utf-8")


def expected_fsd_names() -> list[str]:
    return [
        f"fsd_{group}_r{rank:02d}"
        for group in GROUPS
        for rank in range(1, 21)
    ]


def validate_required_files() -> None:
    for relative in [
        "configs/prepare_data.vdb.in",
        "configs/run_test.vdb.in",
        "rendered/prepare_data.vdb",
        "rendered/run_test.vdb",
        "scripts/derive_zipf_profile.py",
        "render_config.sh",
        "prepare_data.sh",
        "run_test.sh",
        "validate_model.sh",
    ]:
        require_file(relative)


def validate_fsds(text: str, name: str, *, rendered: bool) -> None:
    fsd_lines = re.findall(r"(?m)^fsd=(fsd_[^,]+),anchor=([^,\n]+)$", text)
    names = [item[0] for item in fsd_lines]
    if names != expected_fsd_names():
        fail(f"{name} must contain 60 ordered startup/checkpoint/history rank FSDs")

    for group in GROUPS:
        for rank in range(1, 21):
            fsd = f"fsd_{group}_r{rank:02d}"
            anchor = f"/mnt/cephfs/hpc_wrf_vdbench_v1/{group}/rank_{rank:02d}"
            template_anchor = f"@ANCHOR@/{group}/rank_{rank:02d}"
            actual = dict(fsd_lines)[fsd]
            expected = anchor if rendered else template_anchor
            if actual != expected:
                fail(f"{name} anchor for {fsd} is {actual}, expected {expected}")

    default = re.search(
        r"(?m)^fsd=default,depth=1,width=1,files=([^,]+),size=([^,]+),"
        r"shared=yes,openflags=o_direct$",
        text,
    )
    if not default:
        fail(f"{name} missing Direct-I/O FSD default")
    expected_files = "120" if rendered else "@FILES_PER_RANK@"
    expected_size = "16m" if rendered else "@FILE_SIZE@"
    if default.groups() != (expected_files, expected_size):
        fail(f"{name} FSD default is {default.groups()}, expected {(expected_files, expected_size)}")


def validate_prepare() -> None:
    template = read("configs/prepare_data.vdb.in")
    rendered = read("rendered/prepare_data.vdb")

    for text, name, is_rendered in [
        (template, "configs/prepare_data.vdb.in", False),
        (rendered, "rendered/prepare_data.vdb", True),
    ]:
        validate_fsds(text, name, rendered=is_rendered)
        if text.count("\nfwd=prep_") != 60:
            fail(f"{name} must contain 60 prepare FWDs")
        if "format=(clean,only)" not in text or "format=(restart,only)" not in text:
            fail(f"{name} missing clean/create format RDs")
        for phase, _group in PHASES:
            if f"rd={phase}" in text:
                fail(f"{name} contains run phase {phase}")


def validate_run() -> None:
    template = read("configs/run_test.vdb.in")
    rendered = read("rendered/run_test.vdb")

    for text, name, is_rendered in [
        (template, "configs/run_test.vdb.in", False),
        (rendered, "rendered/run_test.vdb", True),
    ]:
        validate_fsds(text, name, rendered=is_rendered)
        if "abort_failed_skew=2" not in text:
            fail(f"{name} missing abort_failed_skew=2")
        if "operation=write" in text or "format=" in text:
            fail(f"{name} must be run-only and read-only")

        for phase, group in PHASES:
            actual_weights: list[int] = []
            actual_fsds: list[str] = []
            for rank in range(1, 21):
                match = re.search(
                    rf"(?m)^fwd={phase}_r{rank:02d},fsd=(fsd_[^,]+),"
                    r"operation=read,fileio=sequential,fileselect=random,"
                    r"xfersize=([^,]+),threads=([^,]+),skew=([0-9]+)$",
                    text,
                )
                if not match:
                    fail(f"{name} missing valid {phase} rank {rank:02d} FWD")
                actual_fsds.append(match.group(1))
                actual_weights.append(int(match.group(4)))
                expected_xfer = "4m" if is_rendered else "@XFER_SIZE@"
                expected_threads = "4" if is_rendered else "@THREADS@"
                if match.group(2) != expected_xfer or match.group(3) != expected_threads:
                    fail(f"{name} has unexpected xfer/threads for {phase} rank {rank:02d}")

            expected_fsds = [f"fsd_{group}_r{rank:02d}" for rank in range(1, 21)]
            if actual_fsds != expected_fsds:
                fail(f"{name} {phase} references the wrong data group")
            if actual_weights != EXPECTED_WEIGHTS:
                fail(f"{name} {phase} weights are {actual_weights}, expected {EXPECTED_WEIGHTS}")
            if sum(actual_weights) != 100 or min(actual_weights) <= 0:
                fail(f"{name} {phase} weights must be positive and sum to 100")

            fwds = ",".join(f"{phase}_r{rank:02d}" for rank in range(1, 21))
            rate = "1000" if is_rendered else "@FWD_RATE@"
            elapsed = "150" if is_rendered else "@PHASE_SECONDS@"
            rd = f"rd={phase},fwd=({fwds}),fwdrate={rate},elapsed={elapsed},interval=1"
            if rd not in text:
                fail(f"{name} missing exact RD for {phase}")

    checkpoint_first = [
        re.search(
            rf"(?m)^fwd=checkpoint_read_r{rank:02d},fsd=([^,]+),.*skew=([0-9]+)$",
            rendered,
        ).groups()
        for rank in range(1, 21)
    ]
    checkpoint_reheat = [
        re.search(
            rf"(?m)^fwd=checkpoint_reheat_r{rank:02d},fsd=([^,]+),.*skew=([0-9]+)$",
            rendered,
        ).groups()
        for rank in range(1, 21)
    ]
    if checkpoint_first != checkpoint_reheat:
        fail("checkpoint reheat must reuse the same FSDs and Zipf order")


def validate_environment_and_capacity() -> None:
    prepare = read("rendered/prepare_data.vdb")
    run = read("rendered/run_test.vdb")

    for text, name in [(prepare, "rendered/prepare_data.vdb"), (run, "rendered/run_test.vdb")]:
        if re.search(r"@[A-Z_][A-Z_]*@", text):
            fail(f"{name} contains unresolved template tokens")
        if "hd=hd1,system=s52.servers.hustpdsl.cn" not in text:
            fail(f"{name} missing current single-node host")
        for forbidden in [
            "hd=hd2",
            "hd=hd3",
            "hd=hd4",
            "/mnt/cephfs/new_workload",
            "/mnt/ikcdir",
            "user=hust",
        ]:
            if forbidden in text:
                fail(f"{name} contains forbidden legacy setting: {forbidden}")

    total_files = 3 * 20 * 120
    total_gib = total_files * 16 / 1024
    print(f"Total files: {total_files}")
    print(f"Total capacity: {total_gib:.2f} GiB")
    if total_files != 7200 or total_gib != 112.5:
        fail("default data model must contain 7200 files and 112.5 GiB")

    if not (ROOT.parent / "hpc_wrf_ior_v1").is_dir():
        fail("existing hpc_wrf_ior_v1 directory must be preserved")


def validate_docs() -> None:
    readme = read("README.md")
    sources = read("SOURCES.md")

    for marker in [
        "112.5 GiB",
        "Zipf(0.99)",
        "68 / 7 / 4 / 3 / 2 / 2",
        "startup_read",
        "checkpoint_reheat",
        "不是 WRF trace",
        "hpc_wrf_ior_v1",
    ]:
        if marker not in readme:
            fail(f"README.md missing design marker: {marker}")

    for marker in [
        "https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/namelist_variables.html",
        "https://www2.mmm.ucar.edu/wrf/site/documentation/users_guide/running_wrf.html",
        "https://www.oracle.com/downloads/server-storage/vdbench-downloads.html",
        "https://github.com/hpc/ior",
    ]:
        if marker not in sources:
            fail(f"SOURCES.md missing source URL: {marker}")

    for text, name in [(readme, "README.md"), (sources, "SOURCES.md")]:
        if "ground_truth.csv" in text:
            fail(f"{name} must not introduce an external ground-truth table")


def main() -> None:
    validate_required_files()
    validate_prepare()
    validate_run()
    validate_environment_and_capacity()
    validate_docs()
    print("PASS: WRF-derived Vdbench Zipf workload is internally consistent.")


if __name__ == "__main__":
    main()

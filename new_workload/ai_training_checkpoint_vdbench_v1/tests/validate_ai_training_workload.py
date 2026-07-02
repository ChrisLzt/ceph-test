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


def forbid_path(relative: str) -> None:
    path = ROOT / relative
    if path.exists():
        fail(f"stale Python proxy path should not exist: {relative}")


def parse_size_gib(value: str) -> float:
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
    fail(f"unsupported unit: {unit}")


def parse_fsds(text: str) -> dict[str, tuple[int, float]]:
    fsds: dict[str, tuple[int, float]] = {}
    pattern = re.compile(r"^fsd=(fsd_[^,]+),anchor=[^,]+,files=([0-9]+),size=([0-9]+[kKmMgGtT])$", re.M)
    for name, files, size in pattern.findall(text):
        fsds[name] = (int(files), parse_size_gib(size))
    return fsds


def validate_files() -> None:
    for path in [
        "README.md",
        "SOURCES.md",
        "configs/prepare_data.vdb.in",
        "configs/run_test.vdb.in",
        "render_config.sh",
        "prepare_data.sh",
        "run_test.sh",
        "rendered/prepare_data.vdb",
        "rendered/run_test.vdb",
    ]:
        require_file(path)
    for stale in [
        "configs/workload.env.in",
        "rendered/workload.env",
        "rendered/prepare_data.sh",
        "rendered/run_test.sh",
        "scripts/checkpoint_io.py",
    ]:
        forbid_path(stale)


def validate_docs() -> None:
    combined = require_file("README.md").read_text(encoding="utf-8") + require_file("SOURCES.md").read_text(encoding="utf-8")
    for marker in [
        "Meta DSI",
        "ISCA 2022",
        "MLPerf Storage",
        "DLIO",
        "vdbench",
        "/mnt/cephfs/ai_training_checkpoint_vdbench_v1",
    ]:
        if marker not in combined:
            fail(f"docs missing marker: {marker}")
    for stale in [
        "/mnt/cephfs/ai_training_mlperf_checkpoint_v1",
        "/mnt/cephfs/new_workload",
        "ground_truth.csv",
        "Python file backend proxy",
    ]:
        if stale in combined:
            fail(f"docs contain stale marker: {stale}")


def validate_vdbench_configs() -> None:
    prepare = require_file("configs/prepare_data.vdb.in").read_text(encoding="utf-8")
    run = require_file("configs/run_test.vdb.in").read_text(encoding="utf-8")
    rendered_prepare = require_file("rendered/prepare_data.vdb").read_text(encoding="utf-8")
    rendered_run = require_file("rendered/run_test.vdb").read_text(encoding="utf-8")

    for content, name in [(rendered_prepare, "rendered prepare"), (rendered_run, "rendered run")]:
        if re.search(r"@[A-Z_][A-Z_]*@", content):
            fail(f"{name} contains unresolved template variable")
        if "hd=hd1,system=s52.servers.hustpdsl.cn" not in content:
            fail(f"{name} should default to the single-node host")

    fsds = parse_fsds(prepare)
    expected = {
        "fsd_dataset_hot": (32, 1.0),
        "fsd_dataset_warm": (24, 1.0),
        "fsd_dataset_cold": (32, 1.0),
        "fsd_checkpoint_current": (12, 1.0),
        "fsd_checkpoint_old": (12, 1.0),
    }
    if fsds != expected:
        fail(f"unexpected FSD layout: {fsds}")
    total_gib = sum(files * size_gib for files, size_gib in fsds.values())
    print(f"Total prepared capacity: {total_gib:.2f} GiB")
    if not (100 <= total_gib <= 120):
        fail("total prepared capacity should stay within 100-120 GiB")

    if "format=(clean,only)" not in prepare or "format=(restart,only)" not in prepare:
        fail("prepare config must contain clean/create format RDs")
    for content, name in [(run, "run template"), (rendered_run, "rendered run")]:
        if "format=" in content or "prepare_clean" in content or "prepare_create" in content:
            fail(f"{name} must not contain prepare/format directives")
        for rd in [
            "rd=epoch_read_hot_dataset",
            "rd=epoch_read_warm_dataset",
            "rd=checkpoint_write_current",
            "rd=checkpoint_read_current",
            "rd=recovery_read_old_checkpoint",
        ]:
            if rd not in content:
                fail(f"{name} missing {rd}")
        if "fsd_dataset_cold" not in content or re.search(r"fwd=.*fsd=fsd_dataset_cold", content):
            fail(f"{name} should define dataset_cold but not access it during run")

    elapsed_values = re.findall(r"elapsed=([0-9]+)", rendered_run)
    if elapsed_values != ["120"] * 5:
        fail(f"rendered run should contain five 120s phases for a 10min test, got {elapsed_values}")


def main() -> None:
    validate_files()
    validate_docs()
    validate_vdbench_configs()
    print("PASS: AI training checkpoint vdbench workload is internally consistent.")


if __name__ == "__main__":
    main()

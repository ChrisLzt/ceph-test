#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIPFIAN_WEIGHTS = [69, 6, 4, 3, 2, 2] + [1] * 14


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


def parse_fwd_lines(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("fwd="):
            name = line.split(",", 1)[0].split("=", 1)[1]
            result[name] = line
    return result


def rd_fwd_names(text: str, rd_name: str) -> list[str]:
    match = re.search(rf"^rd={re.escape(rd_name)},fwd=\(([^)]*)\),", text, re.M)
    if not match:
        fail(f"missing RD with fwd list: {rd_name}")
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def skew_of(line: str) -> int:
    match = re.search(r",skew=([0-9]+)(?:,|$)", line)
    if not match:
        fail(f"missing skew in fwd line: {line}")
    return int(match.group(1))


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
        "Zipfian",
        "dataset_rank_01~20",
        "/mnt/cephfs/ai_training_checkpoint_vdbench_v1",
    ]:
        if marker not in combined:
            fail(f"docs missing marker: {marker}")
    for stale in [
        "/mnt/cephfs/ai_training_mlperf_checkpoint_v1",
        "/mnt/cephfs/new_workload",
        "ground_truth.csv",
        "Python file backend proxy",
        "dataset_hot_01~04",
        "dataset_cold_01~04",
        "hot/cold = 2:8",
        "cold 分片全程不访问",
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
        **{f"fsd_dataset_rank_{i:02d}": (250, 20 / 1024) for i in range(1, 21)},
        "fsd_checkpoint_current": (400, 20 / 1024),
        "fsd_checkpoint_old": (400, 20 / 1024),
    }
    if fsds != expected:
        fail(f"unexpected FSD layout: {fsds}")
    total_gib = sum(files * size_gib for files, size_gib in fsds.values())
    print(f"Total prepared capacity: {total_gib:.2f} GiB")
    if abs(total_gib - 113.28125) > 0.0001:
        fail("total prepared capacity should be about 113.28 GiB")

    if "format=(clean,only)" not in prepare or "format=(restart,only)" not in prepare:
        fail("prepare config must contain clean/create format RDs")
    for stale in ["dataset_hot", "dataset_cold", "dataset_warm"]:
        if stale in prepare or stale in run or stale in rendered_run:
            fail(f"stale dataset name remains: {stale}")

    for content, name in [(run, "run template"), (rendered_run, "rendered run")]:
        if "format=" in content or "prepare_clean" in content or "prepare_create" in content:
            fail(f"{name} must not contain prepare/format directives")
        expected_rds = [
            "dataset_epoch_01",
            "dataset_epoch_02",
            "dataset_epoch_03",
            "checkpoint_write_current",
            "checkpoint_read_current",
            "recovery_read_old_checkpoint",
        ]
        for rd in expected_rds:
            if f"rd={rd}" not in content:
                fail(f"{name} missing {rd}")
        fwd_lines = parse_fwd_lines(content)
        for rd in expected_rds[:3]:
            fwds = rd_fwd_names(content, rd)
            if len(fwds) != 20:
                fail(f"{name} {rd} should access all twenty dataset ranks")
            skews = [skew_of(fwd_lines[fwd]) for fwd in fwds]
            if skews != ZIPFIAN_WEIGHTS:
                fail(f"{name} {rd} should use Zipfian weights {ZIPFIAN_WEIGHTS}, got {skews}")
            ranks = sorted(set(re.findall(r"fsd_dataset_rank_([0-9]{2})", "\n".join(fwd_lines[fwd] for fwd in fwds))))
            if ranks != [f"{i:02d}" for i in range(1, 21)]:
                fail(f"{name} {rd} should touch all dataset ranks, got {ranks}")
        for rank in range(1, 21):
            if f"fsd=fsd_dataset_rank_{rank:02d}" not in content:
                fail(f"{name} should access dataset rank {rank:02d}")
        if "fsd=fsd_checkpoint_current,operation=write" not in content:
            fail(f"{name} missing current checkpoint write")
        if "fsd=fsd_checkpoint_current,operation=read" not in content:
            fail(f"{name} missing current checkpoint read")
        if "fsd=fsd_checkpoint_old,operation=read" not in content:
            fail(f"{name} missing old checkpoint recovery read")

    elapsed_values = re.findall(r"elapsed=([0-9]+)", rendered_run)
    expected_elapsed = ["160", "160", "160", "40", "40", "40"]
    if elapsed_values != expected_elapsed:
        fail(f"rendered run should use 160s dataset and 40s checkpoint phases, got {elapsed_values}")


def main() -> None:
    validate_files()
    validate_docs()
    validate_vdbench_configs()
    print("PASS: AI training checkpoint vdbench Zipfian workload is internally consistent.")


if __name__ == "__main__":
    main()

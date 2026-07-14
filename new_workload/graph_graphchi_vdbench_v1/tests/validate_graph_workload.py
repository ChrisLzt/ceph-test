#!/usr/bin/env python3
import re
import sys
from collections import defaultdict
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


def forbid_file(relative: str) -> None:
    path = ROOT / relative
    if path.exists():
        fail(f"stale file should not exist: {relative}")


def read_edges(path: Path) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                fail(f"{path}:{lineno} must contain two integer columns")
            try:
                src, dst = int(parts[0]), int(parts[1])
            except ValueError:
                fail(f"{path}:{lineno} contains non-integer vertex id")
            edges.append((src, dst))
    if not edges:
        fail(f"{path} has no edges")
    return edges


def interval_of(vertex: int, vertices_per_interval: int) -> int:
    return vertex // vertices_per_interval


def integer_percentages(counts: list[int]) -> list[int]:
    total = sum(counts)
    if total <= 0:
        fail("cannot normalize empty counts")
    raw = [count * 100 / total for count in counts]
    floors = [int(value) for value in raw]
    remainder = 100 - sum(floors)
    order = sorted(range(len(counts)), key=lambda idx: (raw[idx] - floors[idx], counts[idx]), reverse=True)
    pct = floors[:]
    for idx in order[:remainder]:
        pct[idx] += 1
    return pct


def calculate_expected_rows(
    edges: list[tuple[int, int]],
    intervals: int,
    vertices_per_interval: int,
    iterations: int,
    reheat_interval: int | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    edge_bytes = 16
    phase_sequence = [
        (iteration, interval)
        for iteration in range(1, iterations + 1)
        for interval in range(intervals)
    ]
    if reheat_interval is not None:
        phase_sequence.append((iterations + 1, reheat_interval))

    for iteration, interval in phase_sequence:
        phase = f"iter{iteration}_i{interval}"
        counts = [0 for _ in range(intervals)]
        roles = ["not_accessed" for _ in range(intervals)]

        for src, dst in edges:
            src_i = interval_of(src, vertices_per_interval)
            dst_i = interval_of(dst, vertices_per_interval)
            if src_i < 0 or src_i >= intervals or dst_i < 0 or dst_i >= intervals:
                fail(f"edge ({src}, {dst}) is outside configured intervals")
            if dst_i == interval:
                counts[interval] += 1
                roles[interval] = "memory_shard"
            elif src_i == interval:
                counts[dst_i] += 1
                roles[dst_i] = "sliding_shard"

        pct = integer_percentages(counts)
        for shard, count in enumerate(counts):
            rows.append(
                {
                    "phase": phase,
                    "iteration": str(iteration),
                    "interval": str(interval),
                    "object_id": f"shard_{shard:02d}",
                    "role": roles[shard],
                    "read_edges": str(count),
                    "read_bytes": str(count * edge_bytes),
                    "target_ops_pct": str(pct[shard]),
                }
            )
    return rows


def validate_expected_rows(rows: list[dict[str, str]]) -> None:
    by_phase: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_phase[row["phase"]].append(row)

    for phase, phase_rows in by_phase.items():
        total_pct = sum(int(row["target_ops_pct"]) for row in phase_rows)
        if total_pct != 100:
            fail(f"{phase} target_ops_pct sums to {total_pct}, expected 100")
        memory = [row for row in phase_rows if row["role"] == "memory_shard"]
        if len(memory) != 1:
            fail(f"{phase} should have exactly one memory_shard row")
        interval = int(phase_rows[0]["interval"])
        if memory[0]["object_id"] != f"shard_{interval:02d}":
            fail(f"{phase} memory_shard is {memory[0]['object_id']}, expected shard_{interval:02d}")


def validate_templates(rows: list[dict[str, str]]) -> None:
    prepare_template = require_file("configs/prepare_data.vdb.in").read_text(encoding="utf-8")
    run_template = require_file("configs/run_test.vdb.in").read_text(encoding="utf-8")
    prepare_rendered = require_file("rendered/prepare_data.vdb").read_text(encoding="utf-8")
    run_rendered = require_file("rendered/run_test.vdb").read_text(encoding="utf-8")

    for text, name in [(prepare_template, "configs/prepare_data.vdb.in"), (run_template, "configs/run_test.vdb.in")]:
        if "AUTO-GENERATED by scripts/derive_profile.py" not in text:
            fail(f"{name} must be generated by derive_profile.py")
        for shard in range(4):
            if f"fsd=fsd_s{shard}" not in text:
                fail(f"{name} missing FSD for shard {shard}")
            if f"anchor=@ANCHOR@/shard_{shard:02d}" not in text:
                fail(f"{name} missing anchor for shard_{shard:02d}")
        if "hd=hd2" in text or "hd=hd3" in text or "hd=hd4" in text:
            fail(f"{name} should be single-node only")

    if "format=(clean,only)" not in prepare_template or "format=(restart,only)" not in prepare_template:
        fail("prepare template missing clean/create format RDs")
    for marker in ["rd=iter1_i0", "rd=iter1_i1", "rd=iter1_i2", "rd=iter1_i3"]:
        if marker in prepare_template:
            fail(f"prepare template contains run RD: {marker}")

    for text, name in [(run_template, "configs/run_test.vdb.in"), (run_rendered, "rendered/run_test.vdb")]:
        if "format=" in text or "prepare_clean" in text or "prepare_create" in text:
            fail(f"run-only config contains prepare/format directive: {name}")
        for forbidden_phase in ["iter2_i1", "iter2_i2", "iter2_i3"]:
            if forbidden_phase in text:
                fail(f"run-only config contains unexpected second-iteration phase {forbidden_phase}: {name}")

    for row in rows:
        phase = row["phase"]
        shard = int(row["object_id"].split("_")[1])
        pct = int(row["target_ops_pct"])
        if pct <= 0:
            continue
        expected = f"fwd={phase}_s{shard},fsd=fsd_s{shard},operation=read,fileio=sequential,fileselect=random,xfersize=@XFER_SIZE@,threads=@THREADS@,skew={pct}"
        if expected not in run_template:
            fail(f"run template missing or mismatched FWD line: {expected}")

    for phase in dict.fromkeys(row["phase"] for row in rows):
        active_shards = [
            int(row["object_id"].split("_")[1])
            for row in rows
            if row["phase"] == phase and int(row["target_ops_pct"]) > 0
        ]
        fwd_list = ",".join(f"{phase}_s{shard}" for shard in active_shards)
        expected = f"rd={phase},fwd=({fwd_list}),fwdrate=@FWD_RATE@,elapsed=@PHASE_SECONDS@,interval=1"
        if expected not in run_template:
            fail(f"run template missing RD line: {expected}")

    for text, name in [(prepare_rendered, "rendered/prepare_data.vdb"), (run_rendered, "rendered/run_test.vdb")]:
        if re.search(r"@[A-Z_][A-Z_]*@", text):
            fail(f"{name} contains unresolved template variable")
        if "/mnt/cephfs/new_workload" in text:
            fail(f"{name} still uses old new_workload data path")

    phase_names = re.findall(r"(?m)^rd=([^,]+)", run_rendered)
    expected_phases = ["iter1_i0", "iter1_i1", "iter1_i2", "iter1_i3", "iter2_i0"]
    if phase_names != expected_phases:
        fail(f"rendered run phases should be {expected_phases}, got {phase_names}")

    elapsed_values = re.findall(r"elapsed=([0-9]+)", run_rendered)
    if elapsed_values != ["120"] * 5:
        fail(f"rendered run should contain five 120s phases for a 10min test, got {elapsed_values}")


def validate_capacity() -> None:
    rendered = require_file("rendered/prepare_data.vdb").read_text(encoding="utf-8")
    match = re.search(r"fsd=default,depth=1,width=1,files=(?P<files>[0-9]+),size=(?P<size>[0-9]+)(?P<unit>[kKmMgG])", rendered)
    if not match:
        fail("rendered prepare config missing fsd default files/size")
    files = int(match.group("files"))
    size = int(match.group("size"))
    unit = match.group("unit").lower()
    size_mib = size / 1024 if unit == "k" else size if unit == "m" else size * 1024
    total_gib = 4 * files * size_mib / 1024
    print(f"Total capacity: {total_gib:.2f} GiB")
    if not (100 <= total_gib <= 120):
        fail("total graph dataset capacity should stay within 100-120 GiB")


def validate_docs() -> None:
    readme = require_file("README.md").read_text(encoding="utf-8")
    sources = require_file("SOURCES.md").read_text(encoding="utf-8")
    for marker in [
        "生成图",
        "计算比例",
        "prepare_data.vdb",
        "run_test.vdb",
        "readFully",
        "readNextWindow",
        "derive_profile.py",
        "5 个阶段",
        "120",
        "shard_00 复热",
    ]:
        if marker not in readme:
            fail(f"README.md missing workflow marker: {marker}")
    for marker in [
        "https://www.usenix.org/conference/osdi12/technical-sessions/presentation/kyrola",
        "https://www.usenix.org/system/files/conference/osdi12/osdi12-final-126.pdf",
        "https://www.oracle.com/downloads/server-storage/vdbench-downloads.html",
    ]:
        if marker not in sources:
            fail(f"SOURCES.md missing source marker: {marker}")
    if "ground_truth.csv" in readme or "ground_truth.csv" in sources:
        fail("ground_truth.csv should not be referenced in docs")


def validate_current_server_defaults() -> None:
    render_script = require_file("render_config.sh").read_text(encoding="utf-8")
    readme = require_file("README.md").read_text(encoding="utf-8")

    expected_defaults = [
        "/mnt/cephfs/graph_graphchi_vdbench_v1",
        "/home/chris/PDSL/vdbench",
        "s52.servers.hustpdsl.cn",
        "REMOTE_USER=chris",
    ]
    combined = render_script + readme
    for marker in expected_defaults:
        if marker not in combined:
            fail(f"current-server default missing: {marker}")

    forbidden_defaults = [
        "/mnt/ikcdir",
        "/mnt/cephfs/new_workload",
        "host1001",
        "host1003",
        "host1005",
        "host1007",
        "REMOTE_USER=hust",
        "hd=hd2",
        "hd=hd3",
        "hd=hd4",
    ]
    for marker in forbidden_defaults:
        if marker in render_script:
            fail(f"old environment default still present: {marker}")


def main() -> None:
    require_file("scripts/generate_graph.py")
    require_file("scripts/derive_profile.py")
    forbid_file("ground_truth.csv")
    forbid_file("configs/graphchi_shard_windows.vdb.in")
    forbid_file("rendered/graphchi_shard_windows.vdb")
    edges = read_edges(require_file("datasets/smoke_edges.tsv"))
    rows = calculate_expected_rows(
        edges,
        intervals=4,
        vertices_per_interval=128,
        iterations=1,
        reheat_interval=0,
    )
    validate_expected_rows(rows)
    validate_templates(rows)
    validate_capacity()
    validate_docs()
    validate_current_server_defaults()
    print("PASS: GraphChi vdbench workload is split into prepare-only and run-only configs.")


if __name__ == "__main__":
    main()

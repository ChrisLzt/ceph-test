#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh all >/dev/null

python3 - <<'PY'
from pathlib import Path
import re

prepare_template = Path("configs/prepare_data.vdb.in")
run_template = Path("configs/run_test.vdb.in")
prepare_rendered = Path("rendered/prepare_data.vdb")
run_rendered = Path("rendered/run_test.vdb")
readme = Path("README.md")
sources = Path("SOURCES.md")

for path in [prepare_template, run_template, prepare_rendered, run_rendered, readme, sources]:
    if not path.exists():
        raise SystemExit(f"FAIL: missing required file: {path}")

prepare_text = prepare_template.read_text(encoding="utf-8")
run_text = run_template.read_text(encoding="utf-8")
text = run_text

fsd_re = re.compile(r"^fsd=(?P<name>[^,]+),anchor=[^,]+,files=(?P<files>[0-9]+),size=(?P<size>[0-9.]+)(?P<unit>[kKmMgG])$", re.M)
fsds = []
for match in fsd_re.finditer(prepare_text):
    unit = match.group("unit").lower()
    size = float(match.group("size"))
    if unit == "k":
        size_mib = size / 1024
    elif unit == "m":
        size_mib = size
    elif unit == "g":
        size_mib = size * 1024
    else:
        raise SystemExit(f"FAIL: unsupported size unit: {unit}")
    fsds.append((match.group("name"), int(match.group("files")), size_mib))

if len(fsds) != 5:
    raise SystemExit(f"FAIL: expected 5 FSD pools, got {len(fsds)}")

total_mib = sum(files * size_mib for _, files, size_mib in fsds)
inactive = [row for row in fsds if row[0] == "fsd_inactive"]
if len(inactive) != 1:
    raise SystemExit("FAIL: fsd_inactive missing")
inactive_mib = inactive[0][1] * inactive[0][2]
inactive_files = inactive[0][1]
total_files = sum(files for _, files, _ in fsds)

print(f"Total files: {total_files}")
print(f"Total capacity: {total_mib / 1024:.2f} GiB")
print(f"Inactive: {inactive_files / total_files * 100:.2f}% files, {inactive_mib / total_mib * 100:.2f}% bytes")

total_gib = total_mib / 1024
if not (100 <= total_gib <= 120):
    raise SystemExit("FAIL: total capacity should stay within the 100-120 GiB single-workload budget")
expected_files = {
    "fsd_a": 200,
    "fsd_b": 200,
    "fsd_c": 200,
    "fsd_bg": 5000,
    "fsd_inactive": 4400,
}
actual_files = {name: files for name, files, _ in fsds}
if actual_files != expected_files:
    raise SystemExit(f"FAIL: FSD file counts should keep capacity-first 2/2/2/50/44 ratio, got {actual_files}")
inactive_byte_pct = inactive_mib / total_mib * 100
if not (42 <= inactive_byte_pct <= 46):
    raise SystemExit("FAIL: inactive byte percentage is outside paper range [42,46]")
if abs((inactive_mib / total_mib * 100) - (inactive_files / total_files * 100)) > 0.001:
    raise SystemExit("FAIL: equal-size FSDs should make inactive byte percentage equal inactive file percentage")
sizes = {size_mib for _, _, size_mib in fsds}
if len(sizes) != 1:
    raise SystemExit(f"FAIL: all FSD file sizes should be identical, got {sorted(sizes)}")

for phase, hot in [("hot_a", "ha_a"), ("hot_b", "hb_b"), ("hot_c", "hc_c"), ("reheat_a", "rh_a")]:
    rd = re.search(rf"^rd={phase},fwd=\((?P<fwd>[^)]+)\),", run_text, re.M)
    if not rd:
        raise SystemExit(f"FAIL: missing RD {phase}")
    fwd_names = rd.group("fwd").split(",")
    skews = {}
    for name in fwd_names:
        line = re.search(rf"^fwd={name},.*skew=(?P<skew>[0-9.]+)$", run_text, re.M)
        if not line:
            raise SystemExit(f"FAIL: missing FWD skew for {name}")
        skews[name] = float(line.group("skew"))
    if sum(skews.values()) != 100:
        raise SystemExit(f"FAIL: {phase} skew sum is {sum(skews.values())}, expected 100")
    if skews.get(hot) != 85:
        raise SystemExit(f"FAIL: {phase} hot FWD {hot} should have 85%")
    if sorted(skews.values()) != [1.0, 1.0, 13.0, 85.0]:
        raise SystemExit(f"FAIL: {phase} should use temporal-locality skew 85/1/1/13, got {skews}")

for path in [prepare_template, run_template, prepare_rendered, run_rendered]:
    content = path.read_text(encoding="utf-8")
    for forbidden in ["/mnt/ikcdir", "/mnt/cephfs/new_workload", "host1001", "host1003", "host1005", "host1007", "user=hust", "hd=hd2", "hd=hd3", "hd=hd4", "@HOST2@", "@HOST3@", "@HOST4@"]:
        if forbidden in content:
            raise SystemExit(f"FAIL: old environment default remains in {path}: {forbidden}")
    if "hd=hd1,system=s52.servers.hustpdsl.cn" not in content and "hd=hd1,system=@HOST1@" not in content:
        raise SystemExit(f"FAIL: single-node hd1 definition missing in {path}")

for path in [prepare_template, prepare_rendered]:
    content = path.read_text(encoding="utf-8")
    if "rd=hot_a" in content or "rd=hot_b" in content or "rd=hot_c" in content or "rd=reheat_a" in content:
        raise SystemExit(f"FAIL: prepare-only config contains run RDs: {path}")
    if "format=(clean,only)" not in content or "format=(restart,only)" not in content:
        raise SystemExit(f"FAIL: prepare-only config missing clean/create format RDs: {path}")

for path in [run_template, run_rendered]:
    content = path.read_text(encoding="utf-8")
    if "format=" in content or "prepare_clean" in content or "prepare_create" in content:
        raise SystemExit(f"FAIL: run-only config contains prepare/format directives: {path}")
    for required in ["rd=hot_a", "rd=hot_b", "rd=hot_c", "rd=reheat_a"]:
        if required not in content:
            raise SystemExit(f"FAIL: run-only config missing {required}: {path}")
    for forbidden in ["rd=reference_control", "fwd=ctl_a", "fwd=ctl_b", "fwd=ctl_c", "fwd=ctl_bg"]:
        if forbidden in content:
            raise SystemExit(f"FAIL: removed control phase remains in {path}: {forbidden}")

elapsed_values = re.findall(r"elapsed=([0-9]+)", run_rendered.read_text(encoding="utf-8"))
if elapsed_values != ["150"] * 4:
    raise SystemExit(f"FAIL: rendered run should contain four 150s phases for a 10min test, got {elapsed_values}")

if Path("rendered/data_heat_proxy.vdb").exists():
    raise SystemExit("FAIL: stale combined rendered/data_heat_proxy.vdb should not exist; use prepare_data.vdb or run_test.vdb")
if Path("configs/data_heat_proxy.vdb.in").exists():
    raise SystemExit("FAIL: stale combined configs/data_heat_proxy.vdb.in should not exist; use prepare_data.vdb.in or run_test.vdb.in")

for path in [readme, sources]:
    content = path.read_text(encoding="utf-8")
    if "namespace_heat" in content or "ground_truth.csv" in content:
        raise SystemExit(f"FAIL: removed component still referenced in {path}")

print("PASS: bigdata_mapreduce_vdbench model and environment are internally consistent.")
PY

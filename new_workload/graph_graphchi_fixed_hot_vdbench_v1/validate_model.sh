#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh >/dev/null

python3 - <<'PY'
from pathlib import Path
import re

run_template = Path("configs/run_test.vdb.in")
run_rendered = Path("rendered/run_test.vdb")
readme = Path("README.md")
run_script = Path("run_test.sh")

for path in [run_template, run_rendered, readme, run_script]:
    if not path.exists():
        raise SystemExit(f"FAIL: missing required file: {path}")

run_text = run_template.read_text(encoding="utf-8")
rendered_text = run_rendered.read_text(encoding="utf-8")

for path in [run_template, run_rendered]:
    content = path.read_text(encoding="utf-8")
    for forbidden in [
        "format=", "prepare_clean", "prepare_create",
        "/mnt/ikcdir", "/mnt/cephfs/new_workload",
        "host1001", "host1003", "host1005", "host1007",
        "user=hust", "hd=hd2", "hd=hd3", "hd=hd4",
        "@HOST2@", "@HOST3@", "@HOST4@",
    ]:
        if forbidden in content:
            raise SystemExit(f"FAIL: forbidden directive/default remains in {path}: {forbidden}")
    if "hd=hd1,system=s52.servers.hustpdsl.cn" not in content and "hd=hd1,system=@HOST1@" not in content:
        raise SystemExit(f"FAIL: single-node hd1 definition missing in {path}")

expected_phases = [
    "fixed_i0", "fixed_i1", "fixed_i2", "fixed_i3",
    "fixed_i4", "fixed_i5", "fixed_i6", "fixed_i7",
]
for phase in expected_phases:
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
    if skews.get(f"{phase}_s0") != 75:
        raise SystemExit(f"FAIL: {phase} must keep shard_00 hot at 75%, got {skews}")
    if sorted(skews.values()) != [6.0, 6.0, 13.0, 75.0]:
        raise SystemExit(f"FAIL: {phase} should use fixed GraphChi skew 75/13/6/6, got {skews}")

elapsed_values = re.findall(r"elapsed=([0-9]+)", rendered_text)
if elapsed_values != ["75"] * 8:
    raise SystemExit(f"FAIL: rendered run should contain eight 75s phases, got {elapsed_values}")

if re.search(r"@[A-Z_][A-Z_]*@", rendered_text):
    raise SystemExit("FAIL: rendered config still contains unresolved template variables")

if "/mnt/cephfs/graph_graphchi_vdbench_v1" not in rendered_text:
    raise SystemExit("FAIL: fixed-hot GraphChi workload must reuse the existing GraphChi dataset")

readme_text = readme.read_text(encoding="utf-8")
if "固定热点" not in readme_text or "shard_00" not in readme_text:
    raise SystemExit("FAIL: README must document the fixed-hot purpose and shard_00 hotspot")

print("PASS: graph_graphchi_fixed_hot_vdbench_v1 is a run-only fixed-hot workload.")
PY

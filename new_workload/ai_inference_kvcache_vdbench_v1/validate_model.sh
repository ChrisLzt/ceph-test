#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh all >/dev/null

python3 tests/validate_ai_inference_workload.py
python3 - <<'PY'
import pathlib, re
path = pathlib.Path("rendered/run_test.vdb")
rates = re.findall(r"(?m)^rd=.*?fwdrate=([^,]+)", path.read_text(encoding="utf-8"))
if not rates or set(rates) != {"1000"}:
    raise SystemExit(f"FAIL: accuracy runs require fwdrate=1000, got {sorted(set(rates))}")
PY

#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo"
python3 -m workload_common.single_v2 validate --profile current --case all --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload}"
python3 -m unittest discover -s workload_common/tests -v
python3 -m unittest discover -s workload_common/single_v2/tests -v
while IFS= read -r -d '' script; do bash -n "$script"; done < <(find SINGLE_workload -name '*.sh' -print0)
if [[ -n "${PARSER_RESULTS:-}" ]]; then
    python3 -m workload_common.single_v2 parser-check --case all --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload}" --vdbench "${VDBENCH_HOME:-/home/chris/PDSL/vdbench}/vdbench" --results "$PARSER_RESULTS"
fi
echo 'PASS: SINGLE v2 offline configuration/model checks (no preparation or benchmark)'

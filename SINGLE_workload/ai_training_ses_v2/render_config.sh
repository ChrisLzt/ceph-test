#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python_bin=${PYTHON_BIN:-python3}
data_args=()
if [[ -n ${DATA_ROOT:-} ]]; then data_args+=(--data-root "$DATA_ROOT"); fi
exec "$python_bin" -m workload_common.single_v2 render --case ai_training --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload/current}" --design current --rate max "${data_args[@]}" "$@"

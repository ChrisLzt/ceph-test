#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python_bin=${PYTHON_BIN:-${SES_PYTHON:-$repo/../ceph-tool/.venv-ses120/bin/python}}
exec "$python_bin" -m workload_common.single_v2 run --profile current --vdbench "${VDBENCH_HOME:-$repo/../ceph-tool/runtime/vdbench-fractional-xfer-v1}/vdbench" --case ai_training --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload/current}" "$@"

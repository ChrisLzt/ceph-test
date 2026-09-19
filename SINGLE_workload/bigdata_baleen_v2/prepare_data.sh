#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python_bin=${PYTHON_BIN:-python3}
exec "$python_bin" -m workload_common.single_v2 prepare --case baleen --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload}" "$@"

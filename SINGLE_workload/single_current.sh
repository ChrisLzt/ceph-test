#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo"
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  echo 'Usage: single_current.sh [preview|render|validate|preflight|verify|parser-check|prepare|run] [CLI options]'
  echo 'Default preview is offline. prepare/run require --execute and prior user authorization.'
  exit 0
fi
action=${1:-preview}
if (($#)); then shift; fi
python_bin=${PYTHON_BIN:-python3}
extra=()
if [[ -n ${DATA_ROOT:-} ]]; then extra+=(--data-root "$DATA_ROOT"); fi
if [[ $action == run ]]; then
  extra+=(--vdbench "${VDBENCH_HOME:-/home/chris/PDSL/vdbench}/vdbench")
fi
exec "$python_bin" -m workload_common.single_v2 "$action" --case all \
  --design current --profile current --rate max \
  --output-root "${CONFIG_ROOT:-$repo/SINGLE_workload}" "${extra[@]}" "$@"

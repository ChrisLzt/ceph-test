#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$root/.." && pwd)
workloads=(
  bigdata_mapreduce_no_migration_v1
  graph_graphchi_no_migration_v1
  hpc_wrf_no_migration_v1
  ai_training_no_migration_v1
  ai_inference_no_migration_v1
)

cd "$repo"
for workload in "${workloads[@]}"; do
  "$root/$workload/render_config.sh" >/dev/null
done

python3 -m unittest discover -s no_migration_workload/tests -v
find no_migration_workload -name '*.sh' -print0 | xargs -0 -n1 bash -n

vdbench_bin=${VDBENCH_BIN:-${VDBENCH_HOME:-/home/chris/PDSL/vdbench}/vdbench}
if [[ ! -x "$vdbench_bin" ]]; then
  echo "Vdbench executable is missing: $vdbench_bin" >&2
  exit 1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for workload in "${workloads[@]}"; do
  config="$root/$workload/rendered/run_test.vdb"
  "$vdbench_bin" -f "$config" -o "$tmp/$workload" -s -e 2 >/dev/null
  echo "PASS: Vdbench parsed $workload/rendered/run_test.vdb"
done

echo "PASS: all no-migration workloads validated"

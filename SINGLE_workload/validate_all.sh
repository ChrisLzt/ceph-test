#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo"

workloads=(
    bigdata_mapreduce_vdbench_v1
    graph_graphchi_vdbench_v1
    hpc_wrf_vdbench_v1
    ai_training_checkpoint_vdbench_v1
    ai_inference_kvcache_vdbench_v1
)

for workload in "${workloads[@]}"; do
    "SINGLE_workload/$workload/render_config.sh" all >/dev/null
done

python3 -m unittest discover -s workload_common/tests -v
find SINGLE_workload -name '*.sh' -print0 | xargs -0 -n1 bash -n
SINGLE_workload/hpc_wrf_ior_v1/validate_model.sh

vdbench_bin=${VDBENCH_BIN:-${VDBENCH_HOME:-/home/chris/PDSL/vdbench}/vdbench}
python3 -m workload_common.validate_vdbench \
    SINGLE_workload \
    --vdbench "$vdbench_bin"

echo "PASS: all single-node workloads validated"

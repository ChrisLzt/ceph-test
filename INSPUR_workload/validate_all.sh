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
    ANCHOR_ROOT=/__INSPUR_CEPHFS__ \
        "INSPUR_workload/$workload/render_config.sh"
done

python3 -m unittest discover -s workload_common/tests -v
python3 -m unittest discover -s INSPUR_workload/tests -v
find INSPUR_workload -name '*.sh' -print0 | xargs -0 -n1 bash -n
ANCHOR_ROOT=/__INSPUR_CEPHFS__ \
    INSPUR_workload/hpc_wrf_ior_v1/validate_model.sh

vdbench_bin=${VDBENCH_BIN:-${VDBENCH_HOME:-/home/chris/PDSL/vdbench}/vdbench}
python3 -m workload_common.validate_vdbench \
    INSPUR_workload \
    --vdbench "$vdbench_bin"

echo "PASS: all INSPUR workloads validated"

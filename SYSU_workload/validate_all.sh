#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo"

python3 -m unittest discover -s SYSU_workload/tests -v
find SYSU_workload -name '*.sh' -print0 | xargs -0 -n1 bash -n
ANCHOR_ROOT=/__SYSU_CEPHFS__ \
    SYSU_workload/hpc_wrf_ior_v1/validate_model.sh

echo "PASS: all SYSU workloads validated"

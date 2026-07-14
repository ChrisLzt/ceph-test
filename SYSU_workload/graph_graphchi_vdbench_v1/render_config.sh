#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"

output_dir=${OUTPUT_DIR:-$root/rendered}
threads=${THREADS:-1}
phase_seconds=${PHASE_SECONDS:-120}
fwdrate=${FWD_RATE:-max}

cd -- "$(dirname -- "$root")/.."
python3 -m SYSU_workload.graph_graphchi_vdbench_v1.scripts.render \
    --anchor-root "$ANCHOR_ROOT" \
    --output-dir "$output_dir" \
    --threads "$threads" \
    --phase-seconds "$phase_seconds" \
    --fwdrate "$fwdrate"

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"

output_dir=${OUTPUT_DIR:-$root/rendered}
threads=${THREADS:-1}
dataset_phase_seconds=${DATASET_PHASE_SECONDS:-160}
checkpoint_phase_seconds=${CHECKPOINT_PHASE_SECONDS:-60}
fwdrate=${FWD_RATE:-max}

cd -- "$(dirname -- "$root")/.."
python3 -m SYSU_workload.ai_training_checkpoint_vdbench_v1.scripts.render \
    --anchor-root "$ANCHOR_ROOT" \
    --output-dir "$output_dir" \
    --threads "$threads" \
    --dataset-phase-seconds "$dataset_phase_seconds" \
    --checkpoint-phase-seconds "$checkpoint_phase_seconds" \
    --fwdrate "$fwdrate"

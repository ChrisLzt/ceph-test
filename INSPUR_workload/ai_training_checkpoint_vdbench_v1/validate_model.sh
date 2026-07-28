#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python3 -m unittest \
    INSPUR_workload.tests.test_vdbench_workloads.InspurVdbenchRendererTests.test_ai_training_uses_dataset_reads_checkpoint_write_and_recovery \
    -v
echo "PASS: INSPUR AI training workload validated"

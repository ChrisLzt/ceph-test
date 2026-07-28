#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python3 -m unittest \
    INSPUR_workload.tests.test_vdbench_workloads.InspurVdbenchRendererTests.test_ai_inference_uses_write_prefill_and_read_decode \
    -v
echo "PASS: INSPUR AI inference workload validated"

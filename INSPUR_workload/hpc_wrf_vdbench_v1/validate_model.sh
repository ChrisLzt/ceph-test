#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python3 -m unittest \
    INSPUR_workload.tests.test_vdbench_workloads.InspurVdbenchRendererTests.test_hpc_uses_read_write_write_read \
    -v
echo "PASS: INSPUR WRF Vdbench workload validated"

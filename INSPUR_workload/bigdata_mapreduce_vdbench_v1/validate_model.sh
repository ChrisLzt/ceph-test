#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python3 -m unittest \
    INSPUR_workload.tests.test_vdbench_workloads.InspurVdbenchRendererTests.test_mapreduce_preserves_four_read_stages_and_two_hundred_fwds \
    -v
echo "PASS: INSPUR MapReduce workload validated"

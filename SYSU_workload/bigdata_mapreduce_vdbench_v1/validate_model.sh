#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$repo"
python3 -m unittest SYSU_workload.tests.test_bigdata -v
echo "PASS: SYSU MapReduce workload validated"

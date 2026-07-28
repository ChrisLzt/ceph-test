#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$root/../.."
python3 -m unittest INSPUR_workload.tests.test_hpc_ior -v

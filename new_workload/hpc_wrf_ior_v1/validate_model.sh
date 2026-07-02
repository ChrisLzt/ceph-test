#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh all >/dev/null
bash -n configs/prepare_data.sh.in
bash -n configs/run_test.sh.in
bash -n rendered/prepare_data.sh
bash -n rendered/run_test.sh
python3 tests/validate_hpc_workload.py

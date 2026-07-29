#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh run

vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
output_dir=${OUTPUT_DIR:-output/run_test}

"$vdbench_home/vdbench" \
  -f rendered/run_test.vdb \
  -o "$output_dir"

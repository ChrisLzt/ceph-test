#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh prepare

anchor=${ANCHOR:-/mnt/cephfs/ai_inference_kvcache_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
output_dir=${OUTPUT_DIR:-output/prepare_data}

mkdir -p "$anchor"
echo "Ensured data anchor: $anchor"

"$vdbench_home/vdbench" \
  -f rendered/prepare_data.vdb \
  -o "$output_dir"

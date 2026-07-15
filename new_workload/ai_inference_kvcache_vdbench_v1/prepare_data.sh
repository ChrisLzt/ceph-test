#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh prepare

anchor=${ANCHOR:-${ANCHOR_ROOT:-/mnt/cephfs}/ai_inference_kvcache_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
output_dir=${OUTPUT_DIR:-output/prepare_data}

mkdir -p "$anchor"
echo "Ensured data anchor: $anchor"
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'rank_*' \
  -prune -exec rm -rf -- {} +
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'size_*m' \
  -prune -exec rm -rf -- {} +

stale_dirs=(
  kv_active_01 kv_active_02 kv_active_03 kv_active_04
  kv_next_01 kv_next_02 kv_next_03 kv_next_04
  kv_prefix_reuse_01 kv_prefix_reuse_02 kv_prefix_reuse_03 kv_prefix_reuse_04
  kv_cold_01 kv_cold_02
)

for stale in "${stale_dirs[@]}"; do
  if [[ -e "$anchor/$stale" ]]; then
    echo "Removing stale KV-cache directory: $anchor/$stale"
    rm -rf -- "$anchor/$stale"
  fi
done

"$vdbench_home/vdbench" \
  -f rendered/prepare_data.vdb \
  -o "$output_dir"

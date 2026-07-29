#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh prepare

anchor=${ANCHOR:-${ANCHOR_ROOT:-/mnt/cephfs}/ai_training_checkpoint_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
output_dir=${OUTPUT_DIR:-output/prepare_data}

mkdir -p "$anchor"
echo "Ensured data anchor: $anchor"
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'rank_*' \
  -prune -exec rm -rf -- {} +
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'size_*m' \
  -prune -exec rm -rf -- {} +

stale_dirs=(
  dataset_hot_01 dataset_hot_02 dataset_hot_03 dataset_hot_04
  dataset_warm_01 dataset_warm_02 dataset_warm_03 dataset_warm_04
  dataset_cold_01 dataset_cold_02 dataset_cold_03 dataset_cold_04
)

for stale in "${stale_dirs[@]}"; do
  if [[ -e "$anchor/$stale" ]]; then
    echo "Removing stale training dataset directory: $anchor/$stale"
    rm -rf -- "$anchor/$stale"
  fi
done

"$vdbench_home/vdbench" \
  -f rendered/prepare_data.vdb \
  -o "$output_dir"

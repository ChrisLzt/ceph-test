#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh prepare

anchor=${ANCHOR:-${ANCHOR_ROOT:-/mnt/cephfs}/hpc_wrf_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
output_dir=${OUTPUT_DIR:-output/prepare_data}

mkdir -p "$anchor"
echo "Ensured data anchor: $anchor"
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'rank_*' \
    -prune -exec rm -rf -- {} +
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'size_*m' \
    -prune -exec rm -rf -- {} +

"$vdbench_home/vdbench" \
    -f rendered/prepare_data.vdb \
    -o "$output_dir"

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
anchor=${ANCHOR_ROOT%/}/ai_inference_kvcache_vdbench_v1

mkdir -p -- "$anchor"
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'rank_*' \
    -prune -exec rm -rf -- {} +
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'size_*m' \
    -prune -exec rm -rf -- {} +
"$root/render_config.sh"
exec "$vdbench_home/vdbench" -f "$root/rendered/prepare_data.vdb" \
    -o "$root/output/prepare_data"

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
anchor=${ANCHOR_ROOT%/}/bigdata_mapreduce_vdbench_v1

mkdir -p -- "$anchor"
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'rank_*' \
    -prune -exec rm -rf -- {} +
find "$anchor" -mindepth 2 -maxdepth 2 -type d -name 'size_*m' \
    -prune -exec rm -rf -- {} +
for stale in pool_04 pool_05; do
    if [[ -d "$anchor/$stale" ]]; then
        echo "Removing stale MapReduce pool directory: $anchor/$stale"
        rm -rf -- "$anchor/$stale"
    fi
done
"$root/render_config.sh"
exec "$vdbench_home/vdbench" -f "$root/rendered/prepare_data.vdb" \
    -o "$root/output/prepare_data"

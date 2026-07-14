#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}

mkdir -p -- "$ANCHOR_ROOT/bigdata_mapreduce_vdbench_v1"
"$root/render_config.sh"
exec "$vdbench_home/vdbench" -f "$root/rendered/prepare_data.vdb" \
    -o "$root/output/prepare_data"

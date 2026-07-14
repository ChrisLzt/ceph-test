#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"
rendered_dir=${RENDERED_DIR:-$root/rendered}

mkdir -p -- "$ANCHOR_ROOT/hpc_wrf_ior_v1"
"$root/render_config.sh"
exec "$rendered_dir/prepare_data.sh"

#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

./render_config.sh prepare

anchor=${ANCHOR:-/mnt/cephfs/hpc_wrf_ior_v1}
mkdir -p "$anchor"
echo "Ensured data anchor: $anchor"

exec ./rendered/prepare_data.sh

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}

"$root/render_config.sh"
exec "$vdbench_home/vdbench" -f "$root/rendered/run_test.vdb" \
    -o "$root/output/run_test"

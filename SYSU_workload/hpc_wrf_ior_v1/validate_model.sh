#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

ANCHOR_ROOT=${ANCHOR_ROOT:-/__SYSU_CEPHFS__} \
PHASE_SECONDS=150 \
RENDERED_DIR=$tmp \
    "$root/render_config.sh"
python3 "$root/tests/validate_hpc_ior.py" "$tmp"

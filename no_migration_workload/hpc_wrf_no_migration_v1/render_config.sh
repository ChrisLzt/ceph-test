#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$root/../.." && pwd)
hd_line=$(printf 'hd=default,vdbench=%s,user=%s,shell=ssh\nhd=hd1,system=%s' \
  "${VDBENCH_HOME:-/home/chris/PDSL/vdbench}" "${REMOTE_USER:-chris}" \
  "${HOST1:-s52.servers.hustpdsl.cn}")
cd "$repo"
python3 -m no_migration_workload.scripts.render \
  --workload hpc_wrf_no_migration_v1 \
  --anchor-root "${ANCHOR_ROOT:-/mnt/cephfs}" --output-dir "$root/rendered" \
  --hd-line "$hd_line" --threads "${THREADS:-1}" --fwdrate "${FWD_RATE:-max}"

#!/usr/bin/env bash
set -euo pipefail

profile=${1:-all}
[[ "$profile" =~ ^(all|prepare|run)$ ]] || { echo "Usage: $0 [all|prepare|run]" >&2; exit 2; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$root/../.." && pwd)
workload=graph_graphchi_vdbench_v1
anchor=${ANCHOR:-/mnt/cephfs/$workload}
anchor_root=${ANCHOR_ROOT:-${anchor%/$workload}}

cd "$repo"
python3 -m SINGLE_workload.$workload.scripts.render \
  --anchor-root "$anchor_root" --output-dir "$root/rendered" \
  --host "${HOST1:-s52.servers.hustpdsl.cn}" --remote-user "${REMOTE_USER:-chris}" \
  --vdbench-home "${VDBENCH_HOME:-/home/chris/PDSL/vdbench}" \
  --threads "${THREADS:-1}" --phase-seconds "${PHASE_SECONDS:-150}" \
  --fwdrate "${FWD_RATE:-max}"
echo "Rendered $profile profile: $root/rendered"

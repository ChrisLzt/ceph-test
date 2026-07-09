#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

anchor=${ANCHOR:-/mnt/cephfs/bigdata_mapreduce_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-150}
fwd_rate=${FWD_RATE:-max}
threads=${THREADS:-16}

for value in "$phase_seconds" "$threads"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
        echo "Numeric parameters must be positive integers: $value" >&2
        exit 2
    }
done

[[ "$fwd_rate" == "max" || "$fwd_rate" =~ ^[1-9][0-9]*$ ]] || {
    echo "FWD_RATE must be a positive integer or max: $fwd_rate" >&2
    exit 2
}

mkdir -p rendered

sed \
    -e "s|@ANCHOR@|$anchor|g" \
    -e "s|@VDBENCH_HOME@|$vdbench_home|g" \
    -e "s|@REMOTE_USER@|$remote_user|g" \
    -e "s|@HOST1@|$host1|g" \
    -e "s|@PHASE_SECONDS@|$phase_seconds|g" \
    -e "s|@FWD_RATE@|$fwd_rate|g" \
    -e "s|@THREADS@|$threads|g" \
    configs/run_test.vdb.in > rendered/run_test.vdb

if grep -q '@[A-Z_][A-Z_]*@' rendered/run_test.vdb; then
    echo "Unresolved template variable in rendered/run_test.vdb" >&2
    exit 1
fi

echo "Rendered: $script_dir/rendered/run_test.vdb"
echo "Fixed hot pool: pool_01; phase=${phase_seconds}s; fwdrate=$fwd_rate; anchor=$anchor"

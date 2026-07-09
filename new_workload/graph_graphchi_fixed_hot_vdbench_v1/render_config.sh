#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

anchor=${ANCHOR:-/mnt/cephfs/graph_graphchi_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-75}
fwd_rate=${FWD_RATE:-max}
threads=${THREADS:-16}
files_per_shard=${FILES_PER_SHARD:-1800}
file_size=${FILE_SIZE:-16m}
xfer_size=${XFER_SIZE:-1m}

for value in "$phase_seconds" "$threads" "$files_per_shard"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
        echo "Numeric parameters must be positive integers: $value" >&2
        exit 2
    }
done

[[ "$fwd_rate" == "max" || "$fwd_rate" =~ ^[1-9][0-9]*$ ]] || {
    echo "FWD_RATE must be a positive integer or max: $fwd_rate" >&2
    exit 2
}

[[ "$file_size" =~ ^[1-9][0-9]*[kKmMgGtT]$ ]] || {
    echo "FILE_SIZE must use vdbench size syntax, e.g. 16m or 1g: $file_size" >&2
    exit 2
}
[[ "$xfer_size" =~ ^[1-9][0-9]*[kKmMgGtT]$ ]] || {
    echo "XFER_SIZE must use vdbench size syntax, e.g. 1m: $xfer_size" >&2
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
    -e "s|@FILES_PER_SHARD@|$files_per_shard|g" \
    -e "s|@FILE_SIZE@|$file_size|g" \
    -e "s|@XFER_SIZE@|$xfer_size|g" \
    configs/run_test.vdb.in > rendered/run_test.vdb

if grep -q '@[A-Z_][A-Z_]*@' rendered/run_test.vdb; then
    echo "Unresolved template variable in rendered/run_test.vdb" >&2
    exit 1
fi

echo "Rendered: $script_dir/rendered/run_test.vdb"
echo "Fixed hot shard: shard_00; phase=${phase_seconds}s; fwdrate=$fwd_rate; anchor=$anchor"

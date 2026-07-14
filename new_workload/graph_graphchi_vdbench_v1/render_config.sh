#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [all|prepare|run]" >&2
    echo "  all     render both prepare_data.vdb and run_test.vdb" >&2
    echo "  prepare render only prepare_data.vdb" >&2
    echo "  run     render only run_test.vdb" >&2
}

profile=${1:-all}
case "$profile" in
    all|prepare|run) ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
esac

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

edge_file=${EDGE_FILE:-datasets/smoke_edges.tsv}

anchor=${ANCHOR:-/mnt/cephfs/graph_graphchi_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-120}
fwd_rate=${FWD_RATE:-1000}
threads=${THREADS:-16}
files_per_shard=${FILES_PER_SHARD:-1800}
file_size=${FILE_SIZE:-16m}
xfer_size=${XFER_SIZE:-4m}
intervals=${INTERVALS:-4}
vertices_per_interval=${VERTICES_PER_INTERVAL:-128}
iterations=${ITERATIONS:-1}
reheat_interval=${REHEAT_INTERVAL:-0}

for value in "$phase_seconds" "$threads" "$files_per_shard" "$intervals" "$vertices_per_interval" "$iterations"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
        echo "Numeric parameters must be positive integers: $value" >&2
        exit 2
    }
done

[[ "$reheat_interval" =~ ^[0-9]+$ ]] && (( reheat_interval < intervals )) || {
    echo "REHEAT_INTERVAL must be an integer in [0, INTERVALS): $reheat_interval" >&2
    exit 2
}

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

if [[ "$edge_file" == "datasets/smoke_edges.tsv" ]]; then
    python3 scripts/generate_graph.py \
        --output "$edge_file" \
        --intervals "$intervals" \
        --vertices-per-interval "$vertices_per_interval"
elif [[ ! -f "$edge_file" ]]; then
    echo "EDGE_FILE does not exist: $edge_file" >&2
    exit 2
fi

python3 scripts/derive_profile.py \
    --edges "$edge_file" \
    --prepare-template configs/prepare_data.vdb.in \
    --run-template configs/run_test.vdb.in \
    --intervals "$intervals" \
    --vertices-per-interval "$vertices_per_interval" \
    --iterations "$iterations" \
    --reheat-interval "$reheat_interval" >/dev/null

render_one() {
    local template=$1
    local output=$2

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
        "$template" > "$output"

    if grep -q '@[A-Z_][A-Z_]*@' "$output"; then
        echo "Unresolved template variable in $output" >&2
        exit 1
    fi
    echo "Rendered: $script_dir/$output"
}

case "$profile" in
    all)
        render_one "configs/prepare_data.vdb.in" "rendered/prepare_data.vdb"
        render_one "configs/run_test.vdb.in" "rendered/run_test.vdb"
        ;;
    prepare)
        render_one "configs/prepare_data.vdb.in" "rendered/prepare_data.vdb"
        ;;
    run)
        render_one "configs/run_test.vdb.in" "rendered/run_test.vdb"
        ;;
esac

echo "Profile: $profile; edge_file=$edge_file; phase=${phase_seconds}s; reheat_interval=$reheat_interval; fwdrate=$fwd_rate; anchor=$anchor"

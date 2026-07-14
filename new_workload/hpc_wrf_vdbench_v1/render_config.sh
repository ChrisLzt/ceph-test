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

anchor=${ANCHOR:-/mnt/cephfs/hpc_wrf_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-150}
fwd_rate=${FWD_RATE:-1000}
threads=${THREADS:-4}
format_threads=${FORMAT_THREADS:-8}
files_per_rank=${FILES_PER_RANK:-120}
file_size=${FILE_SIZE:-16m}
xfer_size=${XFER_SIZE:-4m}
rank_count=${RANK_COUNT:-20}
objects_per_rank=${OBJECTS_PER_RANK:-480}
zipf_alpha=${ZIPF_ALPHA:-0.99}

for value in "$phase_seconds" "$threads" "$format_threads" "$files_per_rank"; do
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
    echo "FILE_SIZE must use vdbench size syntax, e.g. 16m: $file_size" >&2
    exit 2
}
[[ "$xfer_size" =~ ^[1-9][0-9]*[kKmMgGtT]$ ]] || {
    echo "XFER_SIZE must use vdbench size syntax, e.g. 1m: $xfer_size" >&2
    exit 2
}
[[ "$rank_count" == "20" ]] || {
    echo "RANK_COUNT is fixed at 20 for the documented Zipf profile: $rank_count" >&2
    exit 2
}
[[ "$objects_per_rank" == "480" ]] || {
    echo "OBJECTS_PER_RANK is fixed at 480 for the documented Zipf profile: $objects_per_rank" >&2
    exit 2
}
[[ "$zipf_alpha" == "0.99" ]] || {
    echo "ZIPF_ALPHA is fixed at 0.99 for the documented Zipf profile: $zipf_alpha" >&2
    exit 2
}

mkdir -p configs rendered

python3 scripts/derive_zipf_profile.py \
    --prepare-template configs/prepare_data.vdb.in \
    --run-template configs/run_test.vdb.in \
    --rank-count "$rank_count" \
    --objects-per-rank "$objects_per_rank" \
    --alpha "$zipf_alpha" >/dev/null

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
        -e "s|@FORMAT_THREADS@|$format_threads|g" \
        -e "s|@FILES_PER_RANK@|$files_per_rank|g" \
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
        render_one configs/prepare_data.vdb.in rendered/prepare_data.vdb
        render_one configs/run_test.vdb.in rendered/run_test.vdb
        ;;
    prepare)
        render_one configs/prepare_data.vdb.in rendered/prepare_data.vdb
        ;;
    run)
        render_one configs/run_test.vdb.in rendered/run_test.vdb
        ;;
esac

echo "Profile: $profile; phase=${phase_seconds}s; fwdrate=$fwd_rate; anchor=$anchor"

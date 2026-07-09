#!/usr/bin/env bash
set -euo pipefail

profile=${1:-all}
if [[ $# -gt 1 || ! "$profile" =~ ^(all|prepare|run)$ ]]; then
    echo "Usage: $0 [all|prepare|run]" >&2
    echo "  all     render both prepare_data.vdb and run_test.vdb" >&2
    echo "  prepare render only prepare_data.vdb" >&2
    echo "  run     render only run_test.vdb" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

anchor=${ANCHOR:-/mnt/cephfs/bigdata_mapreduce_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-150}
fwd_rate=${FWD_RATE:-max}
threads=${THREADS:-16}
format_threads=${FORMAT_THREADS:-32}

for value in "$phase_seconds" "$threads" "$format_threads"; do
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

echo "Profile: $profile; phase=${phase_seconds}s; fwdrate=$fwd_rate; anchor=$anchor"

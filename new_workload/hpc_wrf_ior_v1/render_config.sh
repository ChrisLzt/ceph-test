#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [all|prepare|run]" >&2
    echo "  all     render both prepare_data.sh and run_test.sh" >&2
    echo "  prepare render only prepare_data.sh" >&2
    echo "  run     render only run_test.sh" >&2
}

profile=${1:-all}
case "$profile" in
    all|prepare|run) ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
esac

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$script_dir"

anchor=${ANCHOR:-/mnt/cephfs/hpc_wrf_ior_v1}
ior_bin=${IOR_BIN:-/home/chris/PDSL/ior/src/ior}
mpi_run=${MPI_RUN:-/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun}
np=${NP:-4}
api=${API:-POSIX}
block_size=${BLOCK_SIZE:-4g}
transfer_size=${TRANSFER_SIZE:-1m}
segment_count=${SEGMENT_COUNT:-1}
phase_seconds=${PHASE_SECONDS:-75}
ior_iterations=${IOR_ITERATIONS:-4}

for value in "$np" "$segment_count" "$phase_seconds" "$ior_iterations"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
        echo "Numeric parameters must be positive integers: $value" >&2
        exit 2
    }
done

[[ "$block_size" =~ ^[1-9][0-9]*[kKmMgGtT]$ ]] || {
    echo "BLOCK_SIZE must use IOR size syntax, e.g. 4g: $block_size" >&2
    exit 2
}
[[ "$transfer_size" =~ ^[1-9][0-9]*[kKmMgGtT]$ ]] || {
    echo "TRANSFER_SIZE must use IOR size syntax, e.g. 1m: $transfer_size" >&2
    exit 2
}

mkdir -p rendered

render_one() {
    local template=$1
    local output=$2

    sed \
        -e "s|@ANCHOR@|$anchor|g" \
        -e "s|@IOR_BIN@|$ior_bin|g" \
        -e "s|@MPI_RUN@|$mpi_run|g" \
        -e "s|@NP@|$np|g" \
        -e "s|@API@|$api|g" \
        -e "s|@BLOCK_SIZE@|$block_size|g" \
        -e "s|@TRANSFER_SIZE@|$transfer_size|g" \
        -e "s|@SEGMENT_COUNT@|$segment_count|g" \
        -e "s|@PHASE_SECONDS@|$phase_seconds|g" \
        -e "s|@IOR_ITERATIONS@|$ior_iterations|g" \
        "$template" > "$output"

    if grep -q '@[A-Z_][A-Z_]*@' "$output"; then
        echo "Unresolved template variable in $output" >&2
        exit 1
    fi
    chmod +x "$output"
    echo "Rendered: $script_dir/$output"
}

case "$profile" in
    all)
        render_one "configs/prepare_data.sh.in" "rendered/prepare_data.sh"
        render_one "configs/run_test.sh.in" "rendered/run_test.sh"
        ;;
    prepare)
        render_one "configs/prepare_data.sh.in" "rendered/prepare_data.sh"
        ;;
    run)
        render_one "configs/run_test.sh.in" "rendered/run_test.sh"
        ;;
esac

echo "Profile: $profile; np=$np; block=$block_size; transfer=$transfer_size; phase=${phase_seconds}s; ior_iterations=$ior_iterations; anchor=$anchor"

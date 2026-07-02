#!/usr/bin/env bash
set -euo pipefail

# HPC WRF IOR v1 - run only.
# Runs formal hot/cold phases against an existing dataset.

ANCHOR="/mnt/cephfs/hpc_wrf_ior_v1"
IOR_BIN="/home/chris/PDSL/ior/src/ior"
MPI_RUN="/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun"
NP="4"
API="POSIX"
BLOCK_SIZE="4g"
TRANSFER_SIZE="1m"
SEGMENT_COUNT="1"
PHASE_SECONDS="75"
OUTPUT_DIR="${OUTPUT_DIR:-output/run_test}"

mkdir -p "$ANCHOR/input" "$ANCHOR/restart" "$ANCHOR/checkpoint" "$ANCHOR/history" "$OUTPUT_DIR"

run_ior_read() {
    local phase=$1
    local target=$2
    local log="$OUTPUT_DIR/${phase}.log"
    echo "== $phase read $target =="
    "$MPI_RUN" -np "$NP" "$IOR_BIN" \
        -a "$API" -F -r -k -C \
        -o "$target" \
        -b "$BLOCK_SIZE" \
        -t "$TRANSFER_SIZE" \
        -s "$SEGMENT_COUNT" \
        -D "$PHASE_SECONDS" \
        -i 1 \
        2>&1 | tee "$log"
}

run_ior_write() {
    local phase=$1
    local target=$2
    local log="$OUTPUT_DIR/${phase}.log"
    echo "== $phase write $target =="
    "$MPI_RUN" -np "$NP" "$IOR_BIN" \
        -a "$API" -F -w -k -e -C \
        -o "$target" \
        -b "$BLOCK_SIZE" \
        -t "$TRANSFER_SIZE" \
        -s "$SEGMENT_COUNT" \
        -D "$PHASE_SECONDS" \
        -i 1 \
        2>&1 | tee "$log"
}

run_ior_read startup_read_wrfinput "$ANCHOR/input/wrfinput_d01"
run_ior_read startup_read_wrfbdy "$ANCHOR/input/wrfbdy_d01"
run_ior_read startup_read_restart "$ANCHOR/restart/wrfrst_initial"

run_ior_write checkpoint_write_current "$ANCHOR/checkpoint/wrfrst_current"
run_ior_read checkpoint_hot_read_current "$ANCHOR/checkpoint/wrfrst_current"

run_ior_write history_write_current "$ANCHOR/history/wrfout_current"
run_ior_read history_hot_read_current "$ANCHOR/history/wrfout_current"

run_ior_read recovery_reheat_read_old_checkpoint "$ANCHOR/checkpoint/wrfrst_old"

#!/usr/bin/env bash
set -euo pipefail

# HPC WRF IOR v1 - run only.
# Runs formal hot/cold phases against an existing dataset.

ANCHOR="/mnt/cephfs/hpc_wrf_ior_v1"
IOR_BIN="/home/chris/PDSL/ior/src/ior"
MPI_RUN="/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun"
NP="4"
API="POSIX"
BLOCK_SIZE="9600m"
TRANSFER_SIZE="4m"
SEGMENT_COUNT="1"
PHASE_SECONDS="150"
OUTPUT_DIR="${OUTPUT_DIR:-output/run_test}"

mkdir -p "$ANCHOR/startup" "$ANCHOR/checkpoint" "$ANCHOR/history" "$OUTPUT_DIR"

run_ior_read() {
    local phase=$1
    local target=$2
    local log="$OUTPUT_DIR/${phase}.log"
    echo "== $phase read $target =="
    "$MPI_RUN" -np "$NP" "$IOR_BIN" \
        -a "$API" --posix.odirect -F -r -k -C \
        -o "$target" \
        -b "$BLOCK_SIZE" \
        -t "$TRANSFER_SIZE" \
        -s "$SEGMENT_COUNT" \
        -i 1 \
        -D "$PHASE_SECONDS" \
        -O "minTimeDuration=$PHASE_SECONDS" \
        -O stoneWallingWearOut=0 \
        2>&1 | tee "$log"
}

run_ior_read startup_read "$ANCHOR/startup/wrf_state"
run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"
run_ior_read history_read "$ANCHOR/history/wrfout_current"
run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"

#!/usr/bin/env bash
set -euo pipefail

# HPC WRF IOR v1 - prepare only.
# Creates/overwrites the dataset. Do not use for repeated measurement runs.

ANCHOR="/mnt/cephfs/hpc_wrf_ior_v1"
IOR_BIN="/home/chris/PDSL/ior/src/ior"
MPI_RUN="/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun"
NP="4"
API="POSIX"
BLOCK_SIZE="4g"
TRANSFER_SIZE="1m"
SEGMENT_COUNT="1"
OUTPUT_DIR="${OUTPUT_DIR:-output/prepare_data}"

mkdir -p "$ANCHOR/input" "$ANCHOR/restart" "$ANCHOR/checkpoint" "$ANCHOR/history" "$OUTPUT_DIR"

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
        -i 1 \
        2>&1 | tee "$log"
}

run_ior_write prepare_wrfinput "$ANCHOR/input/wrfinput_d01"
run_ior_write prepare_wrfbdy "$ANCHOR/input/wrfbdy_d01"
run_ior_write prepare_restart_initial "$ANCHOR/restart/wrfrst_initial"
run_ior_write prepare_checkpoint_old "$ANCHOR/checkpoint/wrfrst_old"
run_ior_write prepare_history_old "$ANCHOR/history/wrfout_old"
run_ior_write prepare_checkpoint_current "$ANCHOR/checkpoint/wrfrst_current"
run_ior_write prepare_history_current "$ANCHOR/history/wrfout_current"

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${ANCHOR_ROOT:?Set ANCHOR_ROOT to the shared CephFS data root}"

if [[ "$ANCHOR_ROOT" != /* ]]; then
    echo "ANCHOR_ROOT must be an absolute path: $ANCHOR_ROOT" >&2
    exit 2
fi

ior_bin=${IOR_BIN:-/home/chris/PDSL/ior/src/ior}
mpi_run=${MPI_RUN:-mpirun}
mpi_hostfile=${MPI_HOSTFILE:-}
phase_seconds=${PHASE_SECONDS:-150}
rendered_dir=${RENDERED_DIR:-$root/rendered}
anchor=${ANCHOR_ROOT%/}/hpc_wrf_ior_v1

if [[ ! "$phase_seconds" =~ ^[1-9][0-9]*$ ]]; then
    echo "PHASE_SECONDS must be a positive integer: $phase_seconds" >&2
    exit 2
fi

for value in "$anchor" "$ior_bin" "$mpi_run" "$mpi_hostfile" "$rendered_dir"; do
    if [[ "$value" == *$'\n'* || "$value" == *'|'* ]]; then
        echo "Paths and commands must not contain newlines or '|': $value" >&2
        exit 2
    fi
done

escape_replacement() {
    printf '%s' "$1" | sed -e 's/[\\&]/\\&/g'
}

mkdir -p -- "$rendered_dir"

render_one() {
    local template=$1
    local output=$2
    sed \
        -e "s|@ANCHOR@|$(escape_replacement "$anchor")|g" \
        -e "s|@IOR_BIN@|$(escape_replacement "$ior_bin")|g" \
        -e "s|@MPI_RUN@|$(escape_replacement "$mpi_run")|g" \
        -e "s|@MPI_HOSTFILE@|$(escape_replacement "$mpi_hostfile")|g" \
        -e "s|@PHASE_SECONDS@|$phase_seconds|g" \
        "$template" > "$output"

    if grep -Eq '@[A-Z_][A-Z_]*@' "$output"; then
        echo "Unresolved template variable in $output" >&2
        exit 1
    fi
    chmod +x "$output"
}

render_one "$root/configs/prepare_data.sh.in" "$rendered_dir/prepare_data.sh"
render_one "$root/configs/run_test.sh.in" "$rendered_dir/run_test.sh"

echo "Rendered INSPUR HPC IOR: anchor=$anchor np=4 block=256000m transfer=4m phase=${phase_seconds}s file_per_process=on"

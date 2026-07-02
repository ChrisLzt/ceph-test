#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_single_node_test}"
VDBENCH="${VDBENCH:-/home/chris/PDSL/vdbench/vdbench}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/out/${RUN_ID}}"
LOG_ROOT="${LOG_ROOT:-${SCRIPT_DIR}/logs/${RUN_ID}}"
VD_ARGS="${VD_ARGS:-}"

collect_configs() {
  find "${SCRIPT_DIR}" -path '*/运行测试/*.txt' -type f | sort
}

collect_anchor_dirs() {
  awk '
    /^fsd=/ {
      n = split($0, fields, ",")
      for (i = 1; i <= n; i++) {
        if (fields[i] ~ /^anchor=/) {
          path = fields[i]
          sub(/^anchor=/, "", path)
          if (path != "") {
            print path
          }
        }
      }
    }
  ' "$@"
}

mapfile -t configs < <(collect_configs)
if [[ "${#configs[@]}" -eq 0 ]]; then
  echo "no test config found under ${SCRIPT_DIR}" >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}" "${LOG_ROOT}"

mapfile -t anchor_dirs < <(collect_anchor_dirs "${configs[@]}" | sort -u)
for dir in "${anchor_dirs[@]}"; do
  mkdir -p "${dir}" 2>/dev/null || {
    echo "unable to create anchor directory: ${dir}" >&2
    echo "check that the Ceph test filesystem is mounted and writable." >&2
    echo "for CephFS, run the mount command in Ceph操作手册.md first." >&2
    exit 1
  }
done

echo "Run all single-node tests"
echo "Run ID:  ${RUN_ID}"
echo "Vdbench: ${VDBENCH}"
echo "Output:  ${OUT_ROOT}"
echo "Logs:    ${LOG_ROOT}"
echo "VD_ARGS: ${VD_ARGS}"
echo "Configs:"
printf '  %s\n' "${configs[@]}"

for cfg in "${configs[@]}"; do
  rel="${cfg#${SCRIPT_DIR}/}"
  suite="${rel%%/*}"
  name="$(basename "${cfg}" .txt)"
  out_dir="${OUT_ROOT}/${suite}/${name}"
  log_dir="${LOG_ROOT}/${suite}"
  log_file="${log_dir}/${name}.vdbench.log"

  mkdir -p "${out_dir}" "${log_dir}"

  echo
  echo "===== TEST ${suite}/${name} $(date '+%F %T') ====="
  echo "Config: ${cfg}"
  echo "Log:    ${log_file}"

  "${VDBENCH}" ${VD_ARGS} -f"${cfg}" -o"${out_dir}" >"${log_file}" 2>&1
done

echo
echo "All single-node test jobs finished: $(date '+%F %T')"
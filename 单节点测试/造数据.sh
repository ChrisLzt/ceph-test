#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-${SCRIPT_DIR}/冷热IO}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_single_node_data}"
VDBENCH="${VDBENCH:-/home/chris/PDSL/vdbench/vdbench}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/out/${RUN_ID}}"
LOG_ROOT="${LOG_ROOT:-${SCRIPT_DIR}/logs/${RUN_ID}}"
VD_ARGS="${VD_ARGS:-}"
CAPACITY_LIMIT_PERCENT="${CAPACITY_LIMIT_PERCENT:-85}"

collect_configs() {
  find "${DATA_ROOT}" -path '*/造数据/*.txt' -type f | sort
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

estimate_config_bytes() {
  python3 - "$@" <<'PY'
import re
import sys

UNIT = {
    "k": 1024,
    "m": 1024 ** 2,
    "g": 1024 ** 3,
    "t": 1024 ** 4,
}

def parse_size(value):
    value = value.strip().lower()
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kmgt]?)", value)
    if not m:
        return 0
    number = float(m.group(1))
    unit = m.group(2)
    return int(number * UNIT.get(unit, 1))

def weighted_size(spec):
    spec = spec.strip()
    if spec.startswith("(") and spec.endswith(")"):
        parts = [p.strip() for p in spec[1:-1].split(",") if p.strip()]
        if len(parts) % 2 != 0:
            return 0
        total_weight = 0.0
        total_size = 0.0
        for i in range(0, len(parts), 2):
            size = parse_size(parts[i])
            weight = float(parts[i + 1])
            total_size += size * weight
            total_weight += weight
        return int(total_size / total_weight) if total_weight > 0 else 0
    return parse_size(spec)

def field(line, name, default):
    m = re.search(r"(?:^|,)" + re.escape(name) + r"=([^,]+(?:\([^)]*\))?)", line)
    return m.group(1).strip() if m else default

total = 0
for path in sys.argv[1:]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line.startswith("fsd="):
                continue
            width = int(field(line, "width", "1"))
            files = int(field(line, "files", "1"))
            size = weighted_size(field(line, "sizes", "0"))
            total += width * files * size
print(total)
PY
}

check_capacity_limit() {
  local estimated_bytes fs_root total_bytes limit_bytes

  estimated_bytes="$(estimate_config_bytes "${configs[@]}")"
  fs_root="$(collect_anchor_dirs "${configs[@]}" | head -n 1)"
  fs_root="${fs_root:-/mnt/cephfs}"
  while [[ ! -d "${fs_root}" && "${fs_root}" != "/" ]]; do
    fs_root="$(dirname "${fs_root}")"
  done

  total_bytes="$(df -B1 --output=size "${fs_root}" | awk 'NR == 2 {print $1}')"
  limit_bytes=$(( total_bytes * CAPACITY_LIMIT_PERCENT / 100 ))

  echo "Estimated target data: $(( estimated_bytes / 1024 / 1024 / 1024 )) GiB"
  echo "Filesystem capacity:   $(( total_bytes / 1024 / 1024 / 1024 )) GiB (${fs_root})"
  echo "Capacity limit:        ${CAPACITY_LIMIT_PERCENT}% = $(( limit_bytes / 1024 / 1024 / 1024 )) GiB"

  if (( estimated_bytes > limit_bytes )); then
    echo "estimated data exceeds capacity limit; reduce test data or raise CAPACITY_LIMIT_PERCENT" >&2
    exit 1
  fi
}

mapfile -t configs < <(collect_configs)
if [[ "${#configs[@]}" -eq 0 ]]; then
  echo "no data config found under ${SCRIPT_DIR}" >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}" "${LOG_ROOT}"
check_capacity_limit

mapfile -t anchor_dirs < <(collect_anchor_dirs "${configs[@]}" | sort -u)
for dir in "${anchor_dirs[@]}"; do
  mkdir -p "${dir}" 2>/dev/null || {
    echo "unable to create anchor directory: ${dir}" >&2
    echo "check that the Ceph test filesystem is mounted and writable." >&2
    echo "for CephFS, run the mount command in Ceph操作手册.md first." >&2
    exit 1
  }
done

echo "Prepare all single-node test data"
echo "Run ID:  ${RUN_ID}"
echo "Data root: ${DATA_ROOT}"
echo "Vdbench: ${VDBENCH}"
echo "Output:  ${OUT_ROOT}"
echo "Logs:    ${LOG_ROOT}"
echo "VD_ARGS: ${VD_ARGS}"
echo "Capacity limit: ${CAPACITY_LIMIT_PERCENT}%"
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
  echo "===== DATA ${suite}/${name} $(date '+%F %T') ====="
  echo "Config: ${cfg}"
  echo "Log:    ${log_file}"

  "${VDBENCH}" ${VD_ARGS} -f"${cfg}" -o"${out_dir}" >"${log_file}" 2>&1
done

echo
echo "All single-node data preparation jobs finished: $(date '+%F %T')"

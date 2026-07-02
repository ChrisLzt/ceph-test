#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${CONFIG_DIR:-${SCRIPT_DIR}/冷热IO/运行测试}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_single_node_skew_io}"
VDBENCH="${VDBENCH:-/home/chris/PDSL/vdbench/vdbench}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/out/${RUN_ID}}"
LOG_ROOT="${LOG_ROOT:-${SCRIPT_DIR}/logs/${RUN_ID}}"
STATUS_ROOT="${STATUS_ROOT:-${SCRIPT_DIR}/hp_status/${RUN_ID}}"
BACKGROUND_ROOT="${BACKGROUND_ROOT:-${SCRIPT_DIR}/logs/background}"
VD_ARGS="${VD_ARGS:-}"
STATUS_INTERVAL="${STATUS_INTERVAL:-30}"
RESET_TIMEOUT="${RESET_TIMEOUT:-120}"
RESET_POLL_INTERVAL="${RESET_POLL_INTERVAL:-2}"

usage() {
  cat <<EOF
Usage:
  $0 run [config ...]          前台运行所有单节点冷热 IO 测试
  $0 background [config ...]   后台调用 run
  $0 bg [config ...]           background 的简写
  $0 stop                      停止所有后台冷热 IO 测试

Environment:
  CONFIG_DIR=${CONFIG_DIR}
  VDBENCH=${VDBENCH}
  STATUS_INTERVAL=${STATUS_INTERVAL}
  RESET_TIMEOUT=${RESET_TIMEOUT}
EOF
}

log() {
  echo "[$(date '+%F %T')] $*"
}

resolve_config() {
  local item="$1"

  if [[ -f "${item}" ]]; then
    realpath "${item}"
  elif [[ -f "${CONFIG_DIR}/${item}" ]]; then
    realpath "${CONFIG_DIR}/${item}"
  elif [[ -f "${CONFIG_DIR}/${item}.txt" ]]; then
    realpath "${CONFIG_DIR}/${item}.txt"
  else
    echo "config not found: ${item}" >&2
    return 1
  fi
}

collect_configs() {
  if [[ "$#" -gt 0 ]]; then
    local item
    for item in "$@"; do
      resolve_config "${item}"
    done
  else
    find "${CONFIG_DIR}" -maxdepth 1 -type f -name '*.txt' | sort
  fi
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

append_status_snapshot() {
  local label="$1"
  local status_file="$2"
  local tmp_json tmp_err ts
  tmp_json="$(mktemp)"
  tmp_err="$(mktemp)"
  ts="$(date '+%F %T')"

  if sudo -n ceph osd hp status -f json >"${tmp_json}" 2>"${tmp_err}"; then
    python3 - "${ts}" "${label}" "${tmp_json}" >>"${status_file}" <<'PY'
import json
import sys

ts, label, path = sys.argv[1:4]
with open(path, "r", encoding="utf-8") as f:
    status = json.load(f)
print(f"===== {ts} {label} =====")
print(json.dumps(status, ensure_ascii=False, indent=2))
print()
PY
  else
    python3 - "${ts}" "${label}" "${tmp_err}" >>"${status_file}" <<'PY'
import sys

ts, label, path = sys.argv[1:4]
with open(path, "r", encoding="utf-8", errors="replace") as f:
    error = f.read().strip()
print(f"===== {ts} {label} ERROR =====")
print(error)
print()
PY
  fi

  rm -f "${tmp_json}" "${tmp_err}"
}

status_is_cleared() {
  local status_json="$1"
  python3 - "${status_json}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

root = data.get("osd_hp_status", data)
summary = root.get("summary", {})
missing = root.get("missing_osds", [])
osds = summary.get("osds", {})
samples = summary.get("samples", {})
heat_state = summary.get("heat_state", {})
confusion = summary.get("confusion_matrix", {})
training = summary.get("training", {})
latency = summary.get("latency", {}).get("hp_predict_latency", {})
read_ops = summary.get("read_ops", {})
write_ops = summary.get("write_ops", {})

up = int(osds.get("up_osds", 0) or 0)
reporting = int(osds.get("reporting_osds", 0) or 0)
if missing or up == 0 or reporting != up:
    sys.exit(1)

checks = [
    samples.get("hp_io_count", 0),
    samples.get("hp_labeled_io_total", 0),
    samples.get("hp_pending_io_count", 0),
    heat_state.get("hp_heat_state_count", 0),
    heat_state.get("hp_lru_count", 0),
    confusion.get("hp_true_positive_count", 0),
    confusion.get("hp_false_positive_count", 0),
    confusion.get("hp_true_negative_count", 0),
    confusion.get("hp_false_negative_count", 0),
    training.get("hp_train_queue_length", 0),
    training.get("hp_train_drop_count", 0),
    training.get("hp_swap_count", 0),
    latency.get("avgcount", 0),
    latency.get("sum_ns", 0),
    read_ops.get("hp_op_read_count", 0),
    read_ops.get("hp_op_sync_read_count", 0),
    read_ops.get("hp_op_sparse_read_count", 0),
    write_ops.get("hp_op_write_count", 0),
    write_ops.get("hp_op_writefull_count", 0),
    write_ops.get("hp_op_writesame_count", 0),
]

if all(int(v or 0) == 0 for v in checks):
    sys.exit(0)
sys.exit(1)
PY
}

reset_and_wait_clear() {
  local label="$1"
  local status_file="$2"
  local deadline tmp_json tmp_err
  tmp_json="$(mktemp)"
  tmp_err="$(mktemp)"

  log "Reset Heat Predictor before ${label}"
  sudo -n ceph osd hp reset -f json-pretty >>"${status_file}.reset.log" 2>&1

  deadline=$((SECONDS + RESET_TIMEOUT))
  while (( SECONDS < deadline )); do
    if sudo -n ceph osd hp status -f json >"${tmp_json}" 2>"${tmp_err}"; then
      append_status_snapshot "${label}:after_reset_poll" "${status_file}"
      if status_is_cleared "${tmp_json}"; then
        rm -f "${tmp_json}" "${tmp_err}"
        log "Reset verified for ${label}"
        return 0
      fi
    else
      cat "${tmp_err}" >>"${status_file}.reset.log"
    fi
    sleep "${RESET_POLL_INTERVAL}"
  done

  rm -f "${tmp_json}" "${tmp_err}"
  log "Reset did not become clear within ${RESET_TIMEOUT}s for ${label}"
  return 1
}

collect_status_until_done() {
  local label="$1"
  local status_file="$2"
  local pid="$3"

  while kill -0 "${pid}" 2>/dev/null; do
    append_status_snapshot "${label}:running" "${status_file}"
    sleep "${STATUS_INTERVAL}"
  done
}

run_foreground() {
  mkdir -p "${OUT_ROOT}" "${LOG_ROOT}" "${STATUS_ROOT}"

  mapfile -t configs < <(collect_configs "$@")
  if [[ "${#configs[@]}" -eq 0 ]]; then
    echo "no IO config found in ${CONFIG_DIR}" >&2
    exit 1
  fi

  mapfile -t anchor_dirs < <(collect_anchor_dirs "${configs[@]}" | sort -u)
  for dir in "${anchor_dirs[@]}"; do
    mkdir -p "${dir}" 2>/dev/null || {
      echo "unable to create anchor directory: ${dir}" >&2
      echo "check that CephFS is mounted read-write." >&2
      exit 1
    }
  done

  sudo_keepalive_pid=""
  if sudo -n -v 2>/dev/null; then
    (
      while sudo -n -v 2>/dev/null; do
        sleep 60
      done
    ) &
    sudo_keepalive_pid="$!"
  fi

  cleanup() {
    if [[ -n "${sudo_keepalive_pid}" ]]; then
      kill "${sudo_keepalive_pid}" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT

  log "Run all single-node skew IO tests"
  log "Run ID:          ${RUN_ID}"
  log "Config dir:      ${CONFIG_DIR}"
  log "Vdbench:         ${VDBENCH}"
  log "Output:          ${OUT_ROOT}"
  log "Logs:            ${LOG_ROOT}"
  log "HP status:       ${STATUS_ROOT}"
  log "Status interval: ${STATUS_INTERVAL}s"
  log "Reset timeout:   ${RESET_TIMEOUT}s"
  log "Configs:"
  printf '  %s\n' "${configs[@]}"

  for cfg in "${configs[@]}"; do
    name="$(basename "${cfg}" .txt)"
    rel="${cfg#${SCRIPT_DIR}/}"
    suite="${rel%%/*}"
    out_dir="${OUT_ROOT}/${suite}/${name}"
    log_dir="${LOG_ROOT}/${suite}"
    log_file="${log_dir}/${name}.vdbench.log"
    status_file="${STATUS_ROOT}/${suite}/${name}.hp_status.log"

    mkdir -p "${out_dir}" "${log_dir}" "$(dirname "${status_file}")"

    reset_and_wait_clear "${suite}/${name}" "${status_file}"
    append_status_snapshot "${suite}/${name}:before_test" "${status_file}"

    log "Start test ${suite}/${name}"
    log "Config: ${cfg}"
    log "Log:    ${log_file}"
    "${VDBENCH}" ${VD_ARGS} -f"${cfg}" -o"${out_dir}" >"${log_file}" 2>&1 &
    test_pid="$!"

    collect_status_until_done "${suite}/${name}" "${status_file}" "${test_pid}" &
    collector_pid="$!"

    if wait "${test_pid}"; then
      test_rc=0
    else
      test_rc="$?"
    fi
    wait "${collector_pid}" 2>/dev/null || true
    append_status_snapshot "${suite}/${name}:after_test" "${status_file}"

    if [[ "${test_rc}" -ne 0 ]]; then
      log "Test failed: ${suite}/${name}, rc=${test_rc}"
      exit "${test_rc}"
    fi
    log "Finished test ${suite}/${name}"
  done

  log "All single-node standard IO tests finished"
}

start_background() {
  mkdir -p "${BACKGROUND_ROOT}"
  local bg_log pid_file
  bg_log="${BACKGROUND_ROOT}/${RUN_ID}.standard_io.nohup.log"
  pid_file="${BACKGROUND_ROOT}/${RUN_ID}.standard_io.pid"

  if ! sudo -n ceph osd hp status -f json >/dev/null 2>&1; then
    sudo -v
  fi

  nohup setsid env \
    RUN_ID="${RUN_ID}" \
    CONFIG_DIR="${CONFIG_DIR}" \
    VDBENCH="${VDBENCH}" \
    OUT_ROOT="${OUT_ROOT}" \
    LOG_ROOT="${LOG_ROOT}" \
    STATUS_ROOT="${STATUS_ROOT}" \
    BACKGROUND_ROOT="${BACKGROUND_ROOT}" \
    VD_ARGS="${VD_ARGS}" \
    STATUS_INTERVAL="${STATUS_INTERVAL}" \
    RESET_TIMEOUT="${RESET_TIMEOUT}" \
    RESET_POLL_INTERVAL="${RESET_POLL_INTERVAL}" \
    "$0" run "$@" >"${bg_log}" 2>&1 &

  echo "$!" >"${pid_file}"
  echo "Started single-node skew IO background run"
  echo "Run ID: ${RUN_ID}"
  echo "PID:    $(cat "${pid_file}")"
  echo "Log:    ${bg_log}"
  echo "Status: ${STATUS_ROOT}"
}

stop_background() {
  mkdir -p "${BACKGROUND_ROOT}"
  local pid_file pid stopped=0

  shopt -s nullglob
  for pid_file in "${BACKGROUND_ROOT}"/*.standard_io.pid; do
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      echo "Stopping background skew IO run: pid=${pid}, file=${pid_file}"
      kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
      stopped=1
    fi
    rm -f "${pid_file}"
  done
  shopt -u nullglob

  pkill -TERM -f "${SCRIPT_DIR}/后台运行标准IO测试.sh run" 2>/dev/null || true
  pkill -TERM -f "${VDBENCH}.*single_node_skew_io" 2>/dev/null || true
  pkill -TERM -f "${VDBENCH}.*single_node_standard_io" 2>/dev/null || true
  pkill -TERM -f "SlaveJvm" 2>/dev/null || true
  sleep 2
  pkill -KILL -f "${SCRIPT_DIR}/后台运行标准IO测试.sh run" 2>/dev/null || true
  pkill -KILL -f "${VDBENCH}.*single_node_skew_io" 2>/dev/null || true
  pkill -KILL -f "${VDBENCH}.*single_node_standard_io" 2>/dev/null || true
  pkill -KILL -f "SlaveJvm" 2>/dev/null || true

  if [[ "${stopped}" -eq 0 ]]; then
    echo "No pid file with live background skew IO run was found."
  fi
  echo "Stop request sent. Check with:"
  echo "  ps -ef | grep -E '后台运行标准IO测试|vdbench|SlaveJvm' | grep -v grep"
}

cmd="${1:-run}"
case "${cmd}" in
  run)
    shift || true
    run_foreground "$@"
    ;;
  background|bg)
    shift || true
    start_background "$@"
    ;;
  stop)
    shift || true
    stop_background
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: ${cmd}" >&2
    usage >&2
    exit 2
    ;;
esac

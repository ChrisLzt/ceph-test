#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_SCRIPT="${DATA_SCRIPT:-${SCRIPT_DIR}/造数据.sh}"
DATA_ROOT="${DATA_ROOT:-${SCRIPT_DIR}/冷热IO}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_single_node_data}"
VDBENCH="${VDBENCH:-/home/chris/PDSL/vdbench/vdbench}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/out/${RUN_ID}}"
LOG_ROOT="${LOG_ROOT:-${SCRIPT_DIR}/logs/${RUN_ID}}"
BACKGROUND_ROOT="${BACKGROUND_ROOT:-${SCRIPT_DIR}/logs/background}"
VD_ARGS="${VD_ARGS:-}"
CAPACITY_LIMIT_PERCENT="${CAPACITY_LIMIT_PERCENT:-85}"

usage() {
  cat <<EOF
Usage:
  $0 run          前台运行造数据脚本
  $0 background   后台调用 run
  $0 bg           background 的简写
  $0 stop         停止所有后台造数据任务
  $0 status       查看后台造数据任务

Environment:
  DATA_SCRIPT=${DATA_SCRIPT}
  DATA_ROOT=${DATA_ROOT}
  VDBENCH=${VDBENCH}
  CAPACITY_LIMIT_PERCENT=${CAPACITY_LIMIT_PERCENT}
EOF
}

log() {
  echo "[$(date '+%F %T')] $*"
}

run_foreground() {
  if [[ ! -x "${DATA_SCRIPT}" ]]; then
    echo "data script is not executable: ${DATA_SCRIPT}" >&2
    exit 1
  fi

  log "Run single-node data preparation"
  log "Run ID:         ${RUN_ID}"
  log "Data script:    ${DATA_SCRIPT}"
  log "Data root:      ${DATA_ROOT}"
  log "Vdbench:        ${VDBENCH}"
  log "Output:         ${OUT_ROOT}"
  log "Logs:           ${LOG_ROOT}"
  log "Capacity limit: ${CAPACITY_LIMIT_PERCENT}%"

  exec env \
    RUN_ID="${RUN_ID}" \
    DATA_ROOT="${DATA_ROOT}" \
    VDBENCH="${VDBENCH}" \
    OUT_ROOT="${OUT_ROOT}" \
    LOG_ROOT="${LOG_ROOT}" \
    VD_ARGS="${VD_ARGS}" \
    CAPACITY_LIMIT_PERCENT="${CAPACITY_LIMIT_PERCENT}" \
    "${DATA_SCRIPT}"
}

find_live_background_run() {
  local pid_file pid

  shopt -s nullglob
  for pid_file in "${BACKGROUND_ROOT}"/*.prepare_data.pid; do
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      echo "${pid_file}:${pid}"
      shopt -u nullglob
      return 0
    fi
    rm -f "${pid_file}"
  done
  shopt -u nullglob
  return 1
}

start_background() {
  mkdir -p "${BACKGROUND_ROOT}"

  local live bg_log pid_file pid
  if live="$(find_live_background_run)"; then
    echo "A background data preparation task is already running: ${live}" >&2
    exit 1
  fi

  bg_log="${BACKGROUND_ROOT}/${RUN_ID}.prepare_data.nohup.log"
  pid_file="${BACKGROUND_ROOT}/${RUN_ID}.prepare_data.pid"

  nohup setsid env \
    RUN_ID="${RUN_ID}" \
    DATA_SCRIPT="${DATA_SCRIPT}" \
    DATA_ROOT="${DATA_ROOT}" \
    VDBENCH="${VDBENCH}" \
    OUT_ROOT="${OUT_ROOT}" \
    LOG_ROOT="${LOG_ROOT}" \
    BACKGROUND_ROOT="${BACKGROUND_ROOT}" \
    VD_ARGS="${VD_ARGS}" \
    CAPACITY_LIMIT_PERCENT="${CAPACITY_LIMIT_PERCENT}" \
    "$0" run >"${bg_log}" 2>&1 < /dev/null &

  pid="$!"
  echo "${pid}" >"${pid_file}"

  echo "Started single-node data preparation"
  echo "Run ID: ${RUN_ID}"
  echo "PID:    ${pid}"
  echo "Log:    ${bg_log}"
  echo "Detail: ${LOG_ROOT}"
}

stop_background() {
  mkdir -p "${BACKGROUND_ROOT}"

  local pid_file pid stopped=0
  shopt -s nullglob
  for pid_file in "${BACKGROUND_ROOT}"/*.prepare_data.pid; do
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      echo "Stopping background data preparation: pid=${pid}, file=${pid_file}"
      kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
      stopped=1

      for _ in {1..10}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
          break
        fi
        sleep 1
      done

      if kill -0 "${pid}" 2>/dev/null; then
        kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null || true
      fi
    fi
    rm -f "${pid_file}"
  done
  shopt -u nullglob

  if [[ "${stopped}" -eq 0 ]]; then
    echo "No live background data preparation task was found."
  else
    echo "Background data preparation stopped."
  fi
}

show_status() {
  mkdir -p "${BACKGROUND_ROOT}"

  local pid_file pid found=0
  shopt -s nullglob
  for pid_file in "${BACKGROUND_ROOT}"/*.prepare_data.pid; do
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      echo "RUNNING pid=${pid} pid_file=${pid_file}"
      found=1
    else
      echo "STALE pid=${pid:-unknown} pid_file=${pid_file}"
    fi
  done
  shopt -u nullglob

  if [[ "${found}" -eq 0 ]]; then
    echo "No live background data preparation task."
  fi
}

cmd="${1:-run}"
case "${cmd}" in
  run)
    shift || true
    run_foreground
    ;;
  background|bg)
    shift || true
    start_background
    ;;
  stop)
    shift || true
    stop_background
    ;;
  status)
    shift || true
    show_status
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

#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ceph_repo=${CEPH_REPO:-/home/chris/ceph-heat-predictor}
export VDBENCH_MAIN_XMX=${VDBENCH_MAIN_XMX:-2048m}
profile=
repetitions=1
repetition_start=1
dry_run=0
output_root=
status_interval=30
declare -a selected_workloads=()
declare -a default_workloads=(
  bigdata_mapreduce_vdbench_v1
  graph_graphchi_vdbench_v1
  hpc_wrf_vdbench_v1
  ai_training_checkpoint_vdbench_v1
  ai_inference_kvcache_vdbench_v1
)

usage() {
  cat <<'EOF'
Usage: run_hp_matrix.sh --profile H0P0|H0P1|H1P0|H1P1|D0|D1|D2 [options]

Options:
  --workload NAME      Run one workload; may be repeated.
  --repetitions N      Repetitions per workload (default: 1).
  --repetition-start N Start repetition numbering at N (default: 1).
  --output-root DIR    Report root. Default uses a timestamped reports path.
  --status-interval N  MGR hp status sampling interval in seconds (default: 30).
  --dry-run            Print the expanded matrix without touching Ceph.
EOF
}

while (($#)); do
  case "$1" in
    --profile)
      profile=${2:?missing profile value}
      shift 2
      ;;
    --workload)
      selected_workloads+=("${2:?missing workload value}")
      shift 2
      ;;
    --repetitions)
      repetitions=${2:?missing repetitions value}
      shift 2
      ;;
    --repetition-start)
      repetition_start=${2:?missing repetition start value}
      shift 2
      ;;
    --output-root)
      output_root=${2:?missing output root}
      shift 2
      ;;
    --status-interval)
      status_interval=${2:?missing status interval}
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$profile" in
  H0P0) prediction_calibration=0; prediction_range=0; otsu_profile=1; otsu_data_source=0 ;;
  H0P1) prediction_calibration=1; prediction_range=0; otsu_profile=1; otsu_data_source=0 ;;
  H1P0) prediction_calibration=0; prediction_range=0; otsu_profile=2; otsu_data_source=0 ;;
  H1P1) prediction_calibration=1; prediction_range=0; otsu_profile=2; otsu_data_source=0 ;;
  C0) prediction_calibration=1; prediction_range=0; otsu_profile=2; otsu_data_source=0 ;;
  CW) prediction_calibration=1; prediction_range=1; otsu_profile=2; otsu_data_source=0 ;;
  O0) prediction_calibration=1; prediction_range=0; otsu_profile=0; otsu_data_source=0 ;;
  O1) prediction_calibration=1; prediction_range=0; otsu_profile=1; otsu_data_source=0 ;;
  O2) prediction_calibration=1; prediction_range=0; otsu_profile=2; otsu_data_source=0 ;;
  D0) prediction_calibration=0; prediction_range=0; otsu_profile=1; otsu_data_source=0 ;;
  D1) prediction_calibration=0; prediction_range=0; otsu_profile=1; otsu_data_source=1 ;;
  D2) prediction_calibration=0; prediction_range=0; otsu_profile=1; otsu_data_source=2 ;;
  *)
    echo "Invalid profile: ${profile:-<empty>}" >&2
    exit 2
    ;;
esac

if ! [[ "$repetitions" =~ ^[1-9][0-9]*$ ]]; then
  echo "Repetitions must be a positive integer" >&2
  exit 2
fi
if ! [[ "$repetition_start" =~ ^[1-9][0-9]*$ ]]; then
  echo "Repetition start must be a positive integer" >&2
  exit 2
fi
if ! [[ "$status_interval" =~ ^[1-9][0-9]*$ ]]; then
  echo "Status interval must be a positive integer" >&2
  exit 2
fi

if ((${#selected_workloads[@]} == 0)); then
  selected_workloads=("${default_workloads[@]}")
fi
for workload in "${selected_workloads[@]}"; do
  if [[ ! -x "$root/$workload/run_test.sh" ||
        ! -x "$root/$workload/validate_model.sh" ]]; then
    echo "Invalid workload: $workload" >&2
    exit 2
  fi
done

if ((dry_run)); then
  for ((rep = repetition_start; rep < repetition_start + repetitions; ++rep)); do
    for workload in "${selected_workloads[@]}"; do
      printf 'profile=%s prediction_calibration=%s prediction_range=%s otsu=%s otsu_source=%s repetition=%s workload=%s\n' \
        "$profile" "$prediction_calibration" "$prediction_range" \
        "$otsu_profile" "$otsu_data_source" "$rep" "$workload"
    done
  done
  exit 0
fi

cache="$ceph_repo/build/CMakeCache.txt"
configured_calibration=$(sed -n 's/^HP_ENABLE_PREDICTION_CALIBRATION:STRING=//p' "$cache")
configured_prediction=$(sed -n 's/^HP_PREDICTION_RANGE_PROFILE:STRING=//p' "$cache")
configured_otsu=$(sed -n 's/^HP_OTSU_PROFILE:STRING=//p' "$cache")
configured_otsu_source=$(sed -n 's/^HP_OTSU_DATA_SOURCE:STRING=//p' "$cache")
if [[ "$configured_calibration" != "$prediction_calibration" ||
      "$configured_prediction" != "$prediction_range" ||
      "$configured_otsu" != "$otsu_profile" ||
      "$configured_otsu_source" != "$otsu_data_source" ]]; then
  echo "Configured profile mismatch: expected calibration=$prediction_calibration prediction=$prediction_range otsu=$otsu_profile source=$otsu_data_source, got calibration=${configured_calibration:-missing} prediction=${configured_prediction:-missing} otsu=${configured_otsu:-missing} source=${configured_otsu_source:-missing}" >&2
  exit 1
fi

if [[ -z "$output_root" ]]; then
  output_root="$root/hp_runs/reports/$(date +%Y%m%d_%H%M%S)_hp_matrix"
fi
mkdir -p "$output_root"
output_root=$(cd -- "$output_root" && pwd)
mkdir -p "$output_root/$profile"
matrix_tsv="$output_root/results.tsv"
status_index="$output_root/hp_status_30s_index.tsv"
sampler_pid=

if [[ ! -s "$status_index" ]]; then
  printf 'timestamp\tprofile\tworkload\trepetition\tstatus\tpath\n' >"$status_index"
fi

stop_status_sampler() {
  if [[ -n "${sampler_pid:-}" ]]; then
    kill "$sampler_pid" 2>/dev/null || true
    wait "$sampler_pid" 2>/dev/null || true
    sampler_pid=
  fi
}

cleanup() {
  stop_status_sampler
}

trap cleanup EXIT INT TERM

start_status_sampler() {
  local run_dir=$1 workload_pid=$2 workload=$3 repetition=$4
  local sample_dir="$run_dir/hp_status_30s"
  mkdir -p "$sample_dir"

  (
    local sequence=0 elapsed timestamp sample_file tmp_file relative_path
    while kill -0 "$workload_pid" 2>/dev/null; do
      sequence=$((sequence + 1))
      timestamp=$(date '+%Y%m%d_%H%M%S')
      sample_file=$(printf '%s/%04d_%s.json' "$sample_dir" "$sequence" "$timestamp")
      tmp_file="${sample_file}.tmp"
      relative_path=${sample_file#"$output_root"/}
      if sudo ceph osd hp status -f json-pretty >"$tmp_file"; then
        mv "$tmp_file" "$sample_file"
        printf '%s\t%s\t%s\t%s\tok\t%s\n' \
          "$timestamp" "$profile" "$workload" "$repetition" "$relative_path" \
          >>"$status_index"
      else
        rm -f "$tmp_file"
        printf '%s\t%s\t%s\t%s\terror\t%s\n' \
          "$timestamp" "$profile" "$workload" "$repetition" "$relative_path" \
          >>"$status_index"
      fi

      elapsed=0
      while ((elapsed < status_interval)) && kill -0 "$workload_pid" 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
      done
    done
  ) &
  sampler_pid=$!
}

cluster_is_clean() {
  sudo ceph -s -f json | python3 -c '
import json, sys
s = json.load(sys.stdin)
pg = s.get("pgmap", {})
states = pg.get("pgs_by_state", [])
ok = (pg.get("num_pgs", 0) > 0 and len(states) == 1 and
      states[0].get("state_name") == "active+clean" and
      states[0].get("count") == pg.get("num_pgs") and
      s.get("osdmap", {}).get("num_up_osds") == s.get("osdmap", {}).get("num_osds") and
      s.get("osdmap", {}).get("num_in_osds") == s.get("osdmap", {}).get("num_osds"))
raise SystemExit(0 if ok else 1)
'
}

wait_for_heat_predictor_reset() {
  local -a osds=()
  mapfile -t osds < <(sudo ceph osd ls)
  if ((${#osds[@]} == 0)); then
    return 1
  fi

  local deadline=$((SECONDS + 120))
  while ((SECONDS < deadline)); do
    local all_reset=1 osd
    for osd in "${osds[@]}"; do
      if ! sudo ceph daemon "osd.$osd" object_hp status | python3 -c '
import json, sys
payload = json.load(sys.stdin)
s = payload.get("object_hp_status", payload)
reset = (
    s["enabled"]
    and s["hp_io_count"] == 0
    and s["hp_labeled_io_total"] == 0
    and s["hp_pending_io_count"] == 0
    and s["hp_awaiting_prediction_count"] == 0
    and s["hp_eval_drop_count"] == 0
    and s["hp_train_queue_length"] == 0
    and s["hp_train_drop_count"] == 0
    and s["hp_snapshot_publish_count"] == 0
    and s["hp_predict_error_count"] == 0
)
raise SystemExit(0 if reset else 1)
'; then
        all_reset=0
        continue
      fi
      if ! sudo ceph daemon "osd.$osd" perf dump object_hp_status | python3 -c '
import json, sys
payload = json.load(sys.stdin)
s = payload.get("object_hp_status", payload)
reset = (
    s["hp_heat_state_count"] == 0
    and s["hp_lru_count"] == 0
    and s["hp_otsu_histogram_bin_count"] == 0
    and s["hp_otsu_histogram_vote_count"] == 0
)
raise SystemExit(0 if reset else 1)
'; then
        all_reset=0
      fi
    done
    if ((all_reset)); then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_mgr_heat_predictor_reset() {
  local deadline=$((SECONDS + 120))
  while ((SECONDS < deadline)); do
    if sudo ceph osd hp status -f json 2>/dev/null |
        python3 "$root/tools/check_mgr_hp_reset.py"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_heat_predictor_idle() {
  local -a osds=()
  mapfile -t osds < <(sudo ceph osd ls)
  if ((${#osds[@]} == 0)); then
    return 1
  fi

  local deadline=$((SECONDS + 600))
  while ((SECONDS < deadline)); do
    local all_idle=1
    local osd
    for osd in "${osds[@]}"; do
      if ! sudo ceph daemon "osd.$osd" object_hp status | python3 -c '
import json, sys
status = json.load(sys.stdin)
idle = (
    status["hp_pending_io_count"] == 0
    and status["hp_awaiting_prediction_count"] == 0
    and status["hp_train_queue_length"] == 0
)
raise SystemExit(0 if idle else 1)
'; then
        all_idle=0
      fi
    done
    if ((all_idle)) && sudo ceph osd hp status -f json | python3 -c '
import json, sys
summary = json.load(sys.stdin)["summary"]
osds = summary["osds"]
samples = summary["samples"]
training = summary["training"]
complete = (
    osds["reporting_osds"] == osds["up_osds"]
    and samples["hp_io_count"] > 0
    and samples["hp_pending_io_count"] == 0
    and samples["hp_awaiting_prediction_count"] == 0
    and training["hp_train_queue_length"] == 0
    and samples["hp_labeled_io_total"] + samples["hp_eval_drop_count"]
        == samples["hp_io_count"]
)
raise SystemExit(0 if complete else 1)
'; then
      return 0
    fi
    sleep 5
  done
  return 1
}

write_metadata() {
  local path=$1 workload=$2 repetition=$3 started=$4 ended=$5 config_hash=$6
  local ceph_commit workload_commit hp_hash kernel ceph_version cluster_status osd_metrics
  ceph_commit=$(git -C "$ceph_repo" rev-parse HEAD)
  workload_commit=$(git -C "$root/.." rev-parse HEAD)
  hp_hash=$(sha256sum "$ceph_repo/src/heatpredictor/hp_config.h" | awk '{print $1}')
  kernel=$(uname -r)
  ceph_version=$(ceph --version)
  cluster_status=$(sudo ceph -s -f json)
  osd_metrics=$(ps -C ceph-osd -o pid=,rss=,pcpu=,args= --no-headers)
  python3 - "$path" "$profile" "$prediction_calibration" \
    "$prediction_range" "$otsu_profile" "$otsu_data_source" \
    "$workload" "$repetition" "$started" "$ended" "$ceph_commit" \
    "$workload_commit" "$hp_hash" "$config_hash" "$kernel" "$ceph_version" \
    "$cluster_status" "$osd_metrics" <<'PY'
import json, sys
(
    path, profile, prediction_calibration, prediction_range, otsu_profile,
    otsu_data_source,
    workload, repetition,
    started, ended, ceph_commit, workload_commit, hp_hash, config_hash,
    kernel, ceph_version, cluster_status, osd_metrics,
) = sys.argv[1:]
processes = []
for line in osd_metrics.splitlines():
    fields = line.split(None, 3)
    if len(fields) == 4:
        processes.append({
            "pid": int(fields[0]),
            "rss_kib": int(fields[1]),
            "cpu_percent": float(fields[2]),
            "command": fields[3],
        })
with open(path, "w", encoding="utf-8") as out:
    json.dump({
        "profile": profile,
        "prediction_calibration_enabled": int(prediction_calibration),
        "prediction_range_profile": int(prediction_range),
        "otsu_profile": int(otsu_profile),
        "otsu_data_source": int(otsu_data_source),
        "workload": workload,
        "repetition": int(repetition),
        "started_at": started,
        "ended_at": ended,
        "ceph_commit": ceph_commit,
        "workload_commit": workload_commit,
        "hp_config_sha256": hp_hash,
        "workload_config_sha256": config_hash,
        "kernel": kernel,
        "ceph_version": ceph_version,
        "precheck": "active+clean",
        "cluster_status_after": json.loads(cluster_status),
        "osd_processes_after": processes,
    }, out, ensure_ascii=False, indent=2)
    out.write("\n")
PY
}

for ((rep = repetition_start; rep < repetition_start + repetitions; ++rep)); do
  for workload in "${selected_workloads[@]}"; do
    run_dir="$output_root/$profile/${workload}_r${rep}"
    mkdir -p "$run_dir"
    run_log="$run_dir/run.log"

    echo "[$(date '+%F %T')] START profile=$profile workload=$workload repetition=$rep" |
      tee -a "$run_log"
    if ! cluster_is_clean; then
      echo "Cluster is not active+clean" | tee -a "$run_log" >&2
      exit 1
    fi

    "$root/$workload/validate_model.sh" 2>&1 | tee -a "$run_log"
    config_hash=$(find "$root/$workload/configs" "$root/$workload/rendered" \
      -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')

    sudo ceph osd hp reset 2>&1 | tee -a "$run_log"
    if ! wait_for_heat_predictor_reset; then
      echo "Timed out waiting for Heat Predictor reset" | tee -a "$run_log" >&2
      exit 1
    fi
    echo "Waiting for MGR to observe the Heat Predictor reset" | tee -a "$run_log"
    if ! wait_for_mgr_heat_predictor_reset; then
      echo "Timed out waiting for MGR Heat Predictor reset state" |
        tee -a "$run_log" >&2
      exit 1
    fi
    started=$(date --iso-8601=seconds)
    (
      set -o pipefail
      OUTPUT_DIR="$run_dir/workload_output" \
        "$root/$workload/run_test.sh" 2>&1 | tee -a "$run_log"
    ) &
    workload_pid=$!
    start_status_sampler "$run_dir" "$workload_pid" "$workload" "$rep"
    set +e
    wait "$workload_pid"
    workload_rc=$?
    set -e
    stop_status_sampler
    if ((workload_rc != 0)); then
      echo "Workload failed with exit code $workload_rc" | tee -a "$run_log" >&2
      exit "$workload_rc"
    fi
    if ! wait_for_heat_predictor_idle; then
      echo "Timed out waiting for Heat Predictor to become idle" | tee -a "$run_log" >&2
      exit 1
    fi
    sudo ceph osd hp status -f json-pretty >"$run_dir/hp_status.json"
    ended=$(date --iso-8601=seconds)
    write_metadata "$run_dir/metadata.json" "$workload" "$rep" \
      "$started" "$ended" "$config_hash"

    if [[ ! -s "$matrix_tsv" ]]; then
      python3 "$root/tools/summarize_hp_matrix.py" --header >"$matrix_tsv"
    fi
    python3 "$root/tools/summarize_hp_matrix.py" \
      --status "$run_dir/hp_status.json" \
      --metadata "$run_dir/metadata.json" \
      --workload-output "$run_dir/workload_output" >>"$matrix_tsv"
    echo "[$(date '+%F %T')] DONE profile=$profile workload=$workload repetition=$rep" |
      tee -a "$run_log"
  done
done

echo "Results: $matrix_tsv"

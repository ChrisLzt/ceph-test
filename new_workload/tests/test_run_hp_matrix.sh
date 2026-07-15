#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runner="$root/run_hp_matrix.sh"

if ! grep -Fq 'output_root=$(cd -- "$output_root" && pwd)' "$runner"; then
  echo "FAIL: output root must be canonicalized before workload scripts change directory" >&2
  exit 1
fi

if "$runner" --profile invalid --dry-run >/dev/null 2>&1; then
  echo "FAIL: invalid profile should be rejected" >&2
  exit 1
fi
if "$runner" --profile D0 --dry-run --status-interval 0 >/dev/null 2>&1; then
  echo "FAIL: zero status interval should be rejected" >&2
  exit 1
fi
if ! grep -Fq 'hp_status_30s' "$runner" ||
   ! grep -Fq 'start_status_sampler' "$runner"; then
  echo "FAIL: runner should persist periodic MGR hp status samples" >&2
  exit 1
fi
if ! grep -Fq 'wait_for_heat_predictor_reset' "$runner"; then
  echo "FAIL: runner should wait for every OSD to finish reset" >&2
  exit 1
fi
mgr_reset_checker="$root/tools/check_mgr_hp_reset.py"
reset_status='{"summary":{"osds":{"up_osds":2,"reporting_osds":2,"enabled_osds":2,"disabled_osds":0,"missing_osds":[]},"samples":{"hp_io_count":0,"hp_labeled_io_total":0,"hp_pending_io_count":0,"hp_awaiting_prediction_count":0,"hp_eval_drop_count":0},"heat_state":{"hp_heat_state_count":0,"hp_lru_count":0,"hp_otsu_histogram_bin_count":0,"hp_otsu_histogram_vote_count":0},"confusion_matrix":{"hp_true_positive_count":0,"hp_false_positive_count":0,"hp_true_negative_count":0,"hp_false_negative_count":0},"prediction":{"hp_predict_error_count":0,"hp_predict_calibration_sample_count":0},"training":{"hp_train_queue_length":0,"hp_train_drop_count":0,"hp_snapshot_publish_count":0},"latency":{"hp_predict_latency":{"avgcount":0,"sum_ns":0,"avgtime_ns":0}},"read_ops":{"hp_op_read_count":0,"hp_op_sync_read_count":0,"hp_op_sparse_read_count":0},"write_ops":{"hp_op_write_count":0,"hp_op_writefull_count":0,"hp_op_writesame_count":0}}}'
stale_status=${reset_status/\"hp_io_count\":0/\"hp_io_count\":1}
if ! printf '%s\n' "$reset_status" | python3 "$mgr_reset_checker"; then
  echo "FAIL: fully reset MGR summary should be accepted" >&2
  exit 1
fi
if printf '%s\n' "$stale_status" | python3 "$mgr_reset_checker"; then
  echo "FAIL: stale MGR summary should be rejected" >&2
  exit 1
fi
if ! grep -Fq 'wait_for_mgr_heat_predictor_reset' "$runner"; then
  echo "FAIL: runner should wait for MGR to observe the reset" >&2
  exit 1
fi
python3 - "$runner" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
run = text[text.index("    sudo ceph osd hp reset 2>&1"):]
steps = (
    "wait_for_heat_predictor_reset",
    "wait_for_mgr_heat_predictor_reset",
    "started=$(date --iso-8601=seconds)",
    '"$root/$workload/run_test.sh"',
    "start_status_sampler",
)
positions = [run.index(step) for step in steps]
if positions != sorted(positions):
    raise SystemExit(
        "FAIL: OSD reset, MGR reset, workload, and MGR sampling are out of order"
    )
PY
if ! grep -Fq 'VDBENCH_MAIN_XMX=${VDBENCH_MAIN_XMX:-2048m}' "$runner"; then
  echo "FAIL: runner should provide enough heap for large formal workloads" >&2
  exit 1
fi

output=$($runner --profile O1 --dry-run)
expected=$'profile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=bigdata_mapreduce_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=graph_graphchi_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=hpc_wrf_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=ai_training_checkpoint_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=ai_inference_kvcache_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected O1 dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile CW --dry-run --workload graph_graphchi_vdbench_v1)
expected='profile=CW prediction_calibration=1 prediction_range=1 otsu=2 otsu_source=0 repetition=1 workload=graph_graphchi_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected CW dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile O1 --dry-run --workload graph_graphchi_vdbench_v1 \
  --repetition-start 2 --repetitions 2)
expected=$'profile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=2 workload=graph_graphchi_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 otsu_source=0 repetition=3 workload=graph_graphchi_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected continuation dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile H0P0 --dry-run --workload bigdata_mapreduce_vdbench_v1)
expected='profile=H0P0 prediction_calibration=0 prediction_range=0 otsu=1 otsu_source=0 repetition=1 workload=bigdata_mapreduce_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected H0P0 dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile H1P1 --dry-run --workload ai_inference_kvcache_vdbench_v1)
expected='profile=H1P1 prediction_calibration=1 prediction_range=0 otsu=2 otsu_source=0 repetition=1 workload=ai_inference_kvcache_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected H1P1 dry-run\n%s\n' "$output" >&2
  exit 1
fi

for profile_source in D0:0 D1:1 D2:2; do
  profile=${profile_source%%:*}
  source=${profile_source##*:}
  output=$($runner --profile "$profile" --dry-run --workload hpc_wrf_vdbench_v1)
  expected="profile=$profile prediction_calibration=0 prediction_range=0 otsu=1 otsu_source=$source repetition=1 workload=hpc_wrf_vdbench_v1"
  if [[ "$output" != "$expected" ]]; then
    printf 'FAIL: unexpected %s dry-run\n%s\n' "$profile" "$output" >&2
    exit 1
  fi
done

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/vdbench"
cat >"$tmpdir/status.json" <<'EOF'
{"summary":{"samples":{"hp_io_count":12,"hp_labeled_io_total":10,"hp_pending_io_count":2},"training":{"hp_train_drop_count":0,"hp_snapshot_publish_count":7},"confusion_matrix":{"hp_true_positive_count":3,"hp_false_positive_count":1,"hp_true_negative_count":5,"hp_false_negative_count":1},"prediction":{"hp_hot_predict_threshold_avg":0.5,"hp_hot_predict_threshold_target_avg":0.55},"heat_state":{"hp_otsu_histogram_vote_count":42,"hp_hot_threshold_avg":10.0,"hp_otsu_candidate_threshold_avg":11.0,"hp_otsu_separation_percent_avg":80.0,"hp_otsu_confidence_percent_avg":70.0},"latency":{"hp_predict_latency":{"avgtime_ns":1234}}}}
EOF
cat >"$tmpdir/metadata.json" <<'EOF'
{"profile":"D1","otsu_data_source":1,"workload":"fixture","repetition":1}
EOF
cat >"$tmpdir/vdbench/summary.html" <<'EOF'
12:00:00.000 avg_2-10 1000.0 1.0 2.0 1.0 100.0 1000.0 1.0 0.0 0.0 1000.0 0.0 1000.0
12:00:10.000 avg_2-10 900.0 1.0 2.0 1.0 100.0 900.0 1.0 0.0 0.0 900.0 0.0 900.0
EOF
summary=$(
  python3 "$root/tools/summarize_hp_matrix.py" \
    --status "$tmpdir/status.json" \
    --metadata "$tmpdir/metadata.json" \
    --workload-output "$tmpdir/vdbench"
)
if [[ "$summary" != *$'D1\t1\tfixture'* ||
      "$summary" != *$'\t10.000000\t11.000000\t80.000000\t70.000000\t42\t0.500000\t0.550000\t7\t1234\t950.000000\t950.000000' ]]; then
  printf 'FAIL: unexpected summary fields\n%s\n' "$summary" >&2
  exit 1
fi

echo "PASS: run_hp_matrix dry-run contract"

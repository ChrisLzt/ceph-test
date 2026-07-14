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

output=$($runner --profile O1 --dry-run)
expected=$'profile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=1 workload=bigdata_mapreduce_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=1 workload=graph_graphchi_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=1 workload=ai_training_checkpoint_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=1 workload=ai_inference_kvcache_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected O1 dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile CW --dry-run --workload graph_graphchi_vdbench_v1)
expected='profile=CW prediction_calibration=1 prediction_range=1 otsu=2 repetition=1 workload=graph_graphchi_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected CW dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile O1 --dry-run --workload graph_graphchi_vdbench_v1 \
  --repetition-start 2 --repetitions 2)
expected=$'profile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=2 workload=graph_graphchi_vdbench_v1\nprofile=O1 prediction_calibration=1 prediction_range=0 otsu=1 repetition=3 workload=graph_graphchi_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected continuation dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile H0P0 --dry-run --workload bigdata_mapreduce_vdbench_v1)
expected='profile=H0P0 prediction_calibration=0 prediction_range=0 otsu=1 repetition=1 workload=bigdata_mapreduce_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected H0P0 dry-run\n%s\n' "$output" >&2
  exit 1
fi

output=$($runner --profile H1P1 --dry-run --workload ai_inference_kvcache_vdbench_v1)
expected='profile=H1P1 prediction_calibration=1 prediction_range=0 otsu=2 repetition=1 workload=ai_inference_kvcache_vdbench_v1'
if [[ "$output" != "$expected" ]]; then
  printf 'FAIL: unexpected H1P1 dry-run\n%s\n' "$output" >&2
  exit 1
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/vdbench"
cat >"$tmpdir/status.json" <<'EOF'
{"summary":{"samples":{"hp_io_count":12,"hp_labeled_io_total":10,"hp_pending_io_count":2},"training":{"hp_train_drop_count":0,"hp_snapshot_publish_count":7},"confusion_matrix":{"hp_true_positive_count":3,"hp_false_positive_count":1,"hp_true_negative_count":5,"hp_false_negative_count":1},"prediction":{"hp_hot_predict_threshold_avg":0.5,"hp_hot_predict_threshold_target_avg":0.55},"heat_state":{"hp_hot_threshold_avg":10.0,"hp_otsu_candidate_threshold_avg":11.0,"hp_otsu_separation_percent_avg":80.0,"hp_otsu_confidence_percent_avg":70.0},"latency":{"hp_predict_latency":{"avgtime_ns":1234}}}}
EOF
cat >"$tmpdir/metadata.json" <<'EOF'
{"profile":"O2","workload":"fixture","repetition":1}
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
if [[ "$summary" != *$'\t10.000000\t11.000000\t80.000000\t70.000000\t0.500000\t0.550000\t7\t1234\t950.000000\t950.000000' ]]; then
  printf 'FAIL: unexpected summary fields\n%s\n' "$summary" >&2
  exit 1
fi

echo "PASS: run_hp_matrix dry-run contract"

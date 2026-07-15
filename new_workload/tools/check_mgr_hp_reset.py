#!/usr/bin/env python3
import json
import sys


ZERO_FIELDS = {
    "samples": (
        "hp_io_count",
        "hp_labeled_io_total",
        "hp_pending_io_count",
        "hp_awaiting_prediction_count",
        "hp_eval_drop_count",
    ),
    "heat_state": (
        "hp_heat_state_count",
        "hp_lru_count",
        "hp_otsu_histogram_bin_count",
        "hp_otsu_histogram_vote_count",
    ),
    "confusion_matrix": (
        "hp_true_positive_count",
        "hp_false_positive_count",
        "hp_true_negative_count",
        "hp_false_negative_count",
    ),
    "prediction": (
        "hp_predict_error_count",
        "hp_predict_calibration_sample_count",
    ),
    "training": (
        "hp_train_queue_length",
        "hp_train_drop_count",
        "hp_snapshot_publish_count",
    ),
    "read_ops": (
        "hp_op_read_count",
        "hp_op_sync_read_count",
        "hp_op_sparse_read_count",
    ),
    "write_ops": (
        "hp_op_write_count",
        "hp_op_writefull_count",
        "hp_op_writesame_count",
    ),
}


def is_reset(payload):
    try:
        summary = payload["summary"]
        osds = summary["osds"]
        up_osds = osds["up_osds"]
        if not (
            up_osds > 0
            and osds["reporting_osds"] == up_osds
            and osds["enabled_osds"] == up_osds
            and osds["disabled_osds"] == 0
            and not osds["missing_osds"]
        ):
            return False

        for section, fields in ZERO_FIELDS.items():
            if any(summary[section][field] != 0 for field in fields):
                return False

        latency = summary["latency"]["hp_predict_latency"]
        return all(latency[field] == 0 for field in (
            "avgcount", "sum_ns", "avgtime_ns"
        ))
    except (KeyError, TypeError):
        return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 1
    return 0 if is_reset(payload) else 1


if __name__ == "__main__":
    raise SystemExit(main())

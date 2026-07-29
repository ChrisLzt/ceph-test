#!/usr/bin/env python3
import argparse
import json
import re
import statistics
from pathlib import Path


COLUMNS = [
    "profile", "otsu_data_source", "workload", "repetition", "io", "labeled", "pending",
    "drop", "tp", "fp", "tn", "fn", "accuracy", "balanced_accuracy",
    "precision", "recall", "pred_hot_percent", "actual_hot_percent",
    "majority_baseline", "accuracy_excess", "hot_threshold",
    "otsu_candidate_threshold", "otsu_separation_percent",
    "otsu_confidence_percent", "otsu_vote_count", "predict_threshold",
    "predict_threshold_target", "snapshot_publish_count",
    "predict_latency_avg_ns", "vdbench_rate", "vdbench_mb_sec",
]


def ratio(numerator: int, denominator: int) -> float:
    return 100.0 * numerator / denominator if denominator else 0.0


def vdbench_averages(output_dir: Path | None) -> tuple[float, float]:
    if output_dir is None:
        return 0.0, 0.0
    summary = output_dir / "summary.html"
    if not summary.is_file():
        return 0.0, 0.0

    rates = []
    mb_sec = []
    for raw_line in summary.read_text(encoding="utf-8", errors="replace").splitlines():
        line = re.sub(r"<[^>]+>", " ", raw_line)
        fields = line.split()
        if len(fields) < 14 or not fields[1].startswith("avg_"):
            continue
        try:
            rates.append(float(fields[2]))
            mb_sec.append(float(fields[13]))
        except ValueError:
            continue
    if not rates:
        return 0.0, 0.0
    return statistics.fmean(rates), statistics.fmean(mb_sec)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--header", action="store_true")
    parser.add_argument("--status", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--workload-output", type=Path)
    args = parser.parse_args()

    if args.header:
        print("\t".join(COLUMNS))
        return
    if args.status is None or args.metadata is None:
        parser.error("--status and --metadata are required without --header")

    status = json.loads(args.status.read_text(encoding="utf-8"))["summary"]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    samples = status["samples"]
    training = status["training"]
    confusion = status["confusion_matrix"]
    prediction = status["prediction"]
    heat_state = status["heat_state"]
    latency = status["latency"]["hp_predict_latency"]
    vdbench_rate, vdbench_mb_sec = vdbench_averages(args.workload_output)

    tp = confusion["hp_true_positive_count"]
    fp = confusion["hp_false_positive_count"]
    tn = confusion["hp_true_negative_count"]
    fn = confusion["hp_false_negative_count"]
    labeled = tp + fp + tn + fn
    if samples["hp_labeled_io_total"] != labeled:
        raise SystemExit("confusion matrix does not match labeled I/O count")
    if samples["hp_io_count"] - samples["hp_pending_io_count"] != labeled:
        raise SystemExit("io - pending does not match labeled I/O count")
    if training["hp_train_drop_count"] != 0:
        raise SystemExit("training samples were dropped")

    tpr = ratio(tp, tp + fn)
    tnr = ratio(tn, tn + fp)
    accuracy = ratio(tp + tn, labeled)
    actual_hot_percent = ratio(tp + fn, labeled)
    majority_baseline = max(actual_hot_percent, 100.0 - actual_hot_percent)
    values = {
        "profile": metadata["profile"],
        "otsu_data_source": metadata.get("otsu_data_source", 0),
        "workload": metadata["workload"],
        "repetition": metadata.get("repetition", 1),
        "io": samples["hp_io_count"],
        "labeled": labeled,
        "pending": samples["hp_pending_io_count"],
        "drop": training["hp_train_drop_count"],
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": accuracy,
        "balanced_accuracy": (tpr + tnr) / 2.0,
        "precision": ratio(tp, tp + fp),
        "recall": tpr,
        "pred_hot_percent": ratio(tp + fp, labeled),
        "actual_hot_percent": actual_hot_percent,
        "majority_baseline": majority_baseline,
        "accuracy_excess": accuracy - majority_baseline,
        "hot_threshold": heat_state["hp_hot_threshold_avg"],
        "otsu_candidate_threshold": heat_state["hp_otsu_candidate_threshold_avg"],
        "otsu_separation_percent": heat_state["hp_otsu_separation_percent_avg"],
        "otsu_confidence_percent": heat_state["hp_otsu_confidence_percent_avg"],
        "otsu_vote_count": heat_state["hp_otsu_histogram_vote_count"],
        "predict_threshold": prediction["hp_hot_predict_threshold_avg"],
        "predict_threshold_target": prediction["hp_hot_predict_threshold_target_avg"],
        "snapshot_publish_count": training["hp_snapshot_publish_count"],
        "predict_latency_avg_ns": latency["avgtime_ns"],
        "vdbench_rate": vdbench_rate,
        "vdbench_mb_sec": vdbench_mb_sec,
    }
    print("\t".join(
        f"{values[column]:.6f}" if isinstance(values[column], float)
        else str(values[column])
        for column in COLUMNS
    ))


if __name__ == "__main__":
    main()

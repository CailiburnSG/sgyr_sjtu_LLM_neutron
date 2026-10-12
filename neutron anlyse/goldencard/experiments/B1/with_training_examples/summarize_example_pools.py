#!/usr/bin/env python3
"""Write per-pool and mean±SD Top-K summaries for fixed-example B1 runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent


def read_csv_row(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    all_rows = []
    for metrics_path in sorted((HERE).glob("*/top_k_*/n_*/pool_*/validation_metrics.json")):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        action_rows = {row["action_id"]: row for row in read_csv_row(metrics_path.parent / "b1_action_metrics.csv")}
        all_rows.append({
            "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"],
            "example_count": metrics["fixed_example_count"], "case_count": metrics["case_count"], "pool_id": metrics["example_pool_id"],
            "selection_mode": metrics["selection_mode"], "action_accuracy": metrics["action_accuracy"],
            "action_macro_f1": metrics["action_macro_f1"],
            "a3_f1": float(action_rows["record_processing_and_timestamp_check"]["f1"]),
            "a4_f1": float(action_rows["signal_transmission_path_check"]["f1"]),
            "prompt_tokens": metrics["usage"]["prompt_tokens"], "total_tokens": metrics["usage"]["total_tokens"],
            "latency_mean_seconds": metrics["latency_seconds"]["mean_seconds"],
            "result_directory": str(metrics_path.parent.relative_to(HERE)),
        })
    if not all_rows:
        raise ValueError("No pool results found")
    output_by_model_k: dict[tuple[str, int], list[dict]] = {}
    for row in all_rows:
        output_by_model_k.setdefault((row["model"], row["retrieval_top_k"]), []).append(row)
    for (model, top_k), rows in output_by_model_k.items():
        root = HERE / model / f"top_k_{top_k:02d}"
        fields = list(rows[0])
        write_csv(root / "summary_by_pool.csv", rows, fields)
        grouped: dict[tuple[int, int], list[dict]] = {}
        for row in rows:
            grouped.setdefault((int(row["example_count"]), int(row["case_count"])), []).append(row)
        aggregate = []
        metrics = ("action_accuracy", "action_macro_f1", "a3_f1", "a4_f1", "prompt_tokens", "total_tokens", "latency_mean_seconds")
        for (count, case_count), group in sorted(grouped.items()):
            summary = {"model": model, "retrieval_top_k": top_k, "example_count": count, "case_count": case_count, "pool_count": len(group)}
            for metric in metrics:
                values = [float(row[metric]) for row in group]
                summary[f"{metric}_mean"] = statistics.mean(values)
                summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
            aggregate.append(summary)
        write_csv(root / "summary_by_example_count.csv", aggregate, list(aggregate[0]))


if __name__ == "__main__":
    main()

"""Stable CSV schemas for all B0/B1 experiment outputs.

JSON/JSONL remains the primary format for nested, per-case results.  CSV is
reserved for aggregate metrics, action-level metrics, and error summaries.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_b0_csv(result_dir: Path, rows: list[dict], metrics: dict) -> None:
    run_row = {key: value for key, value in metrics.items() if key not in {"per_action", "confusion_matrix", "gold_action_evidence_candidate_coverage_by_gold_action"}}
    write_csv(result_dir / "b0_run_metrics.csv", [run_row], list(run_row))
    action_rows = [{"experiment_id": metrics["experiment_id"], "retrieval_top_k": metrics["retrieval_top_k"], "action_id": action, **values} for action, values in metrics["per_action"].items()]
    write_csv(result_dir / "b0_action_metrics.csv", action_rows, ["experiment_id", "retrieval_top_k", "action_id", "tp", "fp", "fn", "precision", "recall", "f1"])
    coverage_rows = [{"experiment_id": metrics["experiment_id"], "retrieval_top_k": metrics["retrieval_top_k"], "gold_action_id": action, **values} for action, values in metrics["gold_action_evidence_candidate_coverage_by_gold_action"].items()]
    write_csv(result_dir / "b0_candidate_coverage_by_action.csv", coverage_rows, ["experiment_id", "retrieval_top_k", "gold_action_id", "acceptable_evidence_count", "candidate_coverage_at_k", "candidate_precision_at_k"])


def write_b0_semantic_csv(result_dir: Path, metrics: dict, semantic: dict) -> None:
    run_row = {"experiment_id": metrics["experiment_id"], "retrieval_top_k": metrics["retrieval_top_k"], "semantic_version": "v1", **semantic["totals"]}
    write_csv(result_dir / "b0_semantic_metrics.csv", [run_row], list(run_row))
    action_rows = [{"experiment_id": metrics["experiment_id"], "retrieval_top_k": metrics["retrieval_top_k"], "semantic_version": "v1", **row} for row in semantic["by_action"]]
    write_csv(result_dir / "b0_semantic_by_action.csv", action_rows, list(action_rows[0]))


def write_b1_csv(result_dir: Path, rows: list[dict], metrics: dict) -> None:
    scalar_keys = [key for key, value in metrics.items() if not isinstance(value, (dict, list))]
    run_row = {key: metrics[key] for key in scalar_keys}
    run_row.update({
        "prompt_tokens": metrics["usage"].get("prompt_tokens", 0),
        "completion_tokens": metrics["usage"].get("completion_tokens", 0),
        "total_tokens": metrics["usage"].get("total_tokens", 0),
    })
    write_csv(result_dir / "b1_run_metrics.csv", [run_row], list(run_row))
    action_rows = [{"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "action_id": action, **values} for action, values in metrics["action_per_class"].items()]
    write_csv(result_dir / "b1_action_metrics.csv", action_rows, ["experiment_id", "model", "retrieval_top_k", "action_id", "tp", "fp", "fn", "precision", "recall", "f1"])
    error_rows = [{"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "error_type": key, "case_count": value} for key, value in metrics["error_counts"].items()]
    write_csv(result_dir / "b1_error_counts.csv", error_rows, ["experiment_id", "model", "retrieval_top_k", "error_type", "case_count"])


def write_b1_semantic_csv(result_dir: Path, metrics: dict, semantic: dict) -> None:
    run_row = {
        "experiment_id": metrics["experiment_id"], "model": metrics["model"],
        "retrieval_top_k": metrics["retrieval_top_k"], "split": metrics["split"],
        "semantic_version": "v1", **semantic["totals"],
    }
    write_csv(result_dir / "b1_semantic_metrics.csv", [run_row], list(run_row))
    action_rows = [{
        "experiment_id": metrics["experiment_id"], "model": metrics["model"],
        "retrieval_top_k": metrics["retrieval_top_k"], "semantic_version": "v1", **row,
    } for row in semantic["by_action"]]
    write_csv(result_dir / "b1_semantic_by_action.csv", action_rows, list(action_rows[0]))


def write_b1_stage_summary(stage_dir: Path) -> None:
    rows = []
    for metrics_path in sorted(stage_dir.glob("*/top_k_*/validation_metrics.json")):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        semantic = {}
        semantic_path = metrics_path.parent / "b1_semantic_metrics.csv"
        if semantic_path.exists():
            with semantic_path.open(encoding="utf-8", newline="") as handle:
                semantic = next(csv.DictReader(handle), {})
        rows.append({
            "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "split": metrics["split"],
            "case_count": metrics["case_count"], "json_valid_rate": metrics["json_valid_rate"],
            "constraint_valid_rate": metrics["constraint_valid_rate"], "action_accuracy": metrics["action_accuracy"],
            "action_macro_f1": metrics["action_macro_f1"],
            "semantic_candidate_action_pair_f1_at_k": semantic.get("semantic_candidate_action_pair_f1_at_k"),
            "prompt_tokens": metrics["usage"].get("prompt_tokens", 0),
            "completion_tokens": metrics["usage"].get("completion_tokens", 0),
            "total_tokens": metrics["usage"].get("total_tokens", 0),
            "result_directory": str(metrics_path.parent.relative_to(stage_dir)),
        })
    write_csv(stage_dir / "summary_metrics.csv", rows, ["model", "retrieval_top_k", "split", "case_count", "json_valid_rate", "constraint_valid_rate", "action_accuracy", "action_macro_f1", "semantic_candidate_action_pair_f1_at_k", "prompt_tokens", "completion_tokens", "total_tokens", "result_directory"])

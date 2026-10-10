#!/usr/bin/env python3
"""Migrate existing B0/B1 result JSON artifacts to their primary CSV tables."""

from __future__ import annotations

import json
from pathlib import Path

from result_csv import write_b0_csv, write_b0_semantic_csv, write_b1_csv, write_b1_semantic_csv, write_b1_stage_summary, write_csv
from semantic_metrics import evaluate_b0_semantics, evaluate_b1_semantics, load_units


HERE = Path(__file__).resolve().parent
B0 = HERE / "B0" / "results"
B1_NO_TRAINING = HERE / "B1" / "no_training_examples"
SEMANTIC_MAP = HERE.parents[1] / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"
GOLD = HERE.parent / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
TOP_KS = (3, 5, 8, 10, 12, 15, 20)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def export_b0() -> None:
    sweep, action_rows = [], []
    gold_evidence_by_case = {row["goldcard_id"]: [item["evidence_id"] for item in row["evidence"]] for row in read_jsonl(GOLD)}
    unit_by_evidence = load_units(SEMANTIC_MAP)
    semantic_sweep = []
    for top_k in TOP_KS:
        folder = B0 / f"top_k_{top_k:02d}"
        metrics = json.loads((folder / "b0_bm25_tag_vote_metrics.json").read_text(encoding="utf-8"))
        rows = read_jsonl(folder / "b0_bm25_tag_vote_predictions.jsonl")
        write_b0_csv(folder, rows, metrics)
        semantic = evaluate_b0_semantics(rows, gold_evidence_by_case, unit_by_evidence)
        write_b0_semantic_csv(folder, metrics, semantic)
        semantic_sweep.append({"retrieval_top_k": top_k, "semantic_version": "v1", **semantic["totals"]})
        sweep.append({
            "experiment_id": metrics["experiment_id"], "retrieval_top_k": top_k,
            "case_count": metrics["case_count"], "action_accuracy": metrics["action_accuracy"],
            "action_macro_precision": sum(item["precision"] for item in metrics["per_action"].values()) / len(metrics["per_action"]),
            "action_macro_recall": sum(item["recall"] for item in metrics["per_action"].values()) / len(metrics["per_action"]),
            "action_macro_f1": metrics["macro_f1"],
            "strict_evidence_precision_at_k": metrics["strict_gold_evidence_precision_at_k"],
            "strict_evidence_recall_at_k": metrics["strict_gold_evidence_recall_at_k"],
            "strict_evidence_f1_at_k": metrics["strict_gold_evidence_f1_at_k"],
            "gold_action_candidate_coverage_at_k": metrics["gold_action_evidence_candidate_coverage_at_k"],
            "gold_action_candidate_precision_at_k": metrics["gold_action_evidence_candidate_precision_at_k"],
        })
        action_rows.extend({"retrieval_top_k": top_k, "action_id": action, **values} for action, values in metrics["per_action"].items())
    write_csv(B0 / "b0_k_sweep_metrics.csv", sweep, list(sweep[0]))
    write_csv(B0 / "b0_k_sweep_action_metrics.csv", action_rows, ["retrieval_top_k", "action_id", "tp", "fp", "fn", "precision", "recall", "f1"])
    write_csv(B0 / "b0_semantic_k_sweep_metrics.csv", semantic_sweep, list(semantic_sweep[0]))


def export_b1() -> None:
    for metrics_path in B1_ZS.glob("*/top_k_*/validation_metrics.json"):
        folder = metrics_path.parent
        rows = read_jsonl(folder / "validation_predictions.jsonl")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        write_b1_csv(folder, rows, metrics)
        write_b1_semantic_csv(folder, metrics, evaluate_b1_semantics(rows, load_units(SEMANTIC_MAP)))
    write_b1_stage_summary(B1_NO_TRAINING)


def main() -> None:
    export_b0()
    export_b1()
    print("CSV export complete for B0 and B1 no-training-examples stage.")


if __name__ == "__main__":
    main()

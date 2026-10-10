#!/usr/bin/env python3
"""Run the frozen B0 baseline across the shared B0/B1 candidate-size grid."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TOP_K_VALUES = (3, 5, 8, 10, 12, 15, 20)


def main() -> None:
    spec = importlib.util.spec_from_file_location("b0", HERE / "b0_bm25_tag_vote_baseline.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    rows = []
    for top_k in TOP_K_VALUES:
        metrics = module.run(top_k)
        rows.append({
            "top_k": top_k,
            "action_accuracy": metrics["action_accuracy"],
            "action_macro_precision": sum(item["precision"] for item in metrics["per_action"].values()) / len(metrics["per_action"]),
            "action_macro_recall": sum(item["recall"] for item in metrics["per_action"].values()) / len(metrics["per_action"]),
            "macro_f1": metrics["macro_f1"],
            "strict_evidence_precision_at_k": metrics["strict_gold_evidence_precision_at_k"],
            "strict_evidence_recall_at_k": metrics["strict_gold_evidence_recall_at_k"],
            "strict_evidence_f1_at_k": metrics["strict_gold_evidence_f1_at_k"],
            "gold_action_candidate_coverage_at_k": metrics["gold_action_evidence_candidate_coverage_at_k"],
            "gold_action_candidate_precision_at_k": metrics["gold_action_evidence_candidate_precision_at_k"],
        })
    results = HERE / "results"
    (results / "b0_k_sweep_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# B0：候选规模 K 扫描", "",
        "| K | Action Acc. | Action Macro-P | Action Macro-R | Action Macro-F1 | 严格证据 P@K | 严格证据 R@K | 严格证据 F1@K | 金标准行动证据覆盖@K | 金标准行动候选 P@K |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append("| {top_k} | {action_accuracy:.3f} | {action_macro_precision:.3f} | {action_macro_recall:.3f} | {macro_f1:.3f} | {strict_evidence_precision_at_k:.3f} | {strict_evidence_recall_at_k:.3f} | {strict_evidence_f1_at_k:.3f} | {gold_action_candidate_coverage_at_k:.3f} | {gold_action_candidate_precision_at_k:.3f} |".format(**row))
    (results / "b0_k_sweep_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    detail = [
        "# B0：按行动类别的 Precision、Recall、F1", "",
        "| K | 行动 | Precision | Recall | F1 | TP | FP | FN |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for top_k in TOP_K_VALUES:
        metrics = json.loads((results / f"top_k_{top_k:02d}" / "b0_bm25_tag_vote_metrics.json").read_text(encoding="utf-8"))
        for action, item in metrics["per_action"].items():
            detail.append(f"| {top_k} | `{action}` | {item['precision']:.3f} | {item['recall']:.3f} | {item['f1']:.3f} | {item['tp']} | {item['fp']} | {item['fn']} |")
    (results / "b0_k_sweep_by_action.md").write_text("\n".join(detail) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

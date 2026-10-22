"""Semantic evidence and semantic-evidence--action scoring for B1 outputs."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def load_units(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            result[row["evidence_id"]].add(row["semantic_unit_id"])
    return result


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _set_scores(predicted: set[tuple] | set[str], gold: set[tuple] | set[str]) -> tuple[float, float, float]:
    overlap = len(predicted & gold)
    precision = overlap / len(predicted) if predicted else 0.0
    recall = overlap / len(gold) if gold else 0.0
    return precision, recall, _f1(precision, recall)


def evaluate_b1_semantics(rows: list[dict], unit_by_evidence: dict[str, set[str]]) -> dict:
    per_case, per_action = [], defaultdict(list)
    for row in rows:
        gold_evidence = row["gold"]["evidence_ids"]
        predicted_evidence = [item["evidence_id"] for item in row["prediction"].get("selected_evidence", []) if isinstance(item, dict) and item.get("evidence_id")]
        missing = sorted({evidence_id for evidence_id in gold_evidence + predicted_evidence if evidence_id not in unit_by_evidence})
        gold_units = set().union(*(unit_by_evidence[item] for item in gold_evidence))
        predicted_units = set().union(*(unit_by_evidence[item] for item in predicted_evidence)) if predicted_evidence else set()
        ep, er, ef1 = _set_scores(predicted_units, gold_units)
        predicted_pairs = {(unit, row["prediction"].get("action_id")) for unit in predicted_units}
        gold_pairs = {(unit, row["gold"]["action_id"]) for unit in gold_units}
        pp, pr, pf1 = _set_scores(predicted_pairs, gold_pairs)
        item = {
            "goldcard_id": row["goldcard_id"], "gold_action_id": row["gold"]["action_id"],
            "semantic_evidence_precision": ep, "semantic_evidence_recall": er, "semantic_evidence_f1": ef1,
            "semantic_action_pair_precision": pp, "semantic_action_pair_recall": pr, "semantic_action_pair_f1": pf1,
            "missing_semantic_mapping_ids": ";".join(missing),
        }
        per_case.append(item)
        per_action[item["gold_action_id"]].append(item)
    def average(items: list[dict], key: str) -> float:
        return sum(item[key] for item in items) / len(items) if items else 0.0
    totals = {
        "semantic_evidence_precision": average(per_case, "semantic_evidence_precision"),
        "semantic_evidence_recall": average(per_case, "semantic_evidence_recall"),
        "semantic_evidence_f1": average(per_case, "semantic_evidence_f1"),
        "semantic_action_pair_precision": average(per_case, "semantic_action_pair_precision"),
        "semantic_action_pair_recall": average(per_case, "semantic_action_pair_recall"),
        "semantic_action_pair_f1": average(per_case, "semantic_action_pair_f1"),
        "unmapped_evidence_id_count": sum(bool(item["missing_semantic_mapping_ids"]) for item in per_case),
    }
    action_rows = [{"gold_action_id": action, "case_count": len(items), **{key: average(items, key) for key in (
        "semantic_evidence_precision", "semantic_evidence_recall", "semantic_evidence_f1",
        "semantic_action_pair_precision", "semantic_action_pair_recall", "semantic_action_pair_f1",
    )}} for action, items in sorted(per_action.items())]
    return {"totals": totals, "by_action": action_rows, "per_case": per_case}


def evaluate_b0_semantics(rows: list[dict], gold_evidence_by_case: dict[str, list[str]], unit_by_evidence: dict[str, set[str]]) -> dict:
    """Score a full Top-K candidate package and its predicted action.

    Both B0 and formal B1 now supply all Top-K cards.  The candidate semantic
    F1 therefore measures common retrieval quality; the semantic-unit/action
    pair F1 additionally reflects each method's different predicted action.
    """
    per_case, per_action = [], defaultdict(list)
    for row in rows:
        gold_evidence = gold_evidence_by_case[row["goldcard_id"]]
        evidence_items = row["selected_evidence"] if "selected_evidence" in row else row["retrieved_evidence"]
        retrieved_evidence = [item["evidence_id"] for item in evidence_items]
        missing = sorted({item for item in gold_evidence + retrieved_evidence if item not in unit_by_evidence})
        gold_units = set().union(*(unit_by_evidence[item] for item in gold_evidence))
        retrieved_units = set().union(*(unit_by_evidence[item] for item in retrieved_evidence))
        ep, er, ef1 = _set_scores(retrieved_units, gold_units)
        predicted_pairs = {(unit, row["predicted_action_id"]) for unit in retrieved_units}
        gold_pairs = {(unit, row["gold_action_id"]) for unit in gold_units}
        pp, pr, pf1 = _set_scores(predicted_pairs, gold_pairs)
        item = {
            "goldcard_id": row["goldcard_id"], "gold_action_id": row["gold_action_id"],
            "semantic_candidate_precision_at_k": ep, "semantic_candidate_recall_at_k": er,
            "semantic_candidate_f1_at_k": ef1, "semantic_candidate_coverage_at_k": int(bool(retrieved_units & gold_units)),
            "semantic_candidate_action_pair_precision_at_k": pp, "semantic_candidate_action_pair_recall_at_k": pr,
            "semantic_candidate_action_pair_f1_at_k": pf1, "missing_semantic_mapping_ids": ";".join(missing),
        }
        per_case.append(item)
        per_action[item["gold_action_id"]].append(item)
    def average(items: list[dict], key: str) -> float:
        return sum(item[key] for item in items) / len(items) if items else 0.0
    keys = (
        "semantic_candidate_precision_at_k", "semantic_candidate_recall_at_k", "semantic_candidate_f1_at_k",
        "semantic_candidate_coverage_at_k", "semantic_candidate_action_pair_precision_at_k",
        "semantic_candidate_action_pair_recall_at_k", "semantic_candidate_action_pair_f1_at_k",
    )
    totals = {key: average(per_case, key) for key in keys}
    totals["unmapped_evidence_id_count"] = sum(bool(item["missing_semantic_mapping_ids"]) for item in per_case)
    action_rows = [{"gold_action_id": action, "case_count": len(items), **{key: average(items, key) for key in keys}} for action, items in sorted(per_action.items())]
    return {"totals": totals, "by_action": action_rows, "per_case": per_case}

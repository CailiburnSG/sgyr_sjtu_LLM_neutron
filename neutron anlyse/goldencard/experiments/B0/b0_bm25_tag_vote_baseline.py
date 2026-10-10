#!/usr/bin/env python3
"""B0: BM25 retrieval plus applicability-tag voting, with no LLM.

Unlike an event-type routing rule, this baseline never reads the gold action
label. It serializes the observed event combination, retrieves a candidate
pool from the full evidence library, and maps all retrieved cards' existing
applicability tags to an action score.
"""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[2]
sys.path.insert(0, str(NEUTRON_ROOT))
sys.path.insert(0, str(HERE.parent))

from evidencecard.workflow import load_cards, rank_candidates  # noqa: E402
from result_csv import write_b0_csv, write_b0_semantic_csv  # noqa: E402
from semantic_metrics import evaluate_b0_semantics, load_units  # noqa: E402


GOLD = NEUTRON_ROOT / "goldencard" / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
CARD_PATHS = [
    NEUTRON_ROOT / "evidencecard" / "cards" / "core_seed_evidence.jsonl",
    NEUTRON_ROOT / "evidencecard" / "cards" / "neutron_current_seed_evidence.jsonl",
]
CATALOG = NEUTRON_ROOT / "evidencecard" / "catalog" / "core_sources.jsonl"

A1 = "on_site_operation_or_calibration_check"
A2 = "cross_channel_similar_anomaly_comparison"
A3 = "record_processing_and_timestamp_check"
A4 = "signal_transmission_path_check"
ACTIONS = (A1, A2, A3, A4)

# This is the fixed meaning of the four public action definitions, not an
# event-type-to-label lookup.  The baseline can only vote from retrieved cards.
ACTION_TAGS = {
    A1: {"calibration_activity_check"},
    A2: {"channel_comparison", "neutron_current_channel_comparison"},
    A3: {"data_qualification", "missing_data_check", "stuck_signal_screening", "historian_sampling_check"},
    A4: {"signal_path_context", "neutron_current_signal_path_context"},
}


def query_for(case: dict, source_tiers: list[str]) -> dict:
    components = case["precheck_input"]["component_summary"]
    type_terms = [item["event_type"].replace("_", " ") for item in components]
    scope_terms = [item["scope"].replace("_", " ") for item in components]
    text = "neutron current " + " ".join(type_terms + scope_terms) + " anomaly precheck"
    return {
        "query_id": "B0-" + case["goldcard_id"],
        "query_text": text,
        "filters": {"source_tier": source_tiers, "preferred_applicability": []},
    }


def choose_action(candidates: list[dict], cards_by_id: dict[str, dict]) -> tuple[str, dict[str, float]]:
    scores = {action: 0.0 for action in ACTIONS}
    for candidate in candidates:
        card = cards_by_id[candidate["evidence_id"]]
        matched = set(card.get("applicability", []))
        # BM25 scores determine strength; rank provides a stable small
        # secondary preference when scores are close.
        weight = float(candidate["score"]) + 1.0 / candidate["rank"]
        for action, tags in ACTION_TAGS.items():
            # Normalize by profile size so an action with more applicability
            # aliases (e.g. A3) does not win solely because it has more tags.
            scores[action] += weight * len(matched.intersection(tags)) / len(tags)
    action = max(ACTIONS, key=lambda item: (scores[item], -ACTIONS.index(item)))
    return action, {key: round(value, 6) for key, value in scores.items()}


def action_metrics(rows: list[dict]) -> dict:
    result = {}
    for action in ACTIONS:
        tp = sum(row["predicted_action_id"] == action and row["gold_action_id"] == action for row in rows)
        fp = sum(row["predicted_action_id"] == action and row["gold_action_id"] != action for row in rows)
        fn = sum(row["predicted_action_id"] != action and row["gold_action_id"] == action for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result[action] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}
    return result


def run(top_k: int) -> dict:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    cases = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = load_cards(CARD_PATHS, CATALOG)
    cards_by_id = {card["evidence_id"]: card for card in cards}
    source_tiers = sorted({card.get("source_tier") for card in cards if card.get("source_tier")})
    rows = []
    for case in cases:
        candidates = rank_candidates(query_for(case, source_tiers), cards, top_k=top_k)
        predicted, action_scores = choose_action(candidates, cards_by_id)
        gold_action = case["gold_action_links"][0]["action_id"]
        gold_evidence = {item["evidence_id"] for item in case["evidence"]}
        predicted_evidence = [item["evidence_id"] for item in candidates]
        overlap = len(gold_evidence.intersection(predicted_evidence))
        rows.append({
            "goldcard_id": case["goldcard_id"],
            "query_text": query_for(case, source_tiers)["query_text"],
            "retrieved_evidence": candidates,
            "predicted_action_id": predicted,
            "gold_action_id": gold_action,
            "action_scores": action_scores,
            "correct": predicted == gold_action,
            "gold_evidence_overlap_count": overlap,
        })
    per_action = action_metrics(rows)
    evidence_precision = sum(row["gold_evidence_overlap_count"] / top_k for row in rows) / len(rows)
    evidence_recall = sum(row["gold_evidence_overlap_count"] / 3 for row in rows) / len(rows)
    evidence_f1 = 2 * evidence_precision * evidence_recall / (evidence_precision + evidence_recall) if evidence_precision + evidence_recall else 0.0
    confusion = {gold: {pred: 0 for pred in ACTIONS} for gold in ACTIONS}
    for row in rows:
        confusion[row["gold_action_id"]][row["predicted_action_id"]] += 1
    # A card is category-acceptable if annotators have associated it with the
    # same gold action anywhere in this frozen gold standard. This set is used
    # only after prediction for evaluation; it is never read by B0 retrieval
    # or tag voting.
    acceptable_by_action = {action: set() for action in ACTIONS}
    for case in cases:
        action = case["gold_action_links"][0]["action_id"]
        acceptable_by_action[action].update(item["evidence_id"] for item in case["evidence"])
    category_by_action = {}
    category_hit_values = []
    category_precision_values = []
    for action in ACTIONS:
        action_rows = [row for row in rows if row["gold_action_id"] == action]
        hits, matched_cards = 0, 0
        for row in action_rows:
            retrieved_ids = {item["evidence_id"] for item in row["retrieved_evidence"]}
            match_count = len(retrieved_ids.intersection(acceptable_by_action[action]))
            hits += int(match_count > 0)
            matched_cards += match_count
            category_hit_values.append(int(match_count > 0))
            category_precision_values.append(match_count / top_k)
        category_by_action[action] = {
            "acceptable_evidence_count": len(acceptable_by_action[action]),
            "candidate_coverage_at_k": hits / len(action_rows),
            "candidate_precision_at_k": matched_cards / (top_k * len(action_rows)),
        }
    metrics = {
        "experiment_id": "B0_bm25_tag_vote_v3_all_topk",
        "gold_standard": str(GOLD.relative_to(NEUTRON_ROOT.parent)),
        "case_count": len(rows),
        "evidence_library_card_count": len(cards),
        "retrieval_top_k": top_k,
        "action_accuracy": sum(row["correct"] for row in rows) / len(rows),
        "macro_f1": sum(item["f1"] for item in per_action.values()) / len(per_action),
        "per_action": per_action,
        "confusion_matrix": confusion,
        "strict_gold_evidence_precision_at_k": evidence_precision,
        "strict_gold_evidence_recall_at_k": evidence_recall,
        "strict_gold_evidence_f1_at_k": evidence_f1,
        "gold_action_evidence_candidate_coverage_at_k": sum(category_hit_values) / len(category_hit_values),
        "gold_action_evidence_candidate_precision_at_k": sum(category_precision_values) / len(category_precision_values),
        "gold_action_evidence_candidate_coverage_by_gold_action": category_by_action,
        "scope_note": f"No LLM; no case-level gold action or gold evidence is used during prediction. All BM25 top-{top_k} cards are presented as the candidate evidence package and vote through their applicability tags.",
    }
    result_dir = HERE / "results" / f"top_k_{top_k:02d}"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "b0_bm25_tag_vote_predictions.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    (result_dir / "b0_bm25_tag_vote_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_b0_csv(result_dir, rows, metrics)
    semantic_map = NEUTRON_ROOT / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"
    gold_evidence_by_case = {case["goldcard_id"]: [item["evidence_id"] for item in case["evidence"]] for case in cases}
    write_b0_semantic_csv(result_dir, metrics, evaluate_b0_semantics(rows, gold_evidence_by_case, load_units(semantic_map)))
    print(json.dumps({"top_k": top_k, "action_accuracy": metrics["action_accuracy"], "macro_f1": metrics["macro_f1"], "evidence_f1_at_k": evidence_f1, "case_count": len(rows)}, ensure_ascii=False))
    return metrics


def main() -> None:
    parser = ArgumentParser(description="B0 BM25 retrieval plus applicability-tag voting")
    parser.add_argument("--top-k", type=int, default=10, help="number of BM25 candidates to retrieve and vote over")
    args = parser.parse_args()
    run(args.top_k)


if __name__ == "__main__":
    main()

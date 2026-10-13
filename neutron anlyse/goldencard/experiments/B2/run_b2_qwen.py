#!/usr/bin/env python3
"""B2: fresh LLM full-library evidence selection followed by action choice.

Each case makes two calls.  The first sees a fixed catalogue of all reviewed
cards and returns exactly K evidence IDs.  The second sees only the cards
selected in that same case/run and returns one constrained precheck action.
No gold label or goldcard_id is placed in either model prompt.
"""
from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
B1_NO_TRAINING = EXPERIMENTS / "B1" / "no_training_examples"
B1_DATA = EXPERIMENTS / "B1" / "data"
NEUTRON_ROOT = EXPERIMENTS.parents[1]
sys.path.insert(0, str(B1_NO_TRAINING))
sys.path.insert(0, str(EXPERIMENTS / "B1"))
sys.path.insert(0, str(EXPERIMENTS))

from run_no_training_qwen import (  # noqa: E402
    DEFAULT_BASE_URL, DEFAULT_KEY_FILE, DEFAULT_MODEL, call_qwen, load_key,
    parse_json, read_jsonl, write_jsonl,
)
from semantic_metrics import evaluate_b0_semantics, load_units  # noqa: E402
from result_csv import write_csv  # noqa: E402

ACTIONS = tuple(json.loads((B1_DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])
CARD_PATHS = [
    NEUTRON_ROOT / "evidencecard" / "cards" / "core_seed_evidence.jsonl",
    NEUTRON_ROOT / "evidencecard" / "cards" / "neutron_current_seed_evidence.jsonl",
]
CATALOG_PATH = NEUTRON_ROOT / "evidencecard" / "catalog" / "core_sources.jsonl"


def load_cards() -> list[dict]:
    source_catalogue = {row["doc_id"]: row for row in read_jsonl(CATALOG_PATH)}
    cards = []
    for path in CARD_PATHS:
        for card in read_jsonl(path):
            merged = dict(card)
            for field in ("measurement_scope", "neutron_current_relevance", "transfer_note", "scope_note"):
                if merged.get(field) is None and field in source_catalogue.get(merged.get("doc_id"), {}):
                    merged[field] = source_catalogue[merged["doc_id"]][field]
            cards.append(merged)
    ids = [card.get("evidence_id") for card in cards]
    if len(cards) != 300 or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("B2 requires exactly 300 reviewed cards with unique evidence_id values")
    required = ("topic_tags", "applicability")
    missing = [card["evidence_id"] for card in cards if any(not isinstance(card.get(field), list) for field in required)]
    if missing:
        raise ValueError(f"B2 card metadata missing required fields: {missing[:5]}")
    # This representation deliberately matches the reviewed evidence fields
    # available to B1, except for BM25-specific rank/score.  It contains no
    # gold action, gold evidence, or case ID.
    fields = ("evidence_id", "doc_id", "source_org", "source_tier", "measurement_scope", "neutron_current_relevance", "section_path", "markdown_line_start", "markdown_line_end", "topic_tags", "applicability", "transfer_note", "scope_note", "text")
    return [{key: card.get(key) for key in fields} for card in cards]


def model_case(case: dict) -> dict:
    # B2 must see the event combination itself, not B1/B0 bookkeeping or the
    # lexical query that was used to build a BM25 package.
    return {"precheck_input": case["precheck_input"]}


def select_messages(case: dict, catalogue: list[dict], actions: list[dict], top_k: int) -> list[dict]:
    system = (
        "You are an evidence selector for neutron-current anomaly precheck. "
        "Select evidence that can support why a human should prioritize one of "
        "the supplied fixed precheck actions, without diagnosing a fault or "
        "confirming a cause. Use evidence text and its reviewed metadata, "
        "including topic_tags, applicability, scope and relevance limits. "
        "Use only IDs in the supplied library. Return JSON only: "
        '{"selected_evidence_ids":["..."],"selection_boundary_note":"..."}. '
        f"Select exactly {top_k} distinct IDs. Do not output an action or a diagnosis."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({
        "event_combination": model_case(case), "action_definitions": actions,
        "evidence_library": catalogue,
    }, ensure_ascii=False)}]


def action_messages(case: dict, selected: list[dict], actions: list[dict], contract: dict) -> list[dict]:
    system = (
        "You are a neutron-current anomaly precheck assistant. Read the event "
        "combination and only the supplied evidence cards. Select exactly one fixed "
        "precheck action. Do not diagnose a root cause, confirm a fault, assert a "
        "causal relationship, or confirm that any operation occurred. Return JSON only."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({
        "event_combination": model_case(case), "selected_evidence": selected,
        "action_definitions": actions, "output_contract": contract,
    }, ensure_ascii=False)}]


def selection_errors(value: dict | None, allowed: set[str], top_k: int) -> list[str]:
    if value is None:
        return ["invalid_json"]
    ids = value.get("selected_evidence_ids")
    errors = []
    if not isinstance(ids, list):
        errors.append("missing_selected_evidence_ids")
    else:
        if len(ids) != top_k:
            errors.append("wrong_selected_evidence_count")
        if not all(isinstance(item, str) for item in ids):
            errors.append("non_string_evidence_id")
        if len(set(ids)) != len(ids):
            errors.append("duplicate_evidence_id")
        if not set(ids).issubset(allowed):
            errors.append("unknown_evidence_id")
    if not isinstance(value.get("selection_boundary_note"), str) or not value["selection_boundary_note"].strip():
        errors.append("missing_selection_boundary_note")
    return sorted(set(errors))


def action_errors(value: dict | None) -> list[str]:
    if value is None:
        return ["invalid_json"]
    errors = []
    if value.get("action_id") not in ACTIONS:
        errors.append("invalid_action_id")
    if not isinstance(value.get("boundary_note"), str) or not value["boundary_note"].strip():
        errors.append("missing_boundary_note")
    return errors


def action_metrics(rows: list[dict]) -> tuple[dict, float]:
    details = {}
    for action in ACTIONS:
        tp = sum(r["action_prediction"].get("action_id") == action and r["gold_action_id"] == action for r in rows)
        fp = sum(r["action_prediction"].get("action_id") == action and r["gold_action_id"] != action for r in rows)
        fn = sum(r["action_prediction"].get("action_id") != action and r["gold_action_id"] == action for r in rows)
        p, recall = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
        details[action] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": recall, "f1": 2 * p * recall / (p + recall) if p + recall else 0.0}
    return details, sum(item["f1"] for item in details.values()) / len(details)


def usage(rows: list[dict], stage: str) -> dict:
    return {key: sum(r[stage]["api"].get("usage", {}).get(key, 0) or 0 for r in rows) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def strict_evidence_metrics(rows: list[dict], top_k: int, all_targets: dict[str, dict]) -> dict:
    """Score selected card IDs against frozen gold IDs after model inference only."""
    overlaps = []
    acceptable_by_action = {action: set() for action in ACTIONS}
    for target in all_targets.values():
        acceptable_by_action[target["action_id"]].update(target["action_evidence_ids"])
    by_action, coverage_values, category_precision_values = {}, [], []
    for row in rows:
        selected_ids = {card["evidence_id"] for card in row["selected_evidence"]}
        gold_ids = set(row["gold_evidence_ids"])
        overlaps.append(len(selected_ids & gold_ids))
    precision = sum(value / top_k for value in overlaps) / len(rows)
    recall = sum(value / len(row["gold_evidence_ids"]) for value, row in zip(overlaps, rows)) / len(rows)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    for action in ACTIONS:
        action_rows = [row for row in rows if row["gold_action_id"] == action]
        hits, matches = 0, 0
        for row in action_rows:
            selected_ids = {card["evidence_id"] for card in row["selected_evidence"]}
            count = len(selected_ids & acceptable_by_action[action])
            hits += int(count > 0)
            matches += count
            coverage_values.append(int(count > 0))
            category_precision_values.append(count / top_k)
        by_action[action] = {
            "acceptable_evidence_count": len(acceptable_by_action[action]),
            "candidate_coverage_at_k": hits / len(action_rows) if action_rows else 0.0,
            "candidate_precision_at_k": matches / (top_k * len(action_rows)) if action_rows else 0.0,
        }
    return {
        "strict_gold_evidence_precision_at_k": precision,
        "strict_gold_evidence_recall_at_k": recall,
        "strict_gold_evidence_f1_at_k": f1,
        "gold_action_evidence_candidate_coverage_at_k": sum(coverage_values) / len(coverage_values),
        "gold_action_evidence_candidate_precision_at_k": sum(category_precision_values) / len(category_precision_values),
        "gold_action_evidence_candidate_coverage_by_gold_action": by_action,
    }


def write_b2_csv(result_dir: Path, metrics: dict, semantic: dict) -> None:
    """Write flat B2 statistics while preserving JSON/JSONL as raw records."""
    selection_usage, action_usage = metrics["usage"]["selection"], metrics["usage"]["action"]
    run_row = {
        "experiment_id": metrics["experiment_id"], "model": metrics["model"],
        "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"],
        "split": metrics["split"], "run_at_utc": metrics["run_at_utc"],
        "case_count": metrics["case_count"],
        "selection_json_valid_rate": metrics["selection_json_valid_rate"],
        "selection_contract_valid_rate": metrics["selection_contract_valid_rate"],
        "action_json_valid_rate": metrics["action_json_valid_rate"],
        "action_contract_valid_rate": metrics["action_contract_valid_rate"],
        "action_accuracy": metrics["action_accuracy"], "action_macro_f1": metrics["action_macro_f1"],
        "strict_gold_evidence_precision_at_k": metrics["strict_gold_evidence_precision_at_k"],
        "strict_gold_evidence_recall_at_k": metrics["strict_gold_evidence_recall_at_k"],
        "strict_gold_evidence_f1_at_k": metrics["strict_gold_evidence_f1_at_k"],
        "gold_action_evidence_candidate_coverage_at_k": metrics["gold_action_evidence_candidate_coverage_at_k"],
        "gold_action_evidence_candidate_precision_at_k": metrics["gold_action_evidence_candidate_precision_at_k"],
        "selection_prompt_tokens": selection_usage["prompt_tokens"],
        "selection_completion_tokens": selection_usage["completion_tokens"],
        "selection_total_tokens": selection_usage["total_tokens"],
        "action_prompt_tokens": action_usage["prompt_tokens"],
        "action_completion_tokens": action_usage["completion_tokens"],
        "action_total_tokens": action_usage["total_tokens"],
        "combined_total_tokens": selection_usage["total_tokens"] + action_usage["total_tokens"],
    }
    write_csv(result_dir / "b2_run_metrics.csv", [run_row], list(run_row))
    action_rows = [{"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "action_id": action, **values} for action, values in metrics["action_per_class"].items()]
    write_csv(result_dir / "b2_action_metrics.csv", action_rows, list(action_rows[0]))
    error_rows = []
    for stage, values in (("selection", metrics["selection_error_counts"]), ("action", metrics["action_error_counts"])):
        error_rows.extend({"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "stage": stage, "error_type": error, "case_count": count} for error, count in values.items())
    write_csv(result_dir / "b2_error_counts.csv", error_rows, ["experiment_id", "model", "retrieval_top_k", "run_id", "stage", "error_type", "case_count"])
    semantic_row = {"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "split": metrics["split"], "semantic_version": "v1", **semantic["totals"]}
    write_csv(result_dir / "b2_semantic_metrics.csv", [semantic_row], list(semantic_row))
    by_action = [{"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "semantic_version": "v1", **row} for row in semantic["by_action"]]
    write_csv(result_dir / "b2_semantic_by_action.csv", by_action, list(by_action[0]))
    strict_by_action = [{"experiment_id": metrics["experiment_id"], "model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "gold_action_id": action, **values} for action, values in metrics["gold_action_evidence_candidate_coverage_by_gold_action"].items()]
    write_csv(result_dir / "b2_strict_candidate_coverage_by_action.csv", strict_by_action, list(strict_by_action[0]))


def write_b2_stage_summary(stage_dir: Path) -> None:
    rows = []
    for metrics_path in sorted(stage_dir.rglob("validation_metrics.json")):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics.get("experiment_id") != "B2_llm_full_library_selection_then_action_v1":
            continue
        selection_usage, action_usage = metrics["usage"]["selection"], metrics["usage"]["action"]
        rows.append({"model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "run_id": metrics["run_id"], "split": metrics["split"], "case_count": metrics["case_count"], "selection_contract_valid_rate": metrics["selection_contract_valid_rate"], "action_contract_valid_rate": metrics["action_contract_valid_rate"], "action_accuracy": metrics["action_accuracy"], "action_macro_f1": metrics["action_macro_f1"], "strict_gold_evidence_f1_at_k": metrics.get("strict_gold_evidence_f1_at_k", ""), "semantic_candidate_action_pair_f1_at_k": metrics["semantic_metrics"]["semantic_candidate_action_pair_f1_at_k"], "selection_total_tokens": selection_usage["total_tokens"], "action_total_tokens": action_usage["total_tokens"], "combined_total_tokens": selection_usage["total_tokens"] + action_usage["total_tokens"], "result_directory": str(metrics_path.parent.relative_to(stage_dir))})
    write_csv(stage_dir / "summary_metrics.csv", rows, ["model", "retrieval_top_k", "run_id", "split", "case_count", "selection_contract_valid_rate", "action_contract_valid_rate", "action_accuracy", "action_macro_f1", "strict_gold_evidence_f1_at_k", "semantic_candidate_action_pair_f1_at_k", "selection_total_tokens", "action_total_tokens", "combined_total_tokens", "result_directory"])


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--run-id", help="Fresh independent end-to-end run identifier")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--backfill-result-dir", type=Path, help="Write B2 CSV files for an existing completed result; makes no API calls")
    parser.add_argument("--validate-only", action="store_true", help="Validate frozen inputs and prompt-field isolation; makes no API calls")
    args = parser.parse_args()
    if args.backfill_result_dir:
        metrics_path = args.backfill_result_dir / "validation_metrics.json"
        semantic_path = args.backfill_result_dir / "b2_semantic_metrics.json"
        metrics, semantic = json.loads(metrics_path.read_text(encoding="utf-8")), json.loads(semantic_path.read_text(encoding="utf-8"))
        rows = read_jsonl(args.backfill_result_dir / "validation_predictions.jsonl")
        all_targets = {r["goldcard_id"]: r["target"] for path in (B1_DATA / "labels" / "train_gold_targets.jsonl", B1_DATA / "labels" / "validation_gold_labels.jsonl") for r in read_jsonl(path)}
        metrics.update(strict_evidence_metrics(rows, metrics["retrieval_top_k"], all_targets))
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_b2_csv(args.backfill_result_dir, metrics, semantic)
        write_b2_stage_summary(HERE / "notrain")
        print(json.dumps({"backfilled": str(args.backfill_result_dir), "run_id": metrics["run_id"]}, ensure_ascii=False))
        return
    if not args.run_id and not args.validate_only:
        parser.error("--run-id is required unless --backfill-result-dir is used")
    if args.top_k < 1 or args.top_k > 300:
        raise ValueError("--top-k must be between 1 and 300")
    inputs = read_jsonl(B1_DATA / "candidate_packages" / f"top_k_{args.top_k:02d}" / "validation_inputs.jsonl")
    labels = {r["goldcard_id"]: r["target"] for r in read_jsonl(B1_DATA / "labels" / "validation_gold_labels.jsonl")}
    all_targets = {r["goldcard_id"]: r["target"] for path in (B1_DATA / "labels" / "train_gold_targets.jsonl", B1_DATA / "labels" / "validation_gold_labels.jsonl") for r in read_jsonl(path)}
    actions = json.loads((B1_DATA / "action_definitions.json").read_text(encoding="utf-8"))
    contract = json.loads((B1_DATA / "output_contract.json").read_text(encoding="utf-8"))
    catalogue = load_cards()
    cards_by_id = {card["evidence_id"]: card for card in catalogue}
    sample_prompt = select_messages(inputs[0], catalogue, actions, args.top_k)
    serialized_prompt = json.dumps(sample_prompt, ensure_ascii=False)
    forbidden = ("goldcard_id", "gold_action", "gold_evidence", "validation_gold")
    leaked = [item for item in forbidden if item in serialized_prompt]
    if leaked:
        raise RuntimeError(f"B2 selector prompt contains forbidden evaluation fields: {leaked}")
    if args.validate_only:
        print(json.dumps({"validation_case_count": len(inputs), "card_count": len(catalogue), "top_k": args.top_k, "required_card_fields": ["topic_tags", "applicability"], "selector_action_definitions_present": True, "forbidden_prompt_fields": leaked}, ensure_ascii=False))
        return
    key = load_key(args.key_file)
    inputs = inputs[:args.limit] if args.limit else inputs
    rows = []
    for index, case in enumerate(inputs, 1):
        print(f"[{index}/{len(inputs)}] {case['goldcard_id']}", flush=True)
        try:
            select_raw, select_api = call_qwen(select_messages(case, catalogue, actions, args.top_k), key, args.base_url, args.model)
            selection, select_parse_error = parse_json(select_api["content"])
            select_errors = selection_errors(selection, set(cards_by_id), args.top_k)
        except Exception as exc:
            select_raw, select_api, selection, select_parse_error, select_errors = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}, {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        selected = [cards_by_id[item] for item in selection.get("selected_evidence_ids", []) if item in cards_by_id]
        try:
            action_raw, action_api = call_qwen(action_messages(case, selected, actions, contract), key, args.base_url, args.model)
            action, action_parse_error = parse_json(action_api["content"])
            act_errors = action_errors(action)
        except Exception as exc:
            action_raw, action_api, action, action_parse_error, act_errors = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}, {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        rows.append({"goldcard_id": case["goldcard_id"], "run_id": args.run_id, "retrieval_top_k": args.top_k,
                     "selection": {"prediction": selection or {}, "parse_error": select_parse_error, "validation_errors": select_errors, "api": select_api, "raw_response": select_raw},
                     "selected_evidence": selected,
                     "action": {"prediction": action or {}, "parse_error": action_parse_error, "validation_errors": act_errors, "api": action_api, "raw_response": action_raw},
                     "action_prediction": action or {}, "gold_action_id": labels[case["goldcard_id"]]["action_id"],
                     "gold_evidence_ids": labels[case["goldcard_id"]]["action_evidence_ids"]})
    per_action, macro = action_metrics(rows)
    semantic_rows = [{"goldcard_id": r["goldcard_id"], "retrieved_evidence": [{"evidence_id": c["evidence_id"], "rank": i + 1} for i, c in enumerate(r["selected_evidence"])], "predicted_action_id": r["action_prediction"].get("action_id"), "gold_action_id": r["gold_action_id"]} for r in rows]
    semantic = evaluate_b0_semantics(semantic_rows, {r["goldcard_id"]: r["gold_evidence_ids"] for r in rows}, load_units(NEUTRON_ROOT / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"))
    metrics = {"experiment_id": "B2_llm_full_library_selection_then_action_v1", "model": args.model, "retrieval_top_k": args.top_k, "run_id": args.run_id, "split": f"frozen_validation_{len(rows)}", "run_at_utc": datetime.now(timezone.utc).isoformat(), "case_count": len(rows),
               "selection_json_valid_rate": sum(r["selection"]["parse_error"] is None for r in rows) / len(rows), "selection_contract_valid_rate": sum(not r["selection"]["validation_errors"] for r in rows) / len(rows),
               "action_json_valid_rate": sum(r["action"]["parse_error"] is None for r in rows) / len(rows), "action_contract_valid_rate": sum(not r["action"]["validation_errors"] for r in rows) / len(rows),
               "action_accuracy": sum(r["action_prediction"].get("action_id") == r["gold_action_id"] for r in rows) / len(rows), "action_macro_f1": macro, "action_per_class": per_action,
               "selection_error_counts": dict(Counter(e for r in rows for e in r["selection"]["validation_errors"])), "action_error_counts": dict(Counter(e for r in rows for e in r["action"]["validation_errors"])), "usage": {"selection": usage(rows, "selection"), "action": usage(rows, "action")}, "semantic_metrics": semantic["totals"]}
    metrics.update(strict_evidence_metrics(rows, args.top_k, all_targets))
    # Match B1 zero-shot layout.  `run_id` remains in JSON/CSV for audit, but
    # the one official zero-shot result for a model/K lives directly at Top-K.
    out = HERE / "notrain" / args.model / f"top_k_{args.top_k:02d}"
    write_jsonl(out / "validation_predictions.jsonl", rows)
    (out / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "b2_semantic_metrics.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_b2_csv(out, metrics, semantic)
    write_b2_stage_summary(HERE / "notrain")
    print(json.dumps({key: metrics[key] for key in ("case_count", "selection_contract_valid_rate", "action_contract_valid_rate", "action_accuracy", "action_macro_f1", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

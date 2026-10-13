#!/usr/bin/env python3
"""Shared B2 fixed-example runner for stage-isolated few-shot ablations."""
from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
B2_ROOT = HERE
sys.path.insert(0, str(B2_ROOT))

from run_b2_qwen import (  # noqa: E402
    ACTIONS, B1_DATA, DEFAULT_BASE_URL, DEFAULT_KEY_FILE, DEFAULT_MODEL, NEUTRON_ROOT,
    action_errors, action_metrics, call_qwen, load_cards, load_key, parse_json,
    read_jsonl, selection_errors, strict_evidence_metrics, usage, write_b2_csv,
    write_jsonl,
)
from semantic_metrics import evaluate_b0_semantics, load_units  # noqa: E402
from result_csv import write_csv  # noqa: E402


def model_case(case: dict) -> dict:
    return {"precheck_input": case["precheck_input"]}


def selector_messages(case: dict, catalogue: list[dict], actions: list[dict], top_k: int, examples: list[dict] | None) -> list[dict]:
    system = (
        "You are an evidence selector for neutron-current anomaly precheck. "
        "Select evidence that can support why a human should prioritize one of "
        "the supplied fixed precheck actions, without diagnosing a fault or "
        "confirming a cause. Use evidence text and reviewed metadata. "
        "Use only IDs in the supplied library. Return JSON only: "
        '{"selected_evidence_ids":["..."],"selection_boundary_note":"..."}. '
        f"Select exactly {top_k} distinct IDs. Do not output an action or a diagnosis."
    )
    payload = {"action_definitions": actions, "evidence_library": catalogue, "case_to_select": model_case(case)}
    if examples is not None:
        payload["fixed_complete_golden_examples"] = examples
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def action_messages(case: dict, selected: list[dict], actions: list[dict], contract: dict, examples: list[dict] | None) -> list[dict]:
    system = (
        "You are a neutron-current anomaly precheck assistant. Read the event "
        "combination and only the supplied current-case evidence cards. Select exactly "
        "one fixed precheck action. Do not diagnose a root cause, confirm a fault, "
        "assert a causal relationship, or confirm that any operation occurred. "
        "Return JSON only with exactly action_id and boundary_note."
    )
    payload = {"action_definitions": actions, "output_contract": contract,
               "case_to_predict": {"event_combination": model_case(case), "selected_evidence": selected}}
    if examples is not None:
        payload["fixed_complete_golden_examples"] = examples
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_examples(examples: list[dict], expected_n: int) -> None:
    if len(examples) != expected_n:
        raise ValueError("Example count does not match --n")
    for example in examples:
        if set(example) != {"example_index", "event_combination", "human_evidence_core", "correct_output"}:
            raise ValueError("B2 model-visible examples must use the fixed complete-golden schema")
        if len(example["human_evidence_core"]) != 3:
            raise ValueError("Each B2 complete-golden example must contain three evidence cards")
        if example["correct_output"].get("action_id") not in ACTIONS:
            raise ValueError("Example has an invalid fixed action")
    serialized = json.dumps(examples, ensure_ascii=False)
    forbidden = ("goldcard_id", "gold_action", "gold_evidence", "validation_gold")
    leaked = [field for field in forbidden if field in serialized]
    if leaked:
        raise RuntimeError(f"Model-visible B2 examples contain forbidden fields: {leaked}")


def write_stage_summary(stage_dir: Path) -> None:
    rows = []
    for path in sorted(stage_dir.rglob("validation_metrics.json")):
        metrics = json.loads(path.read_text(encoding="utf-8"))
        if not metrics.get("experiment_id", "").startswith("B2_llm_full_library_selection_then_action_fixed_examples_"):
            continue
        select, action = metrics["usage"]["selection"], metrics["usage"]["action"]
        rows.append({"model": metrics["model"], "retrieval_top_k": metrics["retrieval_top_k"], "fixed_example_count": metrics["fixed_example_count"], "pool_id": metrics["pool_id"], "run_id": metrics["run_id"], "case_count": metrics["case_count"], "selection_contract_valid_rate": metrics["selection_contract_valid_rate"], "action_contract_valid_rate": metrics["action_contract_valid_rate"], "action_accuracy": metrics["action_accuracy"], "action_macro_f1": metrics["action_macro_f1"], "selection_total_tokens": select["total_tokens"], "action_total_tokens": action["total_tokens"], "combined_total_tokens": select["total_tokens"] + action["total_tokens"], "result_directory": str(path.parent.relative_to(stage_dir))})
    write_csv(stage_dir / "summary_metrics.csv", rows, ["model", "retrieval_top_k", "fixed_example_count", "pool_id", "run_id", "case_count", "selection_contract_valid_rate", "action_contract_valid_rate", "action_accuracy", "action_macro_f1", "selection_total_tokens", "action_total_tokens", "combined_total_tokens", "result_directory"])


def main(mode: str) -> None:
    if mode not in {"selector", "action", "both"}:
        raise ValueError("mode must be selector, action, or both")
    parser = ArgumentParser(description=f"B2 fixed complete-golden examples: {mode}")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--pool-id", required=True)
    parser.add_argument("--examples-file", type=Path, required=True)
    parser.add_argument("--run-id", help="Fresh independent end-to-end run identifier")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.top_k < 1 or args.top_k > 300 or args.n < 1:
        raise ValueError("--top-k must be 1..300 and --n must be positive")
    if not args.run_id and not args.validate_only:
        parser.error("--run-id is required unless --validate-only is used")

    examples = read_jsonl(args.examples_file)
    inputs = read_jsonl(B1_DATA / "candidate_packages" / f"top_k_{args.top_k:02d}" / "validation_inputs.jsonl")
    validate_examples(examples, args.n)
    labels = {row["goldcard_id"]: row["target"] for row in read_jsonl(B1_DATA / "labels" / "validation_gold_labels.jsonl")}
    all_targets = {row["goldcard_id"]: row["target"] for path in (B1_DATA / "labels" / "train_gold_targets.jsonl", B1_DATA / "labels" / "validation_gold_labels.jsonl") for row in read_jsonl(path)}
    actions = json.loads((B1_DATA / "action_definitions.json").read_text(encoding="utf-8"))
    contract = json.loads((B1_DATA / "output_contract.json").read_text(encoding="utf-8"))
    catalogue = load_cards()
    cards_by_id = {card["evidence_id"]: card for card in catalogue}
    selector_examples = examples if mode in {"selector", "both"} else None
    action_examples = examples if mode in {"action", "both"} else None
    prompt_a = json.dumps(selector_messages(inputs[0], catalogue, actions, args.top_k, selector_examples), ensure_ascii=False)
    prompt_b = json.dumps(action_messages(inputs[0], catalogue[:args.top_k], actions, contract, action_examples), ensure_ascii=False)
    forbidden = ("goldcard_id", "gold_action", "gold_evidence", "validation_gold")
    leaked = {"selector": [x for x in forbidden if x in prompt_a], "action": [x for x in forbidden if x in prompt_b]}
    if any(leaked.values()):
        raise RuntimeError(f"B2 {mode} prompt contains forbidden fields: {leaked}")
    if args.validate_only:
        print(json.dumps({"mode": mode, "validation_case_count": len(inputs), "card_count": len(catalogue), "top_k": args.top_k, "example_count": len(examples), "examples_in_selector": selector_examples is not None, "examples_in_action": action_examples is not None, "forbidden_prompt_fields": leaked}, ensure_ascii=False))
        return

    key = load_key(args.key_file)
    inputs = inputs[:args.limit] if args.limit else inputs
    rows = []
    for index, case in enumerate(inputs, 1):
        print(f"[{index}/{len(inputs)}] {case['goldcard_id']}", flush=True)
        try:
            select_raw, select_api = call_qwen(selector_messages(case, catalogue, actions, args.top_k, selector_examples), key, args.base_url, args.model)
            selection, select_parse_error = parse_json(select_api["content"])
            select_errors = selection_errors(selection, set(cards_by_id), args.top_k)
        except Exception as exc:
            select_raw, select_api, selection, select_parse_error, select_errors = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}, {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        selected = [cards_by_id[item] for item in selection.get("selected_evidence_ids", []) if item in cards_by_id]
        try:
            action_raw, action_api = call_qwen(action_messages(case, selected, actions, contract, action_examples), key, args.base_url, args.model)
            action, action_parse_error = parse_json(action_api["content"])
            act_errors = action_errors(action)
        except Exception as exc:
            action_raw, action_api, action, action_parse_error, act_errors = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}, {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        rows.append({"goldcard_id": case["goldcard_id"], "run_id": args.run_id, "retrieval_top_k": args.top_k, "pool_id": args.pool_id,
                     "selection": {"prediction": selection or {}, "parse_error": select_parse_error, "validation_errors": select_errors, "api": select_api, "raw_response": select_raw}, "selected_evidence": selected,
                     "action": {"prediction": action or {}, "parse_error": action_parse_error, "validation_errors": act_errors, "api": action_api, "raw_response": action_raw}, "action_prediction": action or {}, "gold_action_id": labels[case["goldcard_id"]]["action_id"], "gold_evidence_ids": labels[case["goldcard_id"]]["action_evidence_ids"]})

    per_action, macro = action_metrics(rows)
    semantic_rows = [{"goldcard_id": r["goldcard_id"], "retrieved_evidence": [{"evidence_id": c["evidence_id"], "rank": i + 1} for i, c in enumerate(r["selected_evidence"])], "predicted_action_id": r["action_prediction"].get("action_id"), "gold_action_id": r["gold_action_id"]} for r in rows]
    semantic = evaluate_b0_semantics(semantic_rows, {r["goldcard_id"]: r["gold_evidence_ids"] for r in rows}, load_units(NEUTRON_ROOT / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"))
    metrics = {"experiment_id": f"B2_llm_full_library_selection_then_action_fixed_examples_{mode}_v1", "model": args.model, "retrieval_top_k": args.top_k, "run_id": args.run_id, "pool_id": args.pool_id, "fixed_example_count": len(examples), "fixed_example_mode": mode, "split": f"frozen_validation_{len(rows)}", "run_at_utc": datetime.now(timezone.utc).isoformat(), "case_count": len(rows), "selection_json_valid_rate": sum(r["selection"]["parse_error"] is None for r in rows) / len(rows), "selection_contract_valid_rate": sum(not r["selection"]["validation_errors"] for r in rows) / len(rows), "action_json_valid_rate": sum(r["action"]["parse_error"] is None for r in rows) / len(rows), "action_contract_valid_rate": sum(not r["action"]["validation_errors"] for r in rows) / len(rows), "action_accuracy": sum(r["action_prediction"].get("action_id") == r["gold_action_id"] for r in rows) / len(rows), "action_macro_f1": macro, "action_per_class": per_action, "selection_error_counts": dict(Counter(e for r in rows for e in r["selection"]["validation_errors"])), "action_error_counts": dict(Counter(e for r in rows for e in r["action"]["validation_errors"])), "usage": {"selection": usage(rows, "selection"), "action": usage(rows, "action")}, "semantic_metrics": semantic["totals"]}
    metrics.update(strict_evidence_metrics(rows, args.top_k, all_targets))
    output = HERE / f"with_training_{mode}" / args.model / f"top_k_{args.top_k:02d}" / f"n_{len(examples):02d}" / f"pool_{args.pool_id}"
    write_jsonl(output / "validation_predictions.jsonl", rows)
    (output / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "b2_semantic_metrics.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_b2_csv(output, metrics, semantic)
    write_stage_summary(HERE / f"with_training_{mode}")
    (output / "README.md").write_text(f"# B2 {mode}\\n\\nFixed complete-golden examples: {len(examples)}; Top-K: {args.top_k}; pool: {args.pool_id}. Each evaluation case selects evidence afresh before its action call.\\n", encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("case_count", "selection_contract_valid_rate", "action_contract_valid_rate", "action_accuracy", "action_macro_f1", "usage")}, ensure_ascii=False))

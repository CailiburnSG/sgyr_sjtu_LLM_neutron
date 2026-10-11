#!/usr/bin/env python3
"""Run B1 with frozen training examples as in-context demonstrations.

This is not parameter fine-tuning.  It reuses the zero-shot runner's API,
validation split, output contract, metrics and same-package B0 comparison.
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
NO_TRAINING_ROOT = B1_ROOT / "no_training_examples"
DATA = B1_ROOT / "data"
sys.path.insert(0, str(NO_TRAINING_ROOT))

from run_no_training_qwen import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_KEY_FILE,
    DEFAULT_MODEL,
    call_qwen,
    evaluate,
    load_key,
    parse_json,
    read_jsonl,
    validate_prediction,
    write_b0_b1_comparison,
    write_b1_csv,
    write_b1_semantic_csv,
    write_b1_stage_summary,
    write_jsonl,
)
from semantic_metrics import evaluate_b0_semantics, load_units  # noqa: E402


def prompt_for_fixed_examples(
    case: dict,
    actions: list[dict],
    contract: dict,
    base_template: str,
    addendum: str,
    examples: list[dict],
) -> list[dict]:
    # The numerical goldcard IDs are bookkeeping keys only.  In this dataset
    # their ranges correlate with the action class, so exposing them would let
    # a few-shot prompt learn an invalid shortcut.
    model_case = {key: value for key, value in case.items() if key != "goldcard_id"}
    return [
        {"role": "system", "content": base_template + "\n\n" + addendum},
        {"role": "user", "content": json.dumps({
            "action_definitions": actions,
            "output_contract": contract,
            "fixed_training_examples": examples,
            "case_to_predict": model_case,
        }, ensure_ascii=False)},
    ]


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--examples-file", type=Path, required=True, help="Frozen ID-free example-pool JSONL")
    parser.add_argument("--pool-id", default="ad_hoc", help="Frozen example-pool identifier recorded with results")
    parser.add_argument("--selection-mode", default="fixed_examples", help="Example selection rule recorded with results")
    parser.add_argument("--limit", type=int, default=0, help="0 means all frozen validation cases")
    args = parser.parse_args()
    examples = read_jsonl(args.examples_file)
    if not examples:
        raise ValueError("No fixed training examples found")
    example_ks = {row["case"].get("retrieval_top_k") for row in examples}
    if example_ks != {args.top_k}:
        raise ValueError(f"Example package K={sorted(example_ks)} does not match requested top_k={args.top_k}")

    candidate_dir = DATA / "candidate_packages" / f"top_k_{args.top_k:02d}"
    inputs = read_jsonl(candidate_dir / "validation_inputs.jsonl")
    if any(len(case.get("bm25_candidates", [])) != args.top_k for case in inputs):
        raise ValueError("Frozen validation candidate count does not match --top-k")
    labels = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "validation_gold_labels.jsonl")}
    actions = json.loads((DATA / "action_definitions.json").read_text(encoding="utf-8"))
    contract = json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))
    base_template = (DATA / "prompt_template.md").read_text(encoding="utf-8")
    addendum = (HERE / "prompt_addendum.md").read_text(encoding="utf-8")
    key = load_key(args.key_file)
    inputs = inputs[:args.limit] if args.limit else inputs

    rows = []
    for index, case in enumerate(inputs, 1):
        print(f"[{index}/{len(inputs)}] {case['goldcard_id']}", flush=True)
        try:
            raw, api = call_qwen(prompt_for_fixed_examples(case, actions, contract, base_template, addendum, examples), key, args.base_url, args.model)
            prediction, parse_error = parse_json(api["content"])
            errors = validate_prediction(prediction, contract)
        except Exception as exc:
            raw, api = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}
            prediction, parse_error, errors = {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        rows.append({
            "goldcard_id": case["goldcard_id"], "retrieval_top_k": args.top_k,
            "prediction": prediction or {}, "parse_error": parse_error, "validation_errors": errors,
            "gold": {"action_id": labels[case["goldcard_id"]]["action_id"]},
            "api": api, "raw_response": raw,
        })

    result_dir = HERE / args.model / f"top_k_{args.top_k:02d}" / f"n_{len(examples):02d}" / f"pool_{args.pool_id}"
    write_jsonl(result_dir / "validation_predictions.jsonl", rows)
    metrics = evaluate(rows, {
        "model": args.model,
        "base_url": args.base_url,
        "retrieval_top_k": args.top_k,
        "split": f"frozen_validation_20_fixed_examples_{len(examples)}",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    metrics["experiment_id"] = "B1_bm25_topk_fixed_examples_llm_action_v1"
    metrics["fixed_example_count"] = len(examples)
    metrics["example_pool_id"] = args.pool_id
    metrics["selection_mode"] = args.selection_mode
    metrics["example_pool_file"] = str(args.examples_file.resolve().relative_to(HERE.resolve()))
    (result_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_b1_csv(result_dir, rows, metrics)
    input_by_case = {case["goldcard_id"]: case for case in inputs}
    gold_evidence_by_case = {case_id: target["action_evidence_ids"] for case_id, target in labels.items()}
    semantic_rows = [{
        "goldcard_id": row["goldcard_id"],
        "retrieved_evidence": input_by_case[row["goldcard_id"]]["bm25_candidates"],
        "predicted_action_id": row["prediction"].get("action_id"),
        "gold_action_id": row["gold"]["action_id"],
    } for row in rows]
    semantic_map = B1_ROOT.parents[2] / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"
    semantic = evaluate_b0_semantics(semantic_rows, gold_evidence_by_case, load_units(semantic_map))
    write_b1_semantic_csv(result_dir, metrics, semantic)
    write_b0_b1_comparison(result_dir, rows, candidate_dir, metrics, semantic, variant_label=f"fixed_examples_{len(examples)}")
    write_b1_stage_summary(HERE)
    (result_dir / "README.md").write_text(
        f"# B1 {args.model} Top-{args.top_k}：固定 {len(examples)} 个训练示例，池 {args.pool_id}\n\n"
        "这是一项固定示例上下文（few-shot）实验，不更新模型参数。训练示例池在 `example_pools/`；"
        "验证逐例输出在 `validation_predictions.jsonl`，聚合指标在 CSV/JSON 文件中。\n",
        encoding="utf-8",
    )
    print(json.dumps({key: metrics[key] for key in ("case_count", "json_valid_rate", "constraint_valid_rate", "action_accuracy", "action_macro_f1", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Materialize ID-free complete-golden few-shot examples for B2.

The frozen B1 pool manifest is used only outside prompts to select training
case IDs.  The JSONL written here deliberately contains no ``goldcard_id``:
each model-visible example is event combination + three reviewed human gold
evidence cards + the fixed action contract output.
"""
from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
B2_ROOT = HERE
B1_POOL_ROOT = B2_ROOT.parent / "B1" / "with_training_examples" / "example_pools"
B1_DATA = B2_ROOT.parent / "B1" / "data"
sys.path.insert(0, str(B2_ROOT))

from run_b2_qwen import load_cards, read_jsonl, write_jsonl  # noqa: E402


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-k", type=int, default=5, help="B1 pool family used only to obtain frozen case IDs")
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--pool-id", required=True, help="For example: 01")
    args = parser.parse_args()
    if args.top_k < 1 or args.n < 1:
        raise ValueError("--top-k and --n must be positive")

    source = B1_POOL_ROOT / f"top_k_{args.top_k:02d}" / f"n_{args.n:02d}" / f"pool_{args.pool_id}.manifest.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    case_ids = manifest.get("goldcard_ids_model_external_only", [])
    if len(case_ids) != args.n or len(case_ids) != len(set(case_ids)):
        raise ValueError("Frozen B1 manifest does not contain exactly n unique external training IDs")

    train_cases = {row["goldcard_id"]: row for row in read_jsonl(B1_DATA / "candidate_packages" / f"top_k_{args.top_k:02d}" / "train_inputs.jsonl")}
    targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(B1_DATA / "labels" / "train_gold_targets.jsonl")}
    cards_by_id = {card["evidence_id"]: card for card in load_cards()}
    examples = []
    for index, case_id in enumerate(case_ids, 1):
        case, target = train_cases.get(case_id), targets.get(case_id)
        if case is None or target is None:
            raise ValueError("Frozen B1 example ID is missing from B2 train materials")
        evidence_ids = target.get("action_evidence_ids", [])
        if len(evidence_ids) != 3 or not set(evidence_ids).issubset(cards_by_id):
            raise ValueError("A B2 full-golden example must have exactly three reviewed evidence cards")
        examples.append({
            "example_index": index,
            "event_combination": {"precheck_input": case["precheck_input"]},
            "human_evidence_core": [cards_by_id[evidence_id] for evidence_id in evidence_ids],
            "correct_output": {"action_id": target["action_id"], "boundary_note": target["boundary_note"]},
        })

    serialized = json.dumps(examples, ensure_ascii=False)
    forbidden = ("goldcard_id", "gold_action", "gold_evidence", "validation_gold")
    leaked = [field for field in forbidden if field in serialized]
    if leaked:
        raise RuntimeError(f"Model-visible B2 examples contain forbidden fields: {leaked}")

    output_dir = HERE / "training_example_pools" / f"top_k_{args.top_k:02d}" / f"n_{args.n:02d}"
    write_jsonl(output_dir / f"pool_{args.pool_id}.jsonl", examples)
    audit_manifest = {
        "pool_id": args.pool_id,
        "example_count": len(examples),
        "source_b1_manifest": str(source.relative_to(B2_ROOT.parent)),
        "source_case_ids_model_external_only": case_ids,
        "model_visible_example_fields": ["example_index", "event_combination", "human_evidence_core", "correct_output"],
        "forbidden_model_prompt_fields": leaked,
        "selection_rule": "Reuse B1 frozen training-case IDs, then materialize each complete golden case as event + 3 reviewed human evidence cards + fixed action output."
    }
    (output_dir / f"pool_{args.pool_id}.manifest.json").write_text(json.dumps(audit_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_dir / f"pool_{args.pool_id}.jsonl"), "example_count": len(examples), "forbidden_prompt_fields": leaked}, ensure_ascii=False))


if __name__ == "__main__":
    main()

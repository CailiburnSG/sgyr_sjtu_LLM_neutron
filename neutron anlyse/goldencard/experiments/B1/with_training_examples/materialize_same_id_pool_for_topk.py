#!/usr/bin/env python3
"""Rebuild frozen few-shot pools with a different BM25 Top-K package.

Case IDs, targets, pool membership and row ordering are copied from a frozen
source pool.  Only ``bm25_candidates`` changes, allowing a controlled Top-K
comparison for the same demonstration sets.
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--source-top-k", type=int, default=10)
    parser.add_argument("--target-top-k", type=int, required=True)
    parser.add_argument("--example-count", type=int, required=True)
    args = parser.parse_args()
    source_root = HERE / "example_pools" / f"top_k_{args.source_top_k:02d}" / f"n_{args.example_count:02d}"
    output_root = HERE / "example_pools" / f"top_k_{args.target_top_k:02d}" / f"n_{args.example_count:02d}"
    inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / f"top_k_{args.target_top_k:02d}" / "train_inputs.jsonl")}
    targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    validation_ids = {row["goldcard_id"] for row in read_jsonl(DATA / "candidate_packages" / f"top_k_{args.target_top_k:02d}" / "validation_inputs.jsonl")}
    manifests = sorted(source_root.glob("pool_*.manifest.json"))
    if not manifests:
        raise FileNotFoundError(f"No source manifests at {source_root}")

    for manifest_path in manifests:
        source = json.loads(manifest_path.read_text(encoding="utf-8"))
        pool_id = source["pool_id"]
        case_ids = source["goldcard_ids_model_external_only"]
        if len(case_ids) != args.example_count or set(case_ids) & validation_ids or not set(case_ids) <= set(inputs):
            raise ValueError(f"Invalid source IDs for pool {pool_id}")
        rows = []
        for index, case_id in enumerate(case_ids, 1):
            model_case = {key: value for key, value in inputs[case_id].items() if key != "goldcard_id"}
            if model_case["retrieval_top_k"] != args.target_top_k or len(model_case["bm25_candidates"]) != args.target_top_k:
                raise ValueError(f"Candidate package mismatch for {case_id}")
            rows.append({"example_index": index, "case": model_case, "correct_output": {
                "action_id": targets[case_id]["action_id"], "boundary_note": targets[case_id]["boundary_note"]}})
        write_jsonl(output_root / f"pool_{pool_id}.jsonl", rows)
        action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": f"same_case_ids_as_top_k_{args.source_top_k:02d}_n_{args.example_count:02d}_v1",
            "retrieval_top_k": args.target_top_k,
            "example_count": args.example_count,
            "action_counts": action_counts,
            "source_pool": str(manifest_path.relative_to(HERE / "example_pools")),
            "goldcard_ids_model_external_only": case_ids,
            "selection_rule": f"Reuse exactly the frozen n{args.example_count:02d} training-case IDs and targets from Top-{args.source_top_k}; replace only candidate packages with frozen BM25 Top-{args.target_top_k} versions. No validation case or goldcard_id enters the model prompt.",
        }
        (output_root / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "ids": case_ids, "actions": action_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

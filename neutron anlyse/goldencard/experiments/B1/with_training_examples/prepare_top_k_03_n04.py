#!/usr/bin/env python3
"""Materialize Top-3 versions of the already frozen Top-10 n04 pools.

The training-case IDs and correct outputs are unchanged.  Only each example's
BM25 candidate package changes from Top-10 to Top-3, isolating retrieval K.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
SOURCE_ROOT = HERE / "example_pools" / "top_k_10" / "n_04"
OUTPUT_ROOT = HERE / "example_pools" / "top_k_03" / "n_04"
ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / "top_k_03" / "train_inputs.jsonl")}
    targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    validation_ids = {row["goldcard_id"] for row in read_jsonl(DATA / "candidate_packages" / "top_k_03" / "validation_inputs.jsonl")}

    for manifest_path in sorted(SOURCE_ROOT.glob("pool_*.manifest.json")):
        source = json.loads(manifest_path.read_text(encoding="utf-8"))
        pool_id = source["pool_id"]
        case_ids = source["goldcard_ids_model_external_only"]
        if len(case_ids) != 4 or set(case_ids) & validation_ids or not set(case_ids) <= set(inputs):
            raise ValueError(f"Invalid frozen n04 IDs for pool {pool_id}")
        rows = []
        for index, case_id in enumerate(case_ids, 1):
            model_case = {key: value for key, value in inputs[case_id].items() if key != "goldcard_id"}
            if len(model_case["bm25_candidates"]) != 3:
                raise ValueError(f"Top-3 package missing for {case_id}")
            rows.append({
                "example_index": index,
                "case": model_case,
                "correct_output": {
                    "action_id": targets[case_id]["action_id"],
                    "boundary_note": targets[case_id]["boundary_note"],
                },
            })
        action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
        if action_counts != Counter({action: 1 for action in ACTIONS}):
            raise ValueError(f"Action balance failure for pool {pool_id}: {action_counts}")
        write_jsonl(OUTPUT_ROOT / f"pool_{pool_id}.jsonl", rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "same_case_ids_as_top_k_10_n04_v1",
            "retrieval_top_k": 3,
            "example_count": 4,
            "per_action_count": 1,
            "source_pool": "top_k_10/n_04/" + manifest_path.name,
            "goldcard_ids_model_external_only": case_ids,
            "selection_rule": "Reuse exactly the frozen n04 training-case IDs and targets from Top-10; replace only candidate packages with their frozen BM25 Top-3 versions. No validation case or goldcard_id enters the model prompt.",
        }
        (OUTPUT_ROOT / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "ids": case_ids, "actions": action_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extend n24 to n28 using the final balanced cyclic reuse of training cases.

Every n24 pool contains its own n20 additions and the next pool's additions.
The only balanced four-case quartet not already in each pool is therefore the
third n20-addition quartet.  Adding it yields 28 distinct examples within each
pool (seven per action and event-group size), but each of those twelve cases
now appears in all three n28 pools.  This is a context-size continuation, not
an independent-pool experiment.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
GOLD = B1_ROOT.parents[1] / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
ROOT = HERE / "example_pools" / "top_k_10"
ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])
SOURCE_POOL = {"01": "03", "02": "01", "03": "02"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    train_inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / "top_k_10" / "train_inputs.jsonl")}
    targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    event_sizes = {row["goldcard_id"]: len(row["trace"]["source_event_ids"]) for row in read_jsonl(GOLD)}
    output = ROOT / "n_28"

    for pool_id, source_pool in SOURCE_POOL.items():
        parent_rows = read_jsonl(ROOT / "n_24" / f"pool_{pool_id}.jsonl")
        parent_manifest = json.loads((ROOT / "n_24" / f"pool_{pool_id}.manifest.json").read_text(encoding="utf-8"))
        source_n20_manifest = json.loads((ROOT / "n_20" / f"pool_{source_pool}.manifest.json").read_text(encoding="utf-8"))
        new_ids = source_n20_manifest["added_goldcard_ids_model_external_only"]
        existing_ids = set(parent_manifest["goldcard_ids_model_external_only"])
        if len(new_ids) != 4 or set(new_ids) & existing_ids:
            raise ValueError(f"Invalid n28 cyclic reuse for pool {pool_id}: {new_ids}")
        rows = parent_rows + [
            {"case": {key: value for key, value in train_inputs[case_id].items() if key != "goldcard_id"},
             "correct_output": {"action_id": targets[case_id]["action_id"], "boundary_note": targets[case_id]["boundary_note"]}}
            for case_id in new_ids
        ]
        for index, row in enumerate(rows, 1):
            row["example_index"] = index
        all_ids = parent_manifest["goldcard_ids_model_external_only"] + new_ids
        action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
        size_counts = Counter(event_sizes[case_id] for case_id in all_ids)
        if action_counts != Counter({action: 7 for action in ACTIONS}) or size_counts != Counter({size: 7 for size in range(1, 5)}):
            raise ValueError(f"n28 balance failure: actions={action_counts}, sizes={size_counts}")
        write_jsonl(output / f"pool_{pool_id}.jsonl", rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "nested_full_cyclic_reuse_extension_of_n24_v1",
            "retrieval_top_k": 10,
            "example_count": 28,
            "per_action_count": 7,
            "parent_pool": f"n_24/pool_{pool_id}",
            "reuse_source_pool": f"n_20/pool_{source_pool}",
            "reused_goldcard_ids_model_external_only": new_ids,
            "goldcard_ids_model_external_only": all_ids,
            "selection_rule": "Preserve n24 and append the remaining n20-addition quartet (03→01, 01→02, 02→03). This gives each pool 28 distinct examples; the twelve cyclic-addition cases now occur in all three pools. All model inputs remain without goldcard_id.",
        }
        (output / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "reused_from": source_pool, "added": new_ids, "actions": action_counts, "sizes": size_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

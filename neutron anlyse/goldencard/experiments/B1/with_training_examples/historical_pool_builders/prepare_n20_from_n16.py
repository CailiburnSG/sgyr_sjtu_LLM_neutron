#!/usr/bin/env python3
"""Exhaustively extend the three n16 pools to balanced n20 pools.

Across the three pools this consumes the final twelve unused training cases,
so n20 is the largest three-pool configuration with no case overlap.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
GOLD = B1_ROOT.parents[1] / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
ROOT = HERE / "example_pools" / "top_k_10"
ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])

# The only remaining cases after n16 can be partitioned as follows.  Each
# column adds all four event-group sizes once, while each action uses all three
# of its remaining cases exactly once across the three pools.
ADDITIONS = {
    "01": {ACTIONS[0]: 2, ACTIONS[1]: 3, ACTIONS[2]: 1, ACTIONS[3]: 4},
    "02": {ACTIONS[0]: 3, ACTIONS[1]: 4, ACTIONS[2]: 2, ACTIONS[3]: 1},
    "03": {ACTIONS[0]: 4, ACTIONS[1]: 1, ACTIONS[2]: 3, ACTIONS[3]: 2},
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    train_inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / "top_k_10" / "train_inputs.jsonl")}
    targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    event_sizes = {row["goldcard_id"]: len(row["trace"]["source_event_ids"]) for row in read_jsonl(GOLD)}
    candidates: dict[tuple[str, int], list[str]] = defaultdict(list)
    for case_id, target in targets.items():
        candidates[(target["action_id"], event_sizes[case_id])].append(case_id)
    for values in candidates.values():
        values.sort()

    parent_manifests = {}
    used = set()
    for pool_id in ADDITIONS:
        manifest = json.loads((ROOT / "n_16" / f"pool_{pool_id}.manifest.json").read_text(encoding="utf-8"))
        parent_manifests[pool_id] = manifest
        used.update(manifest["goldcard_ids_model_external_only"])
    remaining = set(train_inputs) - used
    if len(remaining) != 12:
        raise ValueError(f"Expected 12 unused training cases after n16, found {len(remaining)}")

    consumed = set()
    for pool_id, size_by_action in ADDITIONS.items():
        parent_rows = read_jsonl(ROOT / "n_16" / f"pool_{pool_id}.jsonl")
        parent_manifest = parent_manifests[pool_id]
        new_ids = []
        for action in ACTIONS:
            size = size_by_action[action]
            matches = [case_id for case_id in candidates[(action, size)] if case_id in remaining and case_id not in consumed]
            if len(matches) != 1:
                raise ValueError(f"Expected one remaining case for {action}, size {size}, pool {pool_id}; got {matches}")
            new_ids.append(matches[0])
            consumed.add(matches[0])
        added_rows = []
        for case_id in new_ids:
            target = targets[case_id]
            model_case = {key: value for key, value in train_inputs[case_id].items() if key != "goldcard_id"}
            added_rows.append({"case": model_case, "correct_output": {"action_id": target["action_id"], "boundary_note": target["boundary_note"]}})
        rows = parent_rows + added_rows
        for index, row in enumerate(rows, 1):
            row["example_index"] = index
        action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
        all_ids = parent_manifest["goldcard_ids_model_external_only"] + new_ids
        size_counts = Counter(event_sizes[case_id] for case_id in all_ids)
        if action_counts != Counter({action: 5 for action in ACTIONS}) or size_counts != Counter({size: 5 for size in range(1, 5)}):
            raise ValueError(f"n20 balance failure: actions={action_counts}, sizes={size_counts}")
        output = ROOT / "n_20"
        write_jsonl(output / f"pool_{pool_id}.jsonl", rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "nested_exhaustive_extension_of_n16_v1",
            "retrieval_top_k": 10,
            "example_count": 20,
            "per_action_count": 5,
            "parent_pool": f"n_16/pool_{pool_id}",
            "added_action_event_sizes": size_by_action,
            "added_goldcard_ids_model_external_only": new_ids,
            "goldcard_ids_model_external_only": all_ids,
            "selection_rule": "Preserve all sixteen examples from the corresponding n16 pool; append the unique remaining training case for each fixed action × event-group-size stratum. Across the three pools, all 60 training cases are used exactly once.",
        }
        (output / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "added": new_ids, "actions": action_counts, "sizes": size_counts}, ensure_ascii=False))
    if consumed != remaining:
        raise ValueError("n20 did not consume exactly the remaining training cases")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extend each formal n08 example pool to a balanced nested n12 pool."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
GOLD = B1_ROOT.parents[1] / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
ROOT = HERE / "example_pools" / "top_k_10"
ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])

# One new action × event-group-size stratum per pool.  The four added sizes are
# always 1, 2, 3, 4, so each n12 pool has three examples of every size overall.
ADDITIONS = {
    "01": {"seed": 20261021, "sizes": {ACTIONS[0]: 3, ACTIONS[1]: 2, ACTIONS[2]: 4, ACTIONS[3]: 1}},
    "02": {"seed": 20261022, "sizes": {ACTIONS[0]: 1, ACTIONS[1]: 3, ACTIONS[2]: 4, ACTIONS[3]: 2}},
    "03": {"seed": 20261023, "sizes": {ACTIONS[0]: 2, ACTIONS[1]: 1, ACTIONS[2]: 4, ACTIONS[3]: 3}},
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

    parent_ids = set()
    parent_manifests = {}
    for pool_id in ADDITIONS:
        manifest = json.loads((ROOT / "n_08" / f"pool_{pool_id}.manifest.json").read_text(encoding="utf-8"))
        parent_manifests[pool_id] = manifest
        parent_ids.update(manifest["goldcard_ids_model_external_only"])
    used = set(parent_ids)

    for pool_id, spec in ADDITIONS.items():
        parent_rows = read_jsonl(ROOT / "n_08" / f"pool_{pool_id}.jsonl")
        parent_manifest = parent_manifests[pool_id]
        rng = random.Random(spec["seed"])
        new_ids = []
        for action in ACTIONS:
            size = spec["sizes"][action]
            available = [case_id for case_id in candidates[(action, size)] if case_id not in used]
            if not available:
                raise ValueError(f"No available addition for pool {pool_id}: {action}, size {size}")
            case_id = rng.choice(available)
            used.add(case_id)
            new_ids.append(case_id)
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
        if action_counts != Counter({action: 3 for action in ACTIONS}) or size_counts != Counter({size: 3 for size in range(1, 5)}):
            raise ValueError(f"n12 balance failure: actions={action_counts}, sizes={size_counts}")
        output = ROOT / "n_12"
        write_jsonl(output / f"pool_{pool_id}.jsonl", rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "nested_stratified_extension_of_n08_v1",
            "seed": spec["seed"],
            "retrieval_top_k": 10,
            "example_count": 12,
            "per_action_count": 3,
            "parent_pool": f"n_08/pool_{pool_id}",
            "added_action_event_sizes": spec["sizes"],
            "added_goldcard_ids_model_external_only": new_ids,
            "goldcard_ids_model_external_only": all_ids,
            "selection_rule": "Preserve all eight examples from the corresponding frozen n08 pool; append one training-only random case for each action within fixed action × event-group-size strata. No validation case or label is included.",
        }
        (output / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "added": new_ids, "actions": action_counts, "sizes": size_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Freeze one-example-per-action pools nested inside the formal n08 pools."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE / "example_pools" / "top_k_10"

# Example indices refer to the ID-free n08 pool JSONL rows.  Each selection has
# one A1, A2, A3 and A4 example; indices were fixed before any n04 call.  They
# also maximize event-group-size diversity within each four-example pool where
# the parent n08 composition permits it.
SELECTED_INDICES = {
    "01": (2, 3, 5, 8),
    "02": (2, 3, 5, 8),
    "03": (2, 4, 5, 7),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    output = ROOT / "n_04"
    for pool_id, indices in SELECTED_INDICES.items():
        parent_rows = read_jsonl(ROOT / "n_08" / f"pool_{pool_id}.jsonl")
        parent_manifest = json.loads((ROOT / "n_08" / f"pool_{pool_id}.manifest.json").read_text(encoding="utf-8"))
        selected = [parent_rows[index - 1] for index in indices]
        for new_index, row in enumerate(selected, 1):
            row["example_index"] = new_index
        actions = Counter(row["correct_output"]["action_id"] for row in selected)
        if len(actions) != 4 or set(actions.values()) != {1}:
            raise ValueError(f"n04 action balance failed for pool {pool_id}: {actions}")
        write_jsonl(output / f"pool_{pool_id}.jsonl", selected)
        source_ids = parent_manifest["goldcard_ids_model_external_only"]
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "nested_stratified_subset_of_n08_v1",
            "retrieval_top_k": 10,
            "example_count": 4,
            "per_action_count": 1,
            "parent_pool": f"n_08/pool_{pool_id}",
            "selected_parent_example_indices": list(indices),
            "goldcard_ids_model_external_only": [source_ids[index - 1] for index in indices],
            "selection_rule": "One fixed example per action, selected as a subset of the corresponding pre-existing n08 pool before any n04 model call; no validation case or label is included.",
        }
        (output / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "actions": actions, "parent_indices": indices}, ensure_ascii=False))


if __name__ == "__main__":
    main()

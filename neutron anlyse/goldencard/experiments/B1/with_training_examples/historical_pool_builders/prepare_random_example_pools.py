#!/usr/bin/env python3
"""Create three ID-free, stratified and frozen Top-10 eight-example pools."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
GOLD = B1_ROOT.parents[1] / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
TOP_K = 10
N_PER_ACTION = 2

ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])

# Every pool has two examples for each action and exactly two examples for
# each event-group size overall.  Seeds and size assignments are fixed before
# any model call.  Sampling never consults evidence overlap or model results.
POOL_SPECS = {
    "01": {"seed": 20261011, "sizes": {ACTIONS[0]: (1, 2), ACTIONS[1]: (3, 4), ACTIONS[2]: (1, 3), ACTIONS[3]: (2, 4)}},
    "02": {"seed": 20261012, "sizes": {ACTIONS[0]: (3, 4), ACTIONS[1]: (1, 2), ACTIONS[2]: (2, 4), ACTIONS[3]: (1, 3)}},
    "03": {"seed": 20261013, "sizes": {ACTIONS[0]: (1, 4), ACTIONS[1]: (2, 3), ACTIONS[2]: (1, 3), ACTIONS[3]: (2, 4)}},
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    train_inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / f"top_k_{TOP_K:02d}" / "train_inputs.jsonl")}
    train_targets = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    event_sizes = {row["goldcard_id"]: len(row["trace"]["source_event_ids"]) for row in read_jsonl(GOLD)}
    candidates: dict[tuple[str, int], list[str]] = defaultdict(list)
    for case_id, target in train_targets.items():
        candidates[(target["action_id"], event_sizes[case_id])].append(case_id)
    for values in candidates.values():
        values.sort()

    output_root = HERE / "example_pools" / f"top_k_{TOP_K:02d}" / f"n_{N_PER_ACTION * len(ACTIONS):02d}"
    used: set[str] = set()
    for pool_id, spec in POOL_SPECS.items():
        rng = random.Random(spec["seed"])
        chosen: list[str] = []
        for action in ACTIONS:
            for event_size in spec["sizes"][action]:
                available = [case_id for case_id in candidates[(action, event_size)] if case_id not in used]
                if not available:
                    raise ValueError(f"No unused training case for {action}, event size {event_size}, pool {pool_id}")
                case_id = rng.choice(available)
                used.add(case_id)
                chosen.append(case_id)
        rows = []
        for index, case_id in enumerate(chosen, 1):
            target = train_targets[case_id]
            model_case = {key: value for key, value in train_inputs[case_id].items() if key != "goldcard_id"}
            rows.append({
                "example_index": index,
                "case": model_case,
                "correct_output": {"action_id": target["action_id"], "boundary_note": target["boundary_note"]},
            })
        action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
        size_counts = Counter(event_sizes[case_id] for case_id in chosen)
        if action_counts != Counter({action: N_PER_ACTION for action in ACTIONS}) or size_counts != Counter({size: 2 for size in range(1, 5)}):
            raise ValueError(f"Pool balance failure: actions={action_counts}, sizes={size_counts}")
        pool_path = output_root / f"pool_{pool_id}.jsonl"
        write_jsonl(pool_path, rows)
        manifest = {
            "pool_id": pool_id,
            "selection_mode": "stratified_random_frozen_v1",
            "seed": spec["seed"],
            "retrieval_top_k": TOP_K,
            "example_count": len(rows),
            "per_action_count": N_PER_ACTION,
            "action_counts": dict(action_counts),
            "event_group_size_counts": dict(size_counts),
            "goldcard_ids_model_external_only": chosen,
            "selection_rule": "Randomly selected from training-only cases within fixed action × event-group-size strata; no evidence-overlap or model-result criterion; no case reused across the three pools.",
        }
        (output_root / f"pool_{pool_id}.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"pool": pool_id, "ids": chosen, "actions": action_counts, "sizes": size_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Freeze balanced few-shot examples without changing model parameters.

The eight examples come only from the 60-case training partition.  They are
stored locally so the run script never needs to read training labels at call
time, and the frozen 20-case validation labels remain isolated.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parents[1]
DATA = B1_ROOT / "data"
TOP_K = 10

# Two examples per fixed action.  They were selected from training cases whose
# Top-10 package contains at least one of their reviewed direct-support cards;
# source-event counts 1 and 3 are both represented in every action.
EXAMPLE_IDS = (
    "GC-B80-003", "GC-B80-012",  # A1
    "GC-B80-022", "GC-B80-032",  # A2
    "GC-B80-042", "GC-B80-054",  # A3
    "GC-B80-065", "GC-B80-072",  # A4
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    inputs = {row["goldcard_id"]: row for row in read_jsonl(DATA / "candidate_packages" / f"top_k_{TOP_K:02d}" / "train_inputs.jsonl")}
    labels = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "train_gold_targets.jsonl")}
    if not set(EXAMPLE_IDS).issubset(inputs) or not set(EXAMPLE_IDS).issubset(labels):
        raise ValueError("Fixed examples must all be drawn from the frozen training split")

    rows = []
    for index, case_id in enumerate(EXAMPLE_IDS, 1):
        target = labels[case_id]
        # Goldcard IDs are retained only in the local manifest.  Their numeric
        # ranges correlate with actions in this constructed dataset, so they
        # must never be included in the text sent to a model.
        model_case = {key: value for key, value in inputs[case_id].items() if key != "goldcard_id"}
        rows.append({
            "example_index": index,
            "case": model_case,
            "correct_output": {
                "action_id": target["action_id"],
                "boundary_note": target["boundary_note"],
            },
        })
    action_counts = Counter(row["correct_output"]["action_id"] for row in rows)
    if len(action_counts) != 4 or sorted(action_counts.values()) != [2, 2, 2, 2]:
        raise ValueError(f"Examples are not action-balanced: {action_counts}")
    output = HERE / "data" / f"fixed_examples_top_k_{TOP_K:02d}.jsonl"
    write_jsonl(output, rows)
    manifest = {
        "variant": "fixed_examples_context_v1",
        "learning_mode": "in_context_examples_only_no_parameter_update",
        "retrieval_top_k": TOP_K,
        "example_count": len(rows),
        "goldcard_ids": list(EXAMPLE_IDS),
        "action_counts": dict(action_counts),
        "selection_rule": "Two training-only examples per action; each selected Top-10 package contains at least one reviewed direct-support card; source-event counts 1 and 3 represented per action.",
        "source_inputs": str((DATA / "candidate_packages" / f"top_k_{TOP_K:02d}" / "train_inputs.jsonl").relative_to(B1_ROOT.parent)),
        "source_labels": str((DATA / "labels" / "train_gold_targets.jsonl").relative_to(B1_ROOT.parent)),
    }
    (HERE / "data" / "fixed_examples_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"examples": len(rows), "actions": action_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

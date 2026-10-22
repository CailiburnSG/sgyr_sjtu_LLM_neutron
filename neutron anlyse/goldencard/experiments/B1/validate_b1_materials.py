#!/usr/bin/env python3
"""Check the frozen B1 package without reading upstream experiment outputs."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path


DATA = Path(__file__).resolve().parent / "data"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = ArgumentParser(description="Validate one or more frozen B1 Top-K input packages")
    parser.add_argument("--top-ks", type=int, nargs="+", default=(3,))
    args = parser.parse_args()
    manifest = json.loads((DATA / "split_manifest.json").read_text(encoding="utf-8"))
    train_ids = set(manifest["train_goldcard_ids"])
    validation_ids = set(manifest["validation_goldcard_ids"])
    assert len(train_ids) == 60 and len(validation_ids) > 0 and not train_ids & validation_ids
    assert set(manifest["train_action_counts"].values()) == {15}
    assert len(set(manifest["validation_action_counts"].values())) == 1
    assert set(manifest["train_event_count_counts"].values()) == {15}
    assert len(set(manifest["validation_event_count_counts"].values())) == 1
    actions = {item["action_id"] for item in json.loads((DATA / "action_definitions.json").read_text(encoding="utf-8"))}
    contract = json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))
    assert actions == set(contract["allowed_action_ids"]) and len(actions) == 4
    assert contract["contract_version"] == "B1-v3-all-topk"
    assert set(contract["output_schema"]) == {"action_id", "boundary_note"}
    for top_k in args.top_ks:
        folder = DATA / "candidate_packages" / f"top_k_{top_k:02d}"
        train_rows = read_jsonl(folder / "train_inputs.jsonl")
        validation_rows = read_jsonl(folder / "validation_inputs.jsonl")
        assert {row["goldcard_id"] for row in train_rows} == train_ids
        assert {row["goldcard_id"] for row in validation_rows} == validation_ids
        for row in train_rows + validation_rows:
            candidates = row["bm25_candidates"]
            assert len(candidates) == top_k
            assert [card["rank"] for card in candidates] == list(range(1, top_k + 1))
            assert all(card["text"] and card["evidence_id"] for card in candidates)
            assert "gold_action" not in row and "evidence_combination" not in row
    for split, ids in (("train", train_ids), ("validation", validation_ids)):
        label_name = "train_gold_targets.jsonl" if split == "train" else "validation_gold_labels.jsonl"
        labels = read_jsonl(DATA / "labels" / label_name)
        assert {row["goldcard_id"] for row in labels} == ids
        for label in labels:
            target = label["target"]
            assert target["action_id"] in actions
            assert len(target["selected_evidence"]) == 3
            assert {item["evidence_id"] for item in target["selected_evidence"]} == set(target["action_evidence_ids"])
    print(f"B1 materials valid: {len(train_ids)} train, {len(validation_ids)} evaluation, Top-K={args.top_ks}, full candidate cards.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build 40 combination-held-out cases using the v1 gold-label rules.

The source event atoms are the same 80 cards used by B80, but every new
``source_event_ids`` combination is absent from B80.  This extends evaluation
coverage at the event-combination level; it does not claim atom-disjointness.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
GOLD80 = HERE.parent / "gold_standard_80_eventgroups"
sys.path.insert(0, str(GOLD80))
import build_balanced_80 as base  # noqa: E402


SOURCE_80 = GOLD80 / "goldcase_balanced_80.jsonl"
OUTPUT_40 = HERE / "goldcase_combination_holdout_40.jsonl"
OUTPUT_120 = HERE / "goldcase_combined_120.jsonl"
OVERVIEW = HERE / "一页总览表.md"

# Every action has ten cases.  Across all actions, each event-combination size
# appears exactly ten times; each action receives either two or three cases of
# a given size, preserving the B80 1--4 event composition logic at smaller n.
SIZE_QUOTAS = {
    base.A1: (3, 3, 2, 2),
    base.A2: (2, 3, 3, 2),
    base.A3: (2, 2, 3, 3),
    base.A4: (3, 2, 2, 3),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def action_of(record: dict) -> str:
    return record["gold_action_links"][0]["action_id"]


def valid_event_sets(pool_a: list[dict], pool_b: list[dict], size: int, singleton_from_a: bool) -> list[tuple[dict, ...]]:
    if size == 1:
        return [(event,) for event in (pool_a if singleton_from_a else pool_b)]
    union = pool_a + pool_b
    a_ids = {event["event_id"] for event in pool_a}
    b_ids = {event["event_id"] for event in pool_b}
    return [choice for choice in combinations(union, size)
            if {event["event_id"] for event in choice} & a_ids and {event["event_id"] for event in choice} & b_ids]


def choose_events(pool_a: list[dict], pool_b: list[dict], size: int, ordinal: int,
                  usage: Counter, forbidden: set[tuple[str, ...]]) -> list[dict]:
    choices = valid_event_sets(pool_a, pool_b, size, singleton_from_a=(ordinal % 2 == 0))
    candidates = [choice for choice in choices if tuple(sorted(event["event_id"] for event in choice)) not in forbidden]
    if not candidates:
        raise ValueError(f"No unseen combination for size {size}")
    # Prefer atoms that have been used least often across B80 plus this holdout.
    # Lexical rotation fixes ties deterministically without looking at evidence
    # retrieval or model results.
    def score(choice: tuple[dict, ...]) -> tuple:
        ids = tuple(sorted(event["event_id"] for event in choice))
        return (sum(usage[event_id] for event_id in ids), max(usage[event_id] for event_id in ids),
                tuple((index - ordinal) % len(candidates) for index, _ in enumerate(ids)))
    selected = min(candidates, key=score)
    for event in selected:
        usage[event["event_id"]] += 1
    return list(selected)


def make_case(case_id: str, action_id: str, events: list[dict], action_ordinal: int,
              global_ordinal: int, evidence: dict[str, dict]) -> dict:
    record = base.make_case(case_id, action_id, events, action_ordinal, evidence)
    record["dataset_status"] = "combination_holdout_v1"
    record["precheck_input"] = base.summarize(events, global_ordinal)
    record["trace"]["event_source"] = "goldencard/event_groups (combination-held-out v1)"
    record["evidence_combination"]["combination_id"] = f"EC-{base.ACTION_CODES[action_id]}-H{action_ordinal + 1:02d}"
    record["annotation_notes"] = [
        "本条沿用 B80 的受控事件—证据—检查行为标注规则，不是故障原因诊断。",
        "每例只保留一个优先检查建议及其直接支持证据。",
        "本条事件原子组合不出现在 B80；事件原子可与 B80 复用。",
    ]
    return record


def write_overview(records: list[dict]) -> None:
    action_counts = Counter(action_of(record) for record in records)
    size_counts = Counter(len(record["trace"]["source_event_ids"]) for record in records)
    lines = ["# 40 例组合留出验证集：一页总览", "",
             "沿用 B80 的四行动、三证据组合和 1--4 事件构造规则；新案例与 B80 不共享完整事件组合。", "",
             "| 案例 | 事件数 | 三证据组合 | 唯一检查建议 |", "| --- | ---: | --- | --- |"]
    for record in records:
        evidence_ids = "<br>".join(f"`{item['evidence_id']}`" for item in record["evidence"])
        lines.append(f"| {record['goldcard_id']} | {len(record['trace']['source_event_ids'])} | {evidence_ids} | {base.ACTION_LABELS[action_of(record)]} |")
    lines += ["", "## 配额检查", "",
              "- " + "；".join(f"{base.ACTION_LABELS[action]} {action_counts[action]} 例" for action in base.ACTION_CODES) + "。",
              "- " + "；".join(f"{size} 事件案例 {size_counts[size]} 例" for size in range(1, 5)) + "。",
              "- 每项行动的 10 种三证据组合各出现 1 次。"]
    OVERVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    old = read_jsonl(SOURCE_80)
    evidence = base.load_evidence()
    old_combinations = {tuple(sorted(record["trace"]["source_event_ids"])) for record in old}
    forbidden = set(old_combinations)
    records: list[dict] = []
    global_ordinal = 0

    pools = {action: (json.loads((base.GROUP_DIR / file_a).read_text(encoding="utf-8")),
                      json.loads((base.GROUP_DIR / file_b).read_text(encoding="utf-8")))
             for action, file_a, file_b in base.ACTION_POOLS}
    prior_usage = {action: Counter(event_id for record in old if action_of(record) == action
                                   for event_id in record["trace"]["source_event_ids"])
                   for action in base.ACTION_CODES}

    for action in base.ACTION_CODES:
        pool_a, pool_b = pools[action]
        usage = prior_usage[action]
        ordinal = 0
        for size, quota in enumerate(SIZE_QUOTAS[action], 1):
            for _ in range(quota):
                events = choose_events(pool_a, pool_b, size, ordinal, usage, forbidden)
                combination = tuple(sorted(event["event_id"] for event in events))
                if combination in forbidden:
                    raise ValueError(f"duplicate combination {combination}")
                forbidden.add(combination)
                records.append(make_case(f"GC-H40-{len(records) + 1:03d}", action, events, ordinal, global_ordinal, evidence))
                ordinal += 1
                global_ordinal += 1
        # B80 itself is balanced at 2--3 uses.  This extension is constrained
        # to avoid all previous full combinations while keeping total use
        # within a two-use range.
        if max(usage.values()) - min(usage.values()) > 2:
            raise ValueError(f"unbalanced total source reuse for {action}: {usage}")

    action_counts = Counter(action_of(record) for record in records)
    size_counts = Counter(len(record["trace"]["source_event_ids"]) for record in records)
    if len(records) != 40 or any(action_counts[action] != 10 for action in base.ACTION_CODES):
        raise ValueError(f"action quota failure: {action_counts}")
    if any(size_counts[size] != 10 for size in range(1, 5)):
        raise ValueError(f"size quota failure: {size_counts}")
    if len(forbidden) != 120:
        raise ValueError("new combinations are not disjoint from B80")
    for action in base.ACTION_CODES:
        combos = Counter(tuple(record["evidence_combination"]["evidence_ids"]) for record in records if action_of(record) == action)
        if len(combos) != 10 or set(combos.values()) != {1}:
            raise ValueError(f"evidence quota failure for {action}: {combos}")
    write_jsonl(OUTPUT_40, records)
    write_jsonl(OUTPUT_120, old + records)
    write_overview(records)
    print(json.dumps({"holdout_cases": len(records), "action_counts": action_counts, "size_counts": size_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a balanced 80-case gold draft solely from event_groups source cards.

The gold case is a precheck window, not a fixed event pair. For each action,
there are five cases containing respectively 1, 2, 3 and 4 event atoms.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[2]
GROUP_DIR = NEUTRON_ROOT / "goldencard" / "event_groups"
EVIDENCE_DIR = NEUTRON_ROOT / "evidencecard" / "cards"
OUTPUT = HERE / "goldcase_balanced_80.jsonl"
OVERVIEW = HERE / "一页总览表.md"

A1 = "on_site_operation_or_calibration_check"
A2 = "cross_channel_similar_anomaly_comparison"
A3 = "record_processing_and_timestamp_check"
A4 = "signal_transmission_path_check"

ACTION_LABELS = {
    A1: "查同一时段现场是否有操作或校准",
    A2: "横向对比其他传感器通道是否出现类似问题",
    A3: "查数据记录和时间戳在处理层面是否有问题",
    A4: "查信号/数据传输路径是否异常",
}
ACTION_CODES = {A1: "A1", A2: "A2", A3: "A3", A4: "A4"}
ACTION_POOLS = [
    (A1, "positive_spike__single_channel.json", "positive_spike__multi_channel_temporal_cluster.json"),
    (A2, "negative_drop__single_channel.json", "negative_drop__multi_channel_temporal_cluster.json"),
    (A3, "short_zero__multi_channel_temporal_cluster.json", "sustained_zero__multi_channel_temporal_cluster.json"),
    (A4, "short_zero__single_channel.json", "sustained_zero__single_channel.json"),
]


def parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(value)


def duration_seconds(event: dict) -> int:
    return int((parse_time(event["time_end"]) - parse_time(event["time_start"])).total_seconds())


def load_evidence() -> dict[str, dict]:
    cards = {}
    for path in EVIDENCE_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                card = json.loads(line)
                cards[card["evidence_id"]] = card
    return cards


EVIDENCE_POOLS = {
    A1: [
        "IAEA-TECDOC-1830-2.2.1.3-01", "IAEA-TECDOC-1830-2.2.1.3-02",
        "NRC-IC-EMERGING-TECH-07", "NRC-GE-LPRM-07", "IAEA-SSG-39-05",
    ],
    A2: [
        "SPRINGER-CORE-MONITORING-2.3.2-01", "IAEA-MODERN-IC-GUIDEBOOK-06",
        "NRC-IC-EMERGING-TECH-06", "IAEA-TECDOC-1830-2.2.1.4-01",
        "IAEA-TECDOC-1830-2.3.1.2-01",
    ],
    A3: [
        "IAEA-TECDOC-1830-2.2.1-01", "IAEA-TECDOC-1830-2.2.1.2-01",
        "IAEA-NP-T-1.1-5.1.1-01", "IAEA-NP-T-1.1-4.1.2-01",
        "IAEA-TECDOC-1830-2.2.1.1-01",
    ],
    A4: [
        "IAEA-NP-T-3.12-2.4.1.2.1-01", "IAEA-NP-T-3.12-2.4.4.1-01",
        "ORNL-BWR-NOISE-SIGNATURES-03", "IAEA-NP-T-3.14-3.4.5.2-01",
        "IAEA-ADVANCED-SURVEILLANCE-04",
    ],
}


def evidence_combination_for(action_id: str, ordinal: int) -> tuple[str, ...]:
    """Use each of the ten possible 3-of-5 combinations twice per action."""
    choices = list(combinations(EVIDENCE_POOLS[action_id], 3))
    return choices[ordinal % len(choices)]


def pick_least_used(pool: list[dict], usage: Counter, rotation: int, excluded: set[str]) -> dict:
    ranked = sorted(
        (event for event in pool if event["event_id"] not in excluded),
        key=lambda event: (usage[event["event_id"]], (pool.index(event) - rotation) % len(pool)),
    )
    if not ranked:
        raise ValueError("no unused event available for this case")
    return ranked[0]


def build_case_events(pool_a: list[dict], pool_b: list[dict], size: int, case_ordinal: int, usage: Counter) -> list[dict]:
    """Select 1--4 distinct events; multi-event cases mix the two pools."""
    selected, excluded = [], set()
    for slot in range(size):
        # A singleton alternates pools. For a multi-event case, the first two
        # selections explicitly cover pool A and pool B; later selections alternate.
        if size >= 2 and slot == 0:
            want_a = case_ordinal % 2 == 0
        elif size >= 2 and slot == 1:
            want_a = case_ordinal % 2 != 0
        else:
            want_a = (case_ordinal + slot) % 2 == 0
        pool = pool_a if want_a else pool_b
        event = pick_least_used(pool, usage, case_ordinal + slot, excluded)
        selected.append(event)
        excluded.add(event["event_id"])
        usage[event["event_id"]] += 1
    return selected


def summarize(events: list[dict], ordinal: int) -> dict:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_type[event["event_type"]].append(event)
    event_summary = []
    for event_type in sorted(by_type):
        group = by_type[event_type]
        channels = [item["channel_count"] for item in group]
        event_summary.append({
            "event_type": event_type,
            "count": len(group),
            "channel_count_range": [min(channels), max(channels)],
            "scope_counts": dict(sorted(Counter(item["scope"] for item in group).items())),
        })
    window_seconds = [120, 180, 240, 300, 420][ordinal % 5]
    scopes = {event["scope"] for event in events}
    return {
        "window_duration_seconds": window_seconds,
        "event_summary": event_summary,
        "component_summary": [{
            "event_type": event["event_type"], "channel_count": event["channel_count"],
            "scope": event["scope"], "duration_seconds": duration_seconds(event),
        } for event in events],
        "pattern_summary": {
            "temporal_recurrence": "isolated_observation" if len(events) == 1 else "combined_event_pattern",
            "cross_channel_pattern": "mixed_single_and_multi_channel" if len(scopes) > 1 else next(iter(scopes)),
            "anomaly_density": "moderate" if window_seconds >= 240 else "high",
        },
    }


def make_case(case_id: str, action_id: str, events: list[dict], ordinal: int, evidence: dict[str, dict]) -> dict:
    evidence_ids = evidence_combination_for(action_id, ordinal)
    sources = [evidence[evidence_id] for evidence_id in evidence_ids]
    return {
        "goldcard_id": case_id,
        "draft_status": "proposed_annotation_pending_human_review",
        "precheck_input": summarize(events, ordinal),
        "trace": {
            "event_source": "goldencard/event_groups",
            "source_event_ids": [event["event_id"] for event in events],
            "composition": "单事件观察" if len(events) == 1 else f"{len(events)}事件组合",
        },
        "evidence_combination": {
            "combination_id": f"EC-{ACTION_CODES[action_id]}-{ordinal % 10 + 1:02d}",
            "evidence_ids": list(evidence_ids),
            "construction_rule": "从该建议的 5 张同一检查意图直接支持卡中选取 3 张；三卡并列支持该唯一建议，不诊断根因。",
        },
        "evidence": [{"evidence_id": evidence_id, "content": source["text"],
                      "action_support_scores": {action_id: 2}}
                     for evidence_id, source in zip(evidence_ids, sources)],
        "gold_action_links": [{"action_id": action_id, "evidence_ids": list(evidence_ids)}],
        "annotation_notes": ["本条是受控事件组组合形成的金标准草稿，不是故障原因诊断。",
                             "每例只保留一个优先检查建议及其直接支持证据。"],
    }


def write_overview(records: list[dict]) -> None:
    action_counts = Counter(record["gold_action_links"][0]["action_id"] for record in records)
    size_counts = Counter(len(record["trace"]["source_event_ids"]) for record in records)
    source_use = Counter(event_id for record in records for event_id in record["trace"]["source_event_ids"])
    lines = ["# 平衡 80 例金标准草稿：一页总览", "",
             "事件来源仅为 `event_groups/`。每例含 1--4 个事件原子；事件 ID 仅追溯，不作为模型输入。", "",
             "| 案例 | 事件数 | 事件组合 | 三证据组合 | 唯一检查建议 |",
             "| --- | ---: | --- | --- | --- |"]
    for record in records:
        parts = [f"{item['event_type']}（{item['channel_count']} 通道，{item['scope']}）" for item in record["precheck_input"]["component_summary"]]
        evidence_ids = "<br>".join(f"`{item['evidence_id']}`" for item in record["evidence"])
        action_id = record["gold_action_links"][0]["action_id"]
        lines.append(f"| {record['goldcard_id']} | {len(parts)} | {' + '.join(parts)} | {evidence_ids} | {ACTION_LABELS[action_id]} |")
    lines += ["", "## 配额与复用检查", "",
              "- " + "；".join(f"{ACTION_LABELS[action]} {action_counts[action]} 例" for action in (A1, A2, A3, A4)) + "。",
              "- 事件数配额：" + "；".join(f"{size} 事件案例 {size_counts[size]} 例" for size in range(1, 5)) + "。",
              f"- 事件原子总数：{len(source_use)}；单个原子复用次数范围：{min(source_use.values())}--{max(source_use.values())}。",
              "- 每例固定链接 3 张证据卡；每项建议有 10 种三证据组合，各出现 2 次。",
              "- 每项建议内部均有 5 个单事件、5 个双事件、5 个三事件和 5 个四事件案例。"]
    OVERVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    evidence, records, seen_combinations, all_source_ids = load_evidence(), [], set(), set()
    ordinal = 0
    for action_id, file_a, file_b in ACTION_POOLS:
        pool_a = json.loads((GROUP_DIR / file_a).read_text(encoding="utf-8"))
        pool_b = json.loads((GROUP_DIR / file_b).read_text(encoding="utf-8"))
        if len(pool_a) != 10 or len(pool_b) != 10:
            raise ValueError(f"event-group count mismatch for {action_id}")
        all_source_ids.update(event["event_id"] for event in pool_a + pool_b)
        usage: Counter = Counter()
        for size in range(1, 5):
            for repeat in range(5):
                local_ordinal = (size - 1) * 5 + repeat
                events = build_case_events(pool_a, pool_b, size, local_ordinal, usage)
                combination = tuple(sorted(event["event_id"] for event in events))
                if combination in seen_combinations:
                    raise ValueError(f"duplicate event combination {combination}")
                seen_combinations.add(combination)
                records.append(make_case(f"GC-B80-{len(records) + 1:03d}", action_id, events, ordinal, evidence))
                ordinal += 1
        expected = {event["event_id"] for event in pool_a + pool_b}
        if set(usage) != expected or max(usage.values()) - min(usage.values()) > 1:
            raise ValueError(f"unbalanced source reuse for {action_id}: {usage}")
    action_counts = Counter(record["gold_action_links"][0]["action_id"] for record in records)
    size_counts = Counter(len(record["trace"]["source_event_ids"]) for record in records)
    used_ids = {event_id for record in records for event_id in record["trace"]["source_event_ids"]}
    if len(records) != 80 or any(action_counts[action] != 20 for action in (A1, A2, A3, A4)):
        raise ValueError(f"wrong action quota: {action_counts}")
    if any(size_counts[size] != 20 for size in range(1, 5)) or used_ids != all_source_ids:
        raise ValueError(f"wrong group-size quota or sources: {size_counts}")
    if len(set().union(*map(set, EVIDENCE_POOLS.values()))) != 20:
        raise ValueError("evidence cards must not be shared across action pools")
    if any(len(record["evidence"]) != 3 for record in records):
        raise ValueError("each case must have exactly three evidence cards")
    for action_id in (A1, A2, A3, A4):
        action_records = [record for record in records if record["gold_action_links"][0]["action_id"] == action_id]
        combinations_seen = Counter(tuple(record["evidence_combination"]["evidence_ids"]) for record in action_records)
        if len(combinations_seen) != 10 or set(combinations_seen.values()) != {2}:
            raise ValueError(f"wrong evidence-combination quota for {action_id}: {combinations_seen}")
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    write_overview(records)


if __name__ == "__main__":
    main()

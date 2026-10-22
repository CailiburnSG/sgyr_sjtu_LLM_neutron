#!/usr/bin/env python3
"""Build an 80-case draft from 30 aggregate cases plus 50 real channel-card cases."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[2]
PARENT_CASES = HERE.parent / "precheck_case_draft_30" / "goldcase_30.jsonl"
EVENT_DIR = NEUTRON_ROOT / "eventcard" / "output"
EVIDENCE_DIR = NEUTRON_ROOT / "evidencecard" / "cards"
OUTPUT = HERE / "goldcase_80.jsonl"
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


def parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(value)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_evidence() -> dict[str, dict]:
    result = {}
    for path in EVIDENCE_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                card = json.loads(line)
                result[card["evidence_id"]] = card
    return result


def summarize(cards: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        by_type[card["event_type"]].append(card)
    event_summary = []
    for event_type in sorted(by_type):
        group = by_type[event_type]
        event_summary.append({
            "event_type": event_type,
            "count": len(group),
            "channel_count_range": [1, 1],
            "scope_counts": {"single_channel": len(group)},
        })
    start = min(parse_time(card["time_start"]) for card in cards)
    end = max(parse_time(card["time_end"]) for card in cards)
    return {
        "window_duration_seconds": int((end - start).total_seconds()),
        "event_summary": event_summary,
        "pattern_summary": {
            "temporal_recurrence": "isolated" if len(cards) == 1 else "occasional" if len(cards) <= 3 else "repeated",
            "cross_channel_pattern": "single_channel_only",
            "anomaly_density": "low" if len(cards) <= 2 else "moderate" if len(cards) <= 5 else "high",
        },
    }


def evidence_for(action_id: str, ordinal: int) -> tuple[str, str]:
    options = {
        A1: [
            ("IAEA-TECDOC-1830-2.2.1.3-01", "尖峰可与通道检查或校准活动相关，故核对同一时段现场操作或校准记录，不认定活动发生。"),
            ("NRC-IC-EMERGING-TECH-07", "资料列举例行校准、通道检查和功能试验为性能核实手段，支持查同期现场记录。"),
            ("NRC-GE-LPRM-07", "资料给出运行、旁路和校准模式，支持核对同期现场操作或校准状态，不判定当前模式。"),
        ],
        A2: [
            ("SPRINGER-CORE-MONITORING-2.3.2-01", "资料支持在可比性确认后横向比较其他传感器通道是否有类似时间变化。"),
            ("NRC-IC-EMERGING-TECH-06", "有限通道差异应保留为比较发现，支持横向核对其他可比通道。"),
        ],
        A4: [
            ("IAEA-NP-T-3.12-2.4.1.2.1-01", "受抑零可提示开路；只建议核对信号/数据传输路径，不诊断开路。"),
            ("IAEA-NP-T-3.12-2.4.4.1-01", "转换、隔离、调理和 ADC 输入属于可核对的信号传输路径条件。"),
        ],
    }
    return options[action_id][ordinal % len(options[action_id])]


def make_child(case_id: str, family_id: str, parent: dict, cards: list[dict], ordinal: int, evidence: dict[str, dict]) -> dict:
    parent_action = parent["gold_action_links"][0]["action_id"]
    action = A4 if parent["goldcard_id"] <= "GC-030-010" else parent_action
    evidence_id, rationale = evidence_for(action, ordinal)
    selected = evidence[evidence_id]
    start = min(card["time_start"] for card in cards)
    end = max(card["time_end"] for card in cards)
    return {
        "goldcard_id": case_id,
        "case_family_id": family_id,
        "draft_status": "proposed_annotation_pending_human_review",
        "precheck_input": summarize(cards),
        "trace": {
            "source_eventcard_file": parent["trace"]["source_eventcard_file"].replace("_aggregated_cards.json", "_channel_cards.json"),
            "source_event_ids": [card["channel_card_id"] for card in cards],
            "source_atomic_event_ids": [atomic for card in cards for atomic in card["source_atomic_event_ids"]],
            "time_start": start,
            "time_end": end,
            "selection_note": "real channel-card subcombination within aggregate-case family " + family_id,
        },
        "evidence": [{
            "evidence_id": evidence_id,
            "content": selected["text"],
            "action_support_scores": {action: 2},
            "annotation_note": rationale,
        }],
        "gold_action_links": [{"action_id": action, "evidence_ids": [evidence_id]}],
        "annotation_notes": [
            "本条由真实单通道事件卡组合而成；同一 case_family_id 不得跨训练/测试划分。",
            "每个案例仅保留一个优先检查建议及其直接支持证据。",
        ],
    }


def add_family(parent: dict) -> dict:
    copied = json.loads(json.dumps(parent, ensure_ascii=False))
    copied["case_family_id"] = "F-" + parent["goldcard_id"].removeprefix("GC-")
    return copied


def write_overview(records: list[dict]) -> None:
    counts = Counter(item["gold_action_links"][0]["action_id"] for item in records)
    lines = [
        "# 80 个预检案例草稿：一页总览",
        "",
        "每例都可追溯到真实事件卡。`case_family_id` 相同表示共享同一原始时间簇，未来不得跨训练/测试划分。",
        "",
        "| 案例 | 家族 | 事件组合 | 直接证据 | 唯一检查建议 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        summary = record["precheck_input"]
        shape = "；".join(f"{item['event_type']}×{item['count']}（{item['channel_count_range'][0]}–{item['channel_count_range'][1]} 通道）" for item in summary["event_summary"])
        shape += f"；{len(record['trace']['source_event_ids'])} 个事件；{summary['window_duration_seconds']} s"
        evidence_id = record["evidence"][0]["evidence_id"]
        action = record["gold_action_links"][0]["action_id"]
        lines.append(f"| {record['goldcard_id']} | {record['case_family_id']} | {shape} | `{evidence_id}` | {ACTION_LABELS[action]} |")
    lines.extend([
        "",
        "## 当前分布",
        "",
        "- " + "；".join(f"{action} {counts.get(action, 0)} 例" for action in (A1, A2, A3, A4)) + "。",
        "- 共 30 个 `case_family_id`；80 个案例不是 80 段相互独立的原始运行记录。",
    ])
    OVERVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parents = read_jsonl(PARENT_CASES)
    if len(parents) != 30:
        raise ValueError("expected 30 parent cases")
    evidence = load_evidence()
    channel_files = {
        "eventcard/output/A1_1_snapshot_aggregated_cards.json": "A1_1_snapshot_channel_cards.json",
        "eventcard/output/A1_1_aggregated_cards.json": "A1_1_channel_cards.json",
    }
    source_cards = {key: json.loads((EVENT_DIR / filename).read_text(encoding="utf-8")) for key, filename in channel_files.items()}
    records = [add_family(parent) for parent in parents]
    used_channel_ids: dict[str, set[str]] = defaultdict(set)
    ordinal = 0
    for parent_index, parent in enumerate(parents, start=1):
        source_key = parent["trace"]["source_eventcard_file"]
        start, end = parse_time(parent["trace"]["time_start"]), parse_time(parent["trace"]["time_end"])
        cards = [card for card in source_cards[source_key] if start <= parse_time(card["time_start"]) <= end]
        if not cards:
            raise ValueError(f"no channel cards for {parent['goldcard_id']}")
        family_id = "F-" + parent["goldcard_id"].removeprefix("GC-")
        if parent_index <= 20:
            channels = sorted({card["channel"] for card in cards})
            buckets = [[card for card in cards if card["channel"] in channels[::2]], [card for card in cards if card["channel"] in channels[1::2]]]
        else:
            buckets = [cards]
        for local_index, bucket in enumerate(buckets, start=1):
            if not bucket:
                raise ValueError(f"empty channel bucket for {parent['goldcard_id']}")
            ids = {card["channel_card_id"] for card in bucket}
            source_name = channel_files[source_key]
            if used_channel_ids[source_name] & ids:
                raise ValueError(f"channel-card reuse in {parent['goldcard_id']}")
            used_channel_ids[source_name].update(ids)
            case_id = f"GC-080-{30 + ordinal + 1:03d}"
            records.append(make_child(case_id, family_id, parent, bucket, ordinal, evidence))
            ordinal += 1
    if len(records) != 80 or ordinal != 50:
        raise ValueError(f"expected 80 records / 50 children, got {len(records)} / {ordinal}")
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    write_overview(records)


if __name__ == "__main__":
    main()

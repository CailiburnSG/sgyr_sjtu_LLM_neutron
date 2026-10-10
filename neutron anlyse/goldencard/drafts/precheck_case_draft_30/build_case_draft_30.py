#!/usr/bin/env python3
"""Build 30 disjoint, manually specified precheck-case drafts from event cards."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[2]
EVENT_DIR = NEUTRON_ROOT / "eventcard" / "output"
EVIDENCE_DIR = NEUTRON_ROOT / "evidencecard" / "cards"
OUTPUT = HERE / "goldcase_30.jsonl"
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


def load_json(filename: str) -> list[dict]:
    return json.loads((EVENT_DIR / filename).read_text(encoding="utf-8"))


def load_evidence() -> dict[str, dict]:
    result = {}
    for path in EVIDENCE_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                card = json.loads(line)
                result[card["evidence_id"]] = card
    return result


def choose(cards: list[dict], start: str, end: str) -> list[dict]:
    left, right = parse_time(start), parse_time(end)
    selected = [card for card in cards if left <= parse_time(card["time_start"]) <= right]
    if not selected:
        raise ValueError(f"empty case window {start} -- {end}")
    return selected


def summarize(cards: list[dict]) -> dict:
    start = min(parse_time(card["time_start"]) for card in cards)
    end = max(parse_time(card["time_end"]) for card in cards)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        by_type[card["event_type"]].append(card)
    events = []
    for event_type in sorted(by_type):
        group = by_type[event_type]
        counts = [card["channel_count"] for card in group]
        events.append({
            "event_type": event_type,
            "count": len(group),
            "channel_count_range": [min(counts), max(counts)],
            "scope_counts": dict(sorted(Counter(card["scope"] for card in group).items())),
        })
    scopes = Counter(card["scope"] for card in cards)
    if set(scopes) == {"single_channel"}:
        cross = "single_channel_only"
    elif scopes.get("single_channel", 0):
        cross = "mixed_single_and_multi_channel"
    else:
        cross = "multi_channel_cluster"
    return {
        "window_duration_seconds": int((end - start).total_seconds()),
        "event_summary": events,
        "pattern_summary": {
            "temporal_recurrence": "isolated" if len(cards) == 1 else "occasional" if len(cards) <= 3 else "repeated",
            "cross_channel_pattern": cross,
            "anomaly_density": "low" if len(cards) <= 2 else "moderate" if len(cards) <= 5 else "high",
        },
    }


def make_case(case_id: str, source_file: str, cards: list[dict], note: str, evidence_id: str, action_id: str, rationale: str, evidence: dict[str, dict]) -> dict:
    card = evidence[evidence_id]
    return {
        "goldcard_id": case_id,
        "draft_status": "proposed_annotation_pending_human_review",
        "precheck_input": summarize(cards),
        "trace": {
            "source_eventcard_file": f"eventcard/output/{source_file}",
            "source_event_ids": [item["event_id"] for item in cards],
            "time_start": min(item["time_start"] for item in cards),
            "time_end": max(item["time_end"] for item in cards),
            "selection_note": note,
        },
        "evidence": [{
            "evidence_id": evidence_id,
            "content": card["text"],
            "action_support_scores": {action_id: 2},
            "annotation_note": rationale,
        }],
        "gold_action_links": [{"action_id": action_id, "evidence_ids": [evidence_id]}],
        "annotation_notes": [
            "本条是研究者初标草案，不是已仲裁的正式金标准。",
            "每个案例仅保留一个优先检查建议及其直接支持证据。",
        ],
    }


def write_overview(records: list[dict]) -> None:
    action_counts = Counter(record["gold_action_links"][0]["action_id"] for record in records)
    distribution = "；".join(
        f"{action_id} {action_counts.get(action_id, 0)} 例"
        for action_id in (A1, A2, A3, A4)
    )
    lines = [
        "# 30 个预检案例草稿：一页总览",
        "",
        "每行对应一个真实事件组合；每例只有一张直接证据和一个唯一建议。它们均为待人工复核草稿，",
        "不表示已经确认任何故障原因。",
        "",
        "| 案例 | 事件组合 | 直接证据 | 唯一检查建议 |",
        "| --- | --- | --- | --- |",
    ]
    for record in records:
        summary = record["precheck_input"]
        types = "；".join(
            f"{item['event_type']}×{item['count']}（{item['channel_count_range'][0]}–{item['channel_count_range'][1]} 通道）"
            for item in summary["event_summary"]
        )
        pattern = summary["pattern_summary"]["cross_channel_pattern"]
        shape = f"{types}；{len(record['trace']['source_event_ids'])} 个事件；{summary['window_duration_seconds']} s；{pattern}"
        evidence_id = record["evidence"][0]["evidence_id"]
        action_id = record["gold_action_links"][0]["action_id"]
        lines.append(f"| {record['goldcard_id']} | {shape} | `{evidence_id}` | {ACTION_LABELS[action_id]} |")
    lines.extend([
        "",
        "## 当前分布与边界",
        "",
        f"- 当前分布：{distribution}。",
        "- A3 可由 CSV 层面的多通道同步、覆盖突变或重复短零值等可疑记录形态触发，不要求预先确认 CSV 出错。",
        "- `GC-030-006` 是唯一天然孤立的短零值；其余 29 例均包含两个或以上事件卡。",
        "- 案例之间在同一来源事件文件内不共享事件 ID；后续训练/测试划分仍应按时间簇或来源记录分组。",
    ])
    OVERVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def spec(case_id: str, source: str, start: str, end: str, note: str, evidence_id: str, action: str, rationale: str) -> tuple:
    return case_id, source, start, end, note, evidence_id, action, rationale


def main() -> None:
    zero_file = "A1_1_snapshot_aggregated_cards.json"
    transient_file = "A1_1_aggregated_cards.json"
    source = {zero_file: load_json(zero_file), transient_file: load_json(transient_file)}
    evidence = load_evidence()
    specs = [
        # Short-zero combinations: broad near-synchronous record patterns map to A3; localized patterns map to A4.
        spec("GC-030-001", zero_file, "01-21 01:04:59", "01-21 01:14:34", "two separated two-channel short-zero observations", "IAEA-NP-T-3.12-2.4.1.2.1-01", A4, "受抑零可提示开路；只建议核对两条受影响通道的信号/数据传输路径，不诊断开路。"),
        spec("GC-030-002", zero_file, "01-21 01:40:31", "01-21 01:47:27", "two two-channel short-zero observations in one local window", "IAEA-NP-T-1.1-5.1.1-01", A3, "历史监测数据可出现缺失点、卡滞值等质量问题；两次近时短零值首先支持核对记录、导出和时间戳处理，而不认定 CSV 已出错。"),
        spec("GC-030-003", zero_file, "01-21 01:48:28", "01-21 01:57:02", "repeated short-zero cluster with mixed coverage", "IAEA-TECDOC-1830-2.2.1-01", A3, "资料明确把卡滞、缺失和异常点列为采集后数据合格性对象；重复、覆盖变化的短零值可触发记录/时间戳处理核查。"),
        spec("GC-030-004", zero_file, "01-21 02:01:02", "01-21 02:07:54", "repeated short-zero cluster including whole-array coverage", "IAEA-TECDOC-1830-2.2.1.2-01", A3, "一个或多个传感器的记录缺口可出现在 plant-computer 数据中；全阵列/部分阵列交替短零值支持优先核对记录和时间戳处理。"),
        spec("GC-030-005", zero_file, "01-21 02:10:15", "01-21 02:14:52", "dense short-zero cluster with repeated whole-array coverage", "IAEA-NP-T-1.1-5.1.1-01", A3, "重复全阵列短零值是需要先识别的历史数据质量形态，支持核对 CSV 记录、排序和时间戳处理。"),
        spec("GC-030-006", zero_file, "01-21 02:21:17", "01-21 02:21:17", "natural isolated two-channel short-zero observation", "IAEA-NP-T-3.12-2.4.1.2.1-01", A4, "唯一的天然孤立例；受抑零可提示开路，故检查信号/数据传输路径，不诊断开路。"),
        spec("GC-030-007", zero_file, "01-21 02:38:22", "01-21 02:38:28", "six-second short-zero pair with coverage change", "IAEA-TECDOC-1830-2.2-01", A3, "6 秒内覆盖从少量通道变为多通道，是先核对数据记录、时间标记和处理形态的可疑 CSV 模式。"),
        spec("GC-030-008", zero_file, "01-21 03:18:31", "01-21 03:20:03", "short-zero pair with three- then seven-channel coverage", "IAEA-TECDOC-1830-2.2.1-01", A3, "覆盖范围快速扩展的短零值可先按数据合格性问题核对记录、导出和时间戳处理，不确认任何原因。"),
        spec("GC-030-009", zero_file, "01-21 03:42:01", "01-21 03:44:55", "repeated short-zero cluster with expanding coverage", "IAEA-NP-T-1.1-5.1.1-01", A3, "重复短零值与覆盖扩展属于历史数据中应识别的缺失/异常形态，支持查 CSV 处理与时间戳。"),
        spec("GC-030-010", zero_file, "01-21 04:25:32", "01-21 04:33:30", "repeated short-zero cluster with variable coverage", "IAEA-TECDOC-1830-2.2.1.2-01", A3, "多传感器记录缺口可由 plant-computer 数据产生；覆盖变化的重复短零值支持优先核对记录与时间处理。"),
        # Mixed spike/drop combinations: A1 when spike evidence gives a direct record-check direction.
        spec("GC-030-011", transient_file, "2025-01-21 23:37:11", "2025-01-21 23:40:28", "early multi-channel spike/drop cluster", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰可与通道检查或校准活动相关，故查同一时段现场操作或校准记录，不认定活动发生。"),
        spec("GC-030-012", transient_file, "2025-01-21 23:42:37", "2025-01-21 23:46:43", "mixed spike/drop cluster with single- and multi-channel events", "NRC-IC-EMERGING-TECH-07", A1, "资料明确列举例行校准、通道检查和功能试验为仪表性能核实手段，支持核查同期现场记录。"),
        spec("GC-030-013", transient_file, "2025-01-21 23:50:50", "2025-01-21 23:52:24", "short mixed transient sequence", "NRC-GE-LPRM-07", A1, "资料给出通道运行、旁路和校准模式，支持核查同期现场操作或校准状态，不判定当前模式。"),
        spec("GC-030-014", transient_file, "2025-01-21 23:53:15", "2025-01-21 23:56:32", "dense mixed spike/drop sequence", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰/离群记录可触发对同一时段通道检查或校准记录的核查。"),
        # A2 only for sequences dominated by single-channel observations.
        spec("GC-030-015", transient_file, "2025-01-21 23:56:52", "2025-01-22 00:00:12", "mixed sequence with equal single- and multi-channel observations", "SPRINGER-CORE-MONITORING-2.3.2-01", A2, "资料建议将时间变化与同一探测器链其他探测器比较，故横向检查是否存在类似问题。"),
        spec("GC-030-016", transient_file, "2025-01-22 00:01:21", "2025-01-22 00:03:31", "multi-channel transient cluster", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰出现时可查同一时段现场操作或校准记录，不作因果确认。"),
        spec("GC-030-017", transient_file, "2025-01-22 00:04:02", "2025-01-22 00:06:24", "single-channel-dominant mixed transient sequence", "NRC-IC-EMERGING-TECH-06", A2, "冗余/相关通道差异应保留为比较发现，支持横向核对其他可比通道是否有类似问题。"),
        spec("GC-030-018", transient_file, "2025-01-22 00:08:10", "2025-01-22 00:11:53", "high-density mixed spike/drop cluster", "NRC-GE-LPRM-07", A1, "通道校准模式与替代输入的资料支持核查同期现场操作或校准状态。"),
        spec("GC-030-019", transient_file, "2025-01-22 00:13:27", "2025-01-22 00:17:58", "single-channel-dominant transient sequence", "SPRINGER-CORE-MONITORING-2.3.2-01", A2, "以单通道观测为主时，资料支持在可比性确认后横向比较其他传感器是否有类似时间变化。"),
        spec("GC-030-020", transient_file, "2025-01-22 00:18:04", "2025-01-22 00:22:19", "single-channel-dominant mixed transient cluster", "NRC-HRTD-9.1-9.1.2.4-01", A2, "资料说明探测器输出可作相对比较；本例仅建议横向核对，不假定当前通道天然可比。"),
        spec("GC-030-021", transient_file, "2025-01-22 00:22:37", "2025-01-22 00:25:34", "single-channel-dominant mixed transient cluster", "IAEA-MODERN-IC-GUIDEBOOK-06", A2, "资料把通道比较作为筛查线索且保留通道逻辑限制，支持有前提的横向比较。"),
        spec("GC-030-022", transient_file, "2025-01-22 00:26:34", "2025-01-22 00:30:06", "single-channel-dominant mixed transient sequence", "SPRINGER-CORE-MONITORING-2.3.2-01", A2, "资料支持将时间变化与同一探测器链其他探测器比较，以核对是否存在类似问题。"),
        spec("GC-030-023", transient_file, "2025-01-22 00:30:36", "2025-01-22 00:33:54", "mixed spike/drop cluster", "NRC-IC-EMERGING-TECH-07", A1, "例行校准、通道检查和功能试验可用于核实仪表性能，支持查询同期现场记录。"),
        spec("GC-030-024", transient_file, "2025-01-22 00:35:24", "2025-01-22 00:39:57", "mixed spike/drop cluster with broad channel coverage", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰/离群记录支持查同一时段现场操作或校准记录，不判定其为根因。"),
        spec("GC-030-025", transient_file, "2025-01-22 00:40:30", "2025-01-22 00:43:41", "mixed spike/drop cluster", "NRC-GE-LPRM-07", A1, "运行、旁路和校准模式是需要通过同期记录核对的现场状态，不由事件直接确认。"),
        spec("GC-030-026", transient_file, "2025-01-22 00:44:00", "2025-01-22 00:47:35", "mixed spike/drop cluster", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰可与通道检查或校准活动相关，支持检查同期现场记录。"),
        spec("GC-030-027", transient_file, "2025-01-22 00:48:24", "2025-01-22 00:51:19", "mixed spike/drop sequence", "NRC-IC-EMERGING-TECH-07", A1, "资料列举校准、通道检查和功能试验为性能核实手段，支持核查同期现场记录。"),
        spec("GC-030-028", transient_file, "2025-01-22 00:52:17", "2025-01-22 00:54:39", "mixed spike/drop cluster", "IAEA-TECDOC-1830-2.2.1.3-01", A1, "尖峰/离群资料支持查同一时段现场操作或校准记录，不作因果判断。"),
        spec("GC-030-029", transient_file, "2025-01-22 00:55:27", "2025-01-22 00:56:39", "short mixed spike/drop sequence", "NRC-GE-LPRM-07", A1, "资料中的校准模式支持将短时混合瞬态与同期现场操作/校准记录对齐核对。"),
        spec("GC-030-030", transient_file, "2025-01-22 00:57:33", "2025-01-22 00:59:58", "late mixed transient sequence with single-channel observations", "NRC-IC-EMERGING-TECH-06", A2, "资料支持将有限通道差异保留为横向比较发现，核对其他可比传感器是否有类似问题。"),
    ]
    records = []
    used: dict[str, set[str]] = defaultdict(set)
    for case_id, source_file, start, end, note, evidence_id, action_id, rationale in specs:
        cards = choose(source[source_file], start, end)
        event_ids = {card["event_id"] for card in cards}
        overlap = used[source_file] & event_ids
        if overlap:
            raise ValueError(f"source event overlap in {case_id}: {sorted(overlap)}")
        used[source_file].update(event_ids)
        records.append(make_case(case_id, source_file, cards, note, evidence_id, action_id, rationale, evidence))
    if len(records) != 30:
        raise ValueError(f"expected 30 records, got {len(records)}")
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    write_overview(records)


if __name__ == "__main__":
    main()

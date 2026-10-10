#!/usr/bin/env python3
"""Build ten auditable, unannotated precheck-case drafts from real event cards.

This script deliberately knows nothing about prior goldcard evidence/action drafts.
It reads only the two event-card outputs named below and writes X-only case records.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVENT_OUTPUT = HERE.parents[2] / "eventcard" / "output"
OUTPUT = HERE / "pilot_10_cases.jsonl"
EVIDENCE_CARD_DIR = HERE.parents[2] / "evidencecard" / "cards"


def parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unsupported event time: {value}")


def load_cards(filename: str) -> list[dict]:
    return json.loads((EVENT_OUTPUT / filename).read_text(encoding="utf-8"))


def load_evidence() -> dict[str, dict]:
    evidence: dict[str, dict] = {}
    for path in EVIDENCE_CARD_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                card = json.loads(line)
                evidence[card["evidence_id"]] = card
    return evidence


def select(cards: list[dict], start: str, end: str) -> list[dict]:
    start_time, end_time = parse_time(start), parse_time(end)
    selected = [card for card in cards if start_time <= parse_time(card["time_start"]) <= end_time]
    if not selected:
        raise ValueError(f"Empty selection: {start}--{end}")
    return selected


def pattern_summary(cards: list[dict], duration_seconds: int) -> dict:
    event_count = len(cards)
    scopes = Counter(card["scope"] for card in cards)
    if set(scopes) == {"single_channel"}:
        cross_channel = "single_channel_only"
    elif scopes.get("single_channel", 0):
        cross_channel = "mixed_single_and_multi_channel"
    else:
        cross_channel = "multi_channel_cluster"

    if event_count == 1:
        recurrence = "isolated"
    elif event_count <= 3:
        recurrence = "occasional"
    else:
        recurrence = "repeated"

    density = "low" if event_count == 1 else "moderate" if event_count <= 5 else "high"
    return {
        "temporal_recurrence": recurrence,
        "cross_channel_pattern": cross_channel,
        "anomaly_density": density,
    }


def summarize(cards: list[dict]) -> dict:
    start = min(parse_time(card["time_start"]) for card in cards)
    end = max(parse_time(card["time_end"]) for card in cards)
    duration_seconds = int((end - start).total_seconds())
    by_type: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        by_type[card["event_type"]].append(card)

    event_summary = []
    for event_type in sorted(by_type):
        group = by_type[event_type]
        channel_counts = [card["channel_count"] for card in group]
        event_summary.append(
            {
                "event_type": event_type,
                "count": len(group),
                "channel_count_range": [min(channel_counts), max(channel_counts)],
                "scope_counts": dict(sorted(Counter(card["scope"] for card in group).items())),
            }
        )

    return {
        "window_duration_seconds": duration_seconds,
        "event_summary": event_summary,
        "pattern_summary": pattern_summary(cards, duration_seconds),
    }


def case(
    case_id: str,
    source_file: str,
    cards: list[dict],
    selection_note: str,
    evidence_catalog: dict[str, dict],
    proposed_labels: list[dict],
) -> dict:
    evidence = []
    action_to_evidence: dict[str, list[str]] = defaultdict(list)
    for label in proposed_labels:
        evidence_id = label["evidence_id"]
        source = evidence_catalog[evidence_id]
        support_scores = label["action_support_scores"]
        evidence.append(
            {
                "evidence_id": evidence_id,
                "content": source["text"],
                "action_support_scores": support_scores,
                "annotation_note": label["annotation_note"],
            }
        )
        for action_id, score in support_scores.items():
            if score == 2:
                action_to_evidence[action_id].append(evidence_id)

    return {
        "goldcard_id": case_id,
        "draft_status": (
            "proposed_annotation_pending_human_review"
            if evidence
            else "proposed_no_evidence_action_pending_human_review"
        ),
        "precheck_input": summarize(cards),
        "trace": {
            "source_eventcard_file": f"eventcard/output/{source_file}",
            "source_event_ids": [card["event_id"] for card in cards],
            "time_start": min(card["time_start"] for card in cards),
            "time_end": max(card["time_end"] for card in cards),
            "selection_note": selection_note,
        },
        "evidence": evidence,
        "gold_action_links": [
            {"action_id": action_id, "evidence_ids": evidence_ids}
            for action_id, evidence_ids in sorted(action_to_evidence.items())
        ],
        "annotation_notes": [
            "本条是首轮研究者草案，不是已仲裁的正式金标准。",
            "第一版每个案例至多保留一项固定检查建议；仅记录分数为 2 的正式证据—行动关系。",
            "未列出的关系不应被解读为已完成 0/1 全库穷举。",
        ],
    }


def main() -> None:
    short_zero_file = "A1_1_snapshot_aggregated_cards.json"
    transient_file = "A1_1_aggregated_cards.json"
    short_zero = load_cards(short_zero_file)
    transient = load_cards(transient_file)
    evidence_catalog = load_evidence()

    # These are intentionally explicit pilot windows, selected for morphological variety.
    # They are not a future universal clustering threshold.
    specs = [
        ("GC-PILOT-001", short_zero_file, short_zero, "01-21 01:04:59", "01-21 01:04:59", "single short-zero observation", [
            {"evidence_id": "IAEA-NP-T-3.12-2.4.1.2.1-01", "action_support_scores": {"signal_transmission_path_check": 2}, "annotation_note": "资料明确指出受抑零可提示开路；本例只据此建议人工核对两条受影响通道的信号/数据传输路径，不诊断开路或任何具体失效。"},
        ]),
        ("GC-PILOT-002", short_zero_file, short_zero, "01-21 01:47:27", "01-21 01:53:56", "repeated short-zero cluster with a whole-array occurrence", [
            {"evidence_id": "IAEA-NP-T-3.12-2.4.4.1-01", "action_support_scores": {"signal_transmission_path_check": 2}, "annotation_note": "重复且覆盖范围变化的近时零值需要核对同步采集、相位和信号调理等传输路径条件；不据此断言路径故障。"},
        ]),
        ("GC-PILOT-003", short_zero_file, short_zero, "01-21 02:01:02", "01-21 02:14:52", "repeated short-zero cluster with several whole-array occurrences", [
            {"evidence_id": "IAEA-NP-T-3.14-3.4.5-01", "action_support_scores": {"signal_transmission_path_check": 2}, "annotation_note": "多次全阵列/部分阵列近时短零值使采样、调理与同步等传输路径条件成为需要核对的前提，而非故障结论。"},
        ]),
        ("GC-PILOT-004", short_zero_file, short_zero, "01-21 02:38:22", "01-21 02:38:28", "near-synchronous short-zero pair with different channel coverage", [
            {"evidence_id": "IAEA-NP-T-3.12-2.4.4.1-01", "action_support_scores": {"signal_transmission_path_check": 2}, "annotation_note": "6 秒内覆盖范围变化的同期零值可支持核对多通道同步、复用相位和信号传输路径；不确认共同原因。"},
        ]),
        ("GC-PILOT-005", short_zero_file, short_zero, "01-21 04:25:32", "01-21 04:37:38", "mixed-coverage repeated short-zero cluster", [
            {"evidence_id": "ORNL-BWR-NOISE-SIGNATURES-03", "action_support_scores": {"signal_transmission_path_check": 2}, "annotation_note": "资料说明电流回路转换、隔离、调理和同步记录是信号传输路径的重要条件，适用于覆盖范围反复变化的短零值簇。"},
        ]),
        ("GC-PILOT-006", transient_file, transient, "2025-01-21 23:37:11", "2025-01-21 23:46:43", "early mixed spike/drop cluster", [
            {"evidence_id": "IAEA-TECDOC-1830-2.2.1.3-01", "action_support_scores": {"on_site_operation_or_calibration_check": 2}, "annotation_note": "尖峰/离群记录可与通道检查或校准活动相关，故建议查同一时段现场操作或校准记录，不认定活动已发生。"},
        ]),
        ("GC-PILOT-007", transient_file, transient, "2025-01-21 23:50:50", "2025-01-22 00:00:12", "mixed spike/drop cluster crossing midnight", [
            {"evidence_id": "IAEA-TECDOC-1830-2.2.1.3-01", "action_support_scores": {"on_site_operation_or_calibration_check": 2}, "annotation_note": "包含尖峰的混合簇可触发查同一时段现场操作或校准记录，不构成活动原因判断。"},
        ]),
        ("GC-PILOT-008", transient_file, transient, "2025-01-22 00:01:21", "2025-01-22 00:11:53", "high-density mixed spike/drop cluster", [
            {"evidence_id": "IAEA-TECDOC-1830-2.2.1.3-01", "action_support_scores": {"on_site_operation_or_calibration_check": 2}, "annotation_note": "高密度簇中的尖峰允许建议查同一时段现场操作或校准记录，但不允许推断其为根因。"},
        ]),
        ("GC-PILOT-009", transient_file, transient, "2025-01-22 00:13:27", "2025-01-22 00:18:07", "mostly single-channel transient sequence with one multi-channel observation", [
            {"evidence_id": "SPRINGER-CORE-MONITORING-2.3.2-01", "action_support_scores": {"cross_channel_similar_anomaly_comparison": 2}, "annotation_note": "以单通道瞬态为主时，可在可比性确认后横向对比其他传感器通道是否出现类似问题。"},
        ]),
        ("GC-PILOT-010", transient_file, transient, "2025-01-22 00:44:00", "2025-01-22 00:54:39", "late mixed spike/drop cluster with variable channel coverage", [
            {"evidence_id": "IAEA-MODERN-IC-GUIDEBOOK-06", "action_support_scores": {"cross_channel_similar_anomaly_comparison": 2}, "annotation_note": "资料将通道间比较作为筛查线索并保留特定通道逻辑限制，支持有前提地横向对比是否存在类似问题，而非自动判定。"},
        ]),
    ]

    records = []
    for case_id, source_file, source_cards, start, end, note, labels in specs:
        records.append(case(case_id, source_file, select(source_cards, start, end), note, evidence_catalog, labels))
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


if __name__ == "__main__":
    main()

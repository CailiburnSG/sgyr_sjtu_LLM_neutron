"""Legacy single-event draft generator.

The current gold-standard unit is a multi-event precheck case in
``drafts/precheck_case_pilot_10``.  This module is retained only to read or
reproduce historical single-event drafts; it must not be used to create new
gold labels or evidence/action links.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib
import json

from evidencecard.workflow import QUERY_MAPPING_VERSION, RETRIEVER_VERSION, build_query, load_cards, rank_candidates


ACTION_ONTOLOGY_VERSION = "v2"
ACTION_IDS = frozenset(
    {
        "on_site_operation_or_calibration_check",
        "cross_channel_similar_anomaly_comparison",
        "record_processing_and_timestamp_check",
        "signal_transmission_path_check",
    }
)


def load_events(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Event-card input must be a JSON array.")
    return payload


def _stratum(event: dict[str, Any]) -> tuple[str, str]:
    return event["event_type"], event["scope"]


def _duration_seconds(event: dict[str, Any]) -> float:
    """Return the elapsed event-window duration without changing the event card."""
    def parse(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.strptime(value, "%m-%d %H:%M:%S")

    return max(0.0, (parse(event["time_end"]) - parse(event["time_start"])).total_seconds())


def evenly_spaced_stratified_sample(events: list[dict[str, Any]], per_stratum: int) -> list[dict[str, Any]]:
    """Sample each observed event_type × scope stratum across its full time span."""
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[_stratum(event)].append(event)
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda event: (event["time_start"], event["event_id"]))
        if len(group) < per_stratum:
            raise ValueError(f"Stratum {key} has {len(group)} events, fewer than requested {per_stratum}.")
        indexes = [round(index * (len(group) - 1) / (per_stratum - 1)) if per_stratum > 1 else 0 for index in range(per_stratum)]
        selected.extend(group[index] for index in indexes)
    return sorted(selected, key=lambda event: (event["event_type"], event["scope"], event["time_start"], event["event_id"]))


def quota_stratified_sample(events: list[dict[str, Any]], quotas: dict[tuple[str, str], int]) -> list[dict[str, Any]]:
    """Select a time-spread sample using explicit per-stratum quotas."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[_stratum(event)].append(event)
    selected: list[dict[str, Any]] = []
    for key, quota in sorted(quotas.items()):
        group = sorted(groups[key], key=lambda event: (event["time_start"], event["event_id"]))
        if quota < 1 or len(group) < quota:
            raise ValueError(f"Stratum {key} has {len(group)} events, fewer than requested {quota}.")
        indexes = [round(index * (len(group) - 1) / (quota - 1)) if quota > 1 else 0 for index in range(quota)]
        selected.extend(group[index] for index in indexes)
    return sorted(selected, key=lambda event: (event["event_type"], event["scope"], event["time_start"], event["event_id"]))


def draft_goldcard(event: dict[str, Any], cards: list[dict[str, Any]], top_k: int, ordinal_in_stratum: int) -> dict[str, Any]:
    query = build_query(event)
    candidates = rank_candidates(query, cards, top_k)
    cards_by_id = {card["evidence_id"]: card for card in cards}
    evidence = [
        {
            "evidence_id": item["evidence_id"],
            "content": cards_by_id[item["evidence_id"]]["text"],
            "annotation": {"label": None, "rationale": None, "review_status": "pending_user_review"},
        }
        for item in candidates
    ]
    digest = hashlib.sha256(event["event_id"].encode("utf-8")).hexdigest()[:12].upper()
    return {
        "goldcard_id": f"GC-{digest}",
        "event": {
            "event_id": event["event_id"],
            "duration_seconds": _duration_seconds(event),
            "channel_count": event["channel_count"],
            "scope": event["scope"],
        },
        "evidence": evidence,
        "gold_action_links": [],
    }


def make_drafts(events: list[dict[str, Any]], cards: list[dict[str, Any]], per_stratum: int = 25, top_k: int = 8) -> list[dict[str, Any]]:
    sampled = evenly_spaced_stratified_sample(events, per_stratum)
    ordinals: dict[tuple[str, str], int] = defaultdict(int)
    drafts: list[dict[str, Any]] = []
    for event in sampled:
        key = _stratum(event)
        ordinals[key] += 1
        drafts.append(draft_goldcard(event, cards, top_k, ordinals[key]))
    return drafts


def make_quota_drafts(
    events: list[dict[str, Any]], cards: list[dict[str, Any]], quotas: dict[tuple[str, str], int], top_k: int = 8
) -> list[dict[str, Any]]:
    sampled = quota_stratified_sample(events, quotas)
    ordinals: dict[tuple[str, str], int] = defaultdict(int)
    drafts: list[dict[str, Any]] = []
    for event in sampled:
        key = _stratum(event)
        ordinals[key] += 1
        drafts.append(draft_goldcard(event, cards, top_k, ordinals[key]))
    return drafts


_INITIAL_PROPOSAL_RULES = {
    "on_site_operation_or_calibration_check": "IAEA-TECDOC-1830-2.2.1.3-01",
    "cross_channel_similar_anomaly_comparison": "EPRI-TR-104965-01",
    "signal_transmission_path_check": "ORNL-BWR-NOISE-SIGNATURES-03",
    "short_zero_signal_path": "IAEA-TECDOC-1830-2.2.1.2-01",
}


def add_assistant_initial_proposals(cards: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Add review-required action proposals only when their cited card is frozen.

    These are not gold labels: the reviewer must confirm evidence relevance,
    event applicability, and the availability of the stated check object.
    """
    result: list[dict[str, Any]] = []
    for original in cards:
        card = dict(original)
        candidate_ids = {item["evidence_id"] for item in card["evidence"]}
        event = events_by_id[card["event"]["event_id"]]
        proposals: list[dict[str, Any]] = []
        planned = _INITIAL_PROPOSAL_RULES["on_site_operation_or_calibration_check"]
        if event["event_type"] in {"positive_spike", "negative_drop"} and planned in candidate_ids:
            proposals.append(
                {
                    "action_id": "on_site_operation_or_calibration_check",
                    "evidence_id": planned,
                    "event_facts_used": ["event_type", "time_start", "time_end"],
                    "applicability_condition": "相关通道或系统的测试、维护或校准记录可获得。",
                    "boundary_note": "仅核对时间重叠，不确认事件由测试、维护或校准导致。",
                    "proposal_rationale": "证据说明尖峰/异常点可能与通道检查或校准活动相关。",
                    "annotation_source": "assistant_initial",
                    "review_status": "pending_user_review",
                }
            )
        if event["event_type"] in {"positive_spike", "negative_drop"} and event["scope"] == "single_channel":
            evidence_id = _INITIAL_PROPOSAL_RULES["cross_channel_similar_anomaly_comparison"]
            if evidence_id in candidate_ids:
                proposals.append(
                    {
                        "action_id": "cross_channel_similar_anomaly_comparison",
                        "evidence_id": evidence_id,
                        "event_facts_used": ["event_type", "channels", "time_start", "time_end"],
                        "applicability_condition": "存在测量定义和参考条件已确认可比的传感器或过程估计。",
                        "boundary_note": "比较只能描述一致性或偏差，不能确认具体失效原因。",
                        "proposal_rationale": "证据将在线监测定义为与其他工厂指示的一致性评估。",
                        "annotation_source": "assistant_initial",
                        "review_status": "pending_user_review",
                    }
                )
        if event["scope"] == "multi_channel_temporal_cluster":
            evidence_id = (
                _INITIAL_PROPOSAL_RULES["short_zero_signal_path"]
                if event["event_type"] == "short_zero"
                else _INITIAL_PROPOSAL_RULES["signal_transmission_path_check"]
            )
            if evidence_id in candidate_ids:
                proposals.append(
                    {
                        "action_id": "signal_transmission_path_check",
                        "evidence_id": evidence_id,
                        "event_facts_used": ["event_type", "scope", "channel_count", "time_start", "time_end"],
                        "applicability_condition": "可获得采样、同步、调理或导出配置/记录。",
                        "boundary_note": "多通道时间共现不证明采集或导出过程是异常原因。",
                        "proposal_rationale": (
                            "证据指出传感器数据缺口可由采集错误或通道维护引起。"
                            if event["event_type"] == "short_zero"
                            else "证据描述多通道同步记录、调理和记录质量核查的必要性。"
                        ),
                        "annotation_source": "assistant_initial",
                        "review_status": "pending_user_review",
                    }
                )
        if event["event_type"] == "short_zero":
            evidence_id = _INITIAL_PROPOSAL_RULES["short_zero_signal_path"]
            if evidence_id in candidate_ids:
                proposals.append(
                    {
                        "action_id": "signal_transmission_path_check",
                        "evidence_id": evidence_id,
                        "event_facts_used": ["event_type", "channels", "time_start", "time_end"],
                        "applicability_condition": "可获得通道模式、可用性、报警或功能测试记录。",
                        "boundary_note": "零值/近零读数不确认通道或探测器失效。",
                        "proposal_rationale": "证据将可操作输入和零/近零读数纳入仪表表示充分性的评估。",
                        "annotation_source": "assistant_initial",
                        "review_status": "pending_user_review",
                    }
                )
        card["assistant_initial_proposals"] = proposals
        result.append(card)
    return result


def write_jsonl(cards: list[dict[str, Any]], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(card, ensure_ascii=False, sort_keys=True) + "\n" for card in cards), encoding="utf-8")


def validate_draft(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    event = card.get("event", {})
    required_event_keys = {"event_id", "duration_seconds", "channel_count", "scope"}
    if not required_event_keys <= event.keys():
        errors.append("event must contain event_id, duration_seconds, channel_count, and scope")
    candidate_ids = [item.get("evidence_id") for item in card.get("evidence", [])]
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate evidence IDs must be non-empty and unique")
    for item in card.get("evidence", []):
        if not item.get("content"):
            errors.append("each evidence item must include content")
        annotation = item.get("annotation", {})
        if annotation.get("label") not in {None, "direct_support", "related_but_insufficient", "not_relevant"}:
            errors.append("unknown evidence annotation label")
    for link in card.get("gold_action_links", []):
        if link.get("action_id") not in ACTION_IDS:
            errors.append("unknown action_id")
        link_evidence_ids = link.get("evidence_ids", [])
        if not link_evidence_ids or not set(link_evidence_ids) <= set(candidate_ids):
            errors.append("action link references evidence outside candidate package")
        direct_ids = {
            item["evidence_id"] for item in card.get("evidence", [])
            if item.get("annotation", {}).get("label") == "direct_support"
        }
        if link_evidence_ids and not set(link_evidence_ids) <= direct_ids:
            errors.append("action link must use direct_support evidence")
    for proposal in card.get("assistant_initial_proposals", []):
        if proposal.get("action_id") not in ACTION_IDS:
            errors.append("unknown proposed action_id")
        if proposal.get("evidence_id") not in candidate_ids:
            errors.append("proposal references evidence outside candidate package")
    return errors

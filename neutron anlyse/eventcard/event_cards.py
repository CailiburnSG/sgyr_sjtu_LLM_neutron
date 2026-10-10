"""Build traceable event-card layers from deterministic signal observations.

The pipeline intentionally has three distinct layers:

``atomic observations -> per-channel event cards -> aggregated event cards``.

The first two layers only describe what one channel contains. The final layer
groups temporally adjacent channel cards; it records co-occurrence and never
claims a shared physical cause.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import json
import re

from eventcard.taxonomy import EVENT_SCOPES, EVENT_TAXONOMY_VERSION, EVENT_TYPES, OPERATING_CONTEXTS


SNAPSHOT_TIME_FORMAT = "%m-%d %H:%M:%S"


def _parse_time(value: str) -> datetime:
    """Parse supported timestamps solely for ordering and interval arithmetic."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", SNAPSHOT_TIME_FORMAT):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed if fmt != SNAPSHOT_TIME_FORMAT else parsed.replace(year=2000)
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp: {value!r}")


def _safe_id_part(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-") or "event"


def _normalise_observation(
    *,
    record_id: str,
    event_type: str,
    channel: str,
    time_start: str,
    time_end: str | None = None,
    source: dict[str, Any],
) -> dict[str, Any]:
    """Create one schema-v1, single-channel atomic observation."""
    return {
        "event_taxonomy_version": EVENT_TAXONOMY_VERSION,
        "record_id": record_id,
        "event_type": event_type,
        "channel": channel,
        "time_start": time_start,
        "time_end": time_end or time_start,
        "source": source,
    }


def assign_atomic_ids(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return observations with deterministic identifiers, ordered by channel and time."""
    ordered = sorted(
        observations,
        key=lambda item: (item["record_id"], item["channel"], item["event_type"], _parse_time(item["time_start"])),
    )
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    result: list[dict[str, Any]] = []
    for observation in ordered:
        item = dict(observation)
        key = (item["record_id"], item["channel"], item["event_type"])
        counts[key] += 1
        item["atomic_event_id"] = (
            f"{_safe_id_part(item['record_id'])}-{_safe_id_part(item['channel'])}-"
            f"{item['event_type']}-A{counts[key]:04d}"
        )
        result.append(item)
    return result


def load_zero_observations(snapshot_path: str | Path, record_id: str) -> list[dict[str, Any]]:
    """Read historical snapshot zero timestamps as single-channel observations."""
    snapshot_path = Path(snapshot_path)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Snapshot root must be a list of variable summaries.")

    observations: list[dict[str, Any]] = []
    for variable in payload:
        channel = variable.get("var_name")
        alerts = variable.get("alerts", {})
        if not channel or not isinstance(alerts, dict):
            continue
        for time_text in alerts.get("isolated_zeros", []):
            observations.append(
                _normalise_observation(
                    record_id=record_id,
                    event_type="short_zero",
                    channel=channel,
                    time_start=time_text,
                    source={
                        "kind": "analysis_snapshot",
                        "path": str(snapshot_path),
                        "field": "alerts.isolated_zeros",
                    },
                )
            )
    return assign_atomic_ids(observations)


def _cluster_intervals(items: list[dict[str, Any]], merge_window_seconds: int) -> list[list[dict[str, Any]]]:
    """Cluster ordered intervals when the next start is within the current cluster."""
    clusters: list[list[dict[str, Any]]] = []
    cluster_end: datetime | None = None
    for item in sorted(items, key=lambda value: _parse_time(value["time_start"])):
        start = _parse_time(item["time_start"])
        end = _parse_time(item["time_end"])
        if not clusters or start > cluster_end + timedelta(seconds=merge_window_seconds):
            clusters.append([item])
            cluster_end = end
        else:
            clusters[-1].append(item)
            cluster_end = max(cluster_end, end)
    return clusters


def build_channel_cards(
    observations: list[dict[str, Any]], merge_window_seconds: int = 1
) -> list[dict[str, Any]]:
    """Merge near-adjacent observations within one channel into local event cards."""
    if merge_window_seconds < 0:
        raise ValueError("merge_window_seconds must be non-negative")
    observations = assign_atomic_ids(observations)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[(observation["record_id"], observation["channel"], observation["event_type"])].append(observation)

    cards: list[dict[str, Any]] = []
    for (record_id, channel, event_type), group in grouped.items():
        for ordinal, cluster in enumerate(_cluster_intervals(group, merge_window_seconds), start=1):
            start = min(cluster, key=lambda item: _parse_time(item["time_start"]))["time_start"]
            end = max(cluster, key=lambda item: _parse_time(item["time_end"]))["time_end"]
            cards.append(
                {
                    "channel_card_id": (
                        f"{_safe_id_part(record_id)}-{_safe_id_part(channel)}-{event_type}-C{ordinal:04d}"
                    ),
                    "record_id": record_id,
                    "event_taxonomy_version": EVENT_TAXONOMY_VERSION,
                    "event_type": event_type,
                    "channel": channel,
                    "time_start": start,
                    "time_end": end,
                    "scope": "single_channel",
                    "operating_context": "operation_context_unknown",
                    "context_source": None,
                    "observed_facts": [f"通道 {channel} 在 {start} 至 {end} 出现 {event_type} 观测。"],
                    "source_atomic_event_ids": [item["atomic_event_id"] for item in cluster],
                    "provenance": {
                        "merge_window_seconds": merge_window_seconds,
                        "atomic_observation_count": len(cluster),
                    },
                    "limitations": ["该卡片仅记录单通道数据现象，不能确认失效机理或因果关系。"],
                }
            )
    return sorted(cards, key=lambda item: (item["record_id"], _parse_time(item["time_start"]), item["channel_card_id"]))


def aggregate_channel_cards(
    channel_cards: list[dict[str, Any]], merge_window_seconds: int = 1
) -> list[dict[str, Any]]:
    """Group adjacent same-type channel cards into overall event cards."""
    if merge_window_seconds < 0:
        raise ValueError("merge_window_seconds must be non-negative")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in channel_cards:
        grouped[(card["record_id"], card["event_type"])].append(card)

    aggregated: list[dict[str, Any]] = []
    for (record_id, event_type), group in grouped.items():
        for ordinal, cluster in enumerate(_cluster_intervals(group, merge_window_seconds), start=1):
            channels = sorted({item["channel"] for item in cluster})
            start = min(cluster, key=lambda item: _parse_time(item["time_start"]))["time_start"]
            end = max(cluster, key=lambda item: _parse_time(item["time_end"]))["time_end"]
            scope = "multi_channel_temporal_cluster" if len(channels) > 1 else "single_channel"
            aggregated.append(
                {
                    "event_id": f"{_safe_id_part(record_id)}-{event_type}-E{ordinal:04d}",
                    "record_id": record_id,
                    "event_taxonomy_version": EVENT_TAXONOMY_VERSION,
                    "event_type": event_type,
                    "time_start": start,
                    "time_end": end,
                    "channels": channels,
                    "channel_count": len(channels),
                    "scope": scope,
                    "operating_context": "operation_context_unknown",
                    "context_source": None,
                    "observed_facts": [
                        f"在 {merge_window_seconds} 秒聚合窗口内，{len(channels)} 个通道出现 {event_type} 观测。"
                    ],
                    "source_channel_card_ids": [item["channel_card_id"] for item in cluster],
                    "provenance": {
                        "merge_window_seconds": merge_window_seconds,
                        "channel_card_count": len(cluster),
                        "atomic_observation_count": sum(
                            item["provenance"]["atomic_observation_count"] for item in cluster
                        ),
                    },
                    "limitations": ["该卡片仅记录跨通道时间共现，不能据此确认共同失效机理或因果关系。"],
                }
            )
    return sorted(aggregated, key=lambda item: (item["record_id"], _parse_time(item["time_start"]), item["event_id"]))


def aggregate_observations(
    observations: list[dict[str, Any]], merge_window_seconds: int = 1
) -> list[dict[str, Any]]:
    """Compatibility wrapper returning final cards after both aggregation layers."""
    return aggregate_channel_cards(build_channel_cards(observations, merge_window_seconds), merge_window_seconds)


def _validate_items(items: list[dict[str, Any]], required: set[str], id_field: str, label: str) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        missing = required.difference(item)
        if missing:
            errors.append(f"{label}[{index}] missing fields: {sorted(missing)}")
            continue
        item_id = item[id_field]
        if item_id in seen:
            errors.append(f"duplicate {id_field}: {item_id}")
        seen.add(item_id)
        try:
            if _parse_time(item["time_end"]) < _parse_time(item["time_start"]):
                errors.append(f"{item_id} ends before it starts")
        except ValueError as exc:
            errors.append(f"{item_id} has invalid time: {exc}")
    return errors


def validate_atomic_observations(observations: list[dict[str, Any]]) -> list[str]:
    required = {"atomic_event_id", "record_id", "event_type", "channel", "time_start", "time_end", "source"}
    errors = _validate_items(observations, required, "atomic_event_id", "atomic observation")
    for observation in observations:
        if observation.get("event_type") not in EVENT_TYPES:
            errors.append(f"{observation.get('atomic_event_id', '<unknown>')} has unsupported event type")
    return errors


def validate_channel_cards(cards: list[dict[str, Any]]) -> list[str]:
    required = {
        "channel_card_id", "record_id", "event_type", "channel", "time_start", "time_end",
        "source_atomic_event_ids", "provenance", "operating_context", "context_source",
    }
    errors = _validate_items(cards, required, "channel_card_id", "channel card")
    for card in cards:
        if card.get("event_type") not in EVENT_TYPES:
            errors.append(f"{card.get('channel_card_id', '<unknown>')} has unsupported event type")
        if card.get("scope") not in EVENT_SCOPES:
            errors.append(f"{card.get('channel_card_id', '<unknown>')} has unsupported scope")
        if card.get("operating_context") not in OPERATING_CONTEXTS:
            errors.append(f"{card.get('channel_card_id', '<unknown>')} has unsupported operating context")
    return errors


def validate_cards(cards: list[dict[str, Any]]) -> list[str]:
    required = {
        "event_id", "record_id", "event_type", "time_start", "time_end", "channels", "scope",
        "source_channel_card_ids", "provenance", "operating_context", "context_source",
    }
    errors = _validate_items(cards, required, "event_id", "event card")
    for card in cards:
        if card.get("scope") not in EVENT_SCOPES:
            errors.append(f"{card.get('event_id', '<unknown>')} has unsupported scope")
        if card.get("event_type") not in EVENT_TYPES:
            errors.append(f"{card.get('event_id', '<unknown>')} has unsupported event type")
        if card.get("operating_context") not in OPERATING_CONTEXTS:
            errors.append(f"{card.get('event_id', '<unknown>')} has unsupported operating context")
        if card.get("operating_context", "").endswith("_confirmed") and not card.get("context_source"):
            errors.append(f"{card.get('event_id', '<unknown>')} has confirmed operating context without source")
    return errors


def write_json(items: list[dict[str, Any]], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def write_cards(cards: list[dict[str, Any]], output_path: str | Path) -> None:
    """Compatibility name for writing final aggregated event cards."""
    write_json(cards, output_path)

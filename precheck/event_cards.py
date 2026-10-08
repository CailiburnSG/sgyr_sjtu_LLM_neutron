"""Build auditable pre-screening event cards from existing analysis snapshots.

The snapshot is an input artifact, not a source of diagnosis.  This module only
records observable phenomena and their provenance; it never assigns a physical
failure mechanism.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import re


SNAPSHOT_TIME_FORMAT = "%m-%d %H:%M:%S"


def _parse_snapshot_time(value: str) -> datetime:
    """Parse a snapshot timestamp for ordering without inventing a real year."""
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", SNAPSHOT_TIME_FORMAT):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed if fmt != SNAPSHOT_TIME_FORMAT else parsed.replace(year=2000)
        except ValueError:
            continue
    raise ValueError(f"Unsupported snapshot timestamp: {value!r}")


def _safe_id_part(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-") or "event"


def load_zero_observations(snapshot_path: str | Path, record_id: str) -> list[dict[str, Any]]:
    """Expand every timestamp in ``isolated_zeros`` into one atomic observation."""
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
                {
                    "record_id": record_id,
                    "event_type": "isolated_zero",
                    "channel": channel,
                    "time_text": time_text,
                    "time_order": _parse_snapshot_time(time_text).isoformat(),
                    "source": {
                        "kind": "analysis_snapshot",
                        "path": str(snapshot_path),
                        "field": "alerts.isolated_zeros",
                    },
                }
            )
    return observations


def aggregate_observations(
    observations: list[dict[str, Any]], merge_window_seconds: int = 1
) -> list[dict[str, Any]]:
    """Merge same-record, same-type observations occurring in one time window.

    A card represents an observation cluster.  It does not assert that a
    multi-channel cluster has a common physical cause.
    """
    if merge_window_seconds < 0:
        raise ValueError("merge_window_seconds must be non-negative")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[(observation["record_id"], observation["event_type"])].append(observation)

    cards: list[dict[str, Any]] = []
    for (record_id, event_type), group in grouped.items():
        ordered = sorted(group, key=lambda item: item["time_order"])
        clusters: list[list[dict[str, Any]]] = []
        for observation in ordered:
            now = datetime.fromisoformat(observation["time_order"])
            if not clusters:
                clusters.append([observation])
                continue
            last = datetime.fromisoformat(clusters[-1][-1]["time_order"])
            if (now - last).total_seconds() <= merge_window_seconds:
                clusters[-1].append(observation)
            else:
                clusters.append([observation])

        for ordinal, cluster in enumerate(clusters, start=1):
            channels = sorted({item["channel"] for item in cluster})
            start, end = cluster[0], cluster[-1]
            scope = "multi_channel_synchronous" if len(channels) > 1 else "single_channel"
            source_kinds = {item.get("source", {}).get("kind") for item in cluster}
            time_precision = "timestamp" if source_kinds == {"csv_detector"} else "snapshot_timestamp"
            cards.append(
                {
                    "event_id": f"{_safe_id_part(record_id)}-{event_type}-{ordinal:04d}",
                    "record_id": record_id,
                    "event_type": event_type,
                    "time_start": start["time_text"],
                    "time_end": end["time_text"],
                    "time_precision": time_precision,
                    "channels": channels,
                    "channel_count": len(channels),
                    "scope": scope,
                    "observed_facts": [
                        f"在 {merge_window_seconds} 秒合并窗口内，"
                        f"{len(channels)} 个通道出现了 {event_type} 观测。"
                    ],
                    "provenance": {
                        "merge_window_seconds": merge_window_seconds,
                        "atomic_observation_count": len(cluster),
                        "atomic_observations": cluster,
                    },
                    "limitations": [
                        "该卡片仅记录数据观测，不能据此确认失效机理或因果关系。",
                        "快照时间戳可能缺少年份；记录编号与来源溯源信息共同构成事件身份。",
                    ],
                }
            )
    return sorted(cards, key=lambda item: (item["record_id"], item["time_start"], item["event_id"]))


def validate_cards(cards: list[dict[str, Any]]) -> list[str]:
    """Return validation errors; an empty list means the cards meet the v1 schema."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    required = {"event_id", "record_id", "event_type", "time_start", "channels", "scope", "provenance"}
    for index, card in enumerate(cards):
        missing = required.difference(card)
        if missing:
            errors.append(f"card[{index}] missing fields: {sorted(missing)}")
            continue
        if card["event_id"] in seen_ids:
            errors.append(f"duplicate event_id: {card['event_id']}")
        seen_ids.add(card["event_id"])
        if not card["channels"]:
            errors.append(f"{card['event_id']} has no channels")
        if card["scope"] not in {"single_channel", "multi_channel_synchronous"}:
            errors.append(f"{card['event_id']} has unsupported scope: {card['scope']}")
    return errors


def write_cards(cards: list[dict[str, Any]], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

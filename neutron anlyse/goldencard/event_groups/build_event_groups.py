"""Materialize the eight fixed 10-case goldencard event-group templates."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import json

from goldencard.workflow import evenly_spaced_stratified_sample


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
OUTPUT = ROOT
GROUPS = (
    ("short_zero", "single_channel"),
    ("short_zero", "multi_channel_temporal_cluster"),
    ("sustained_zero", "single_channel"),
    ("sustained_zero", "multi_channel_temporal_cluster"),
    ("positive_spike", "single_channel"),
    ("positive_spike", "multi_channel_temporal_cluster"),
    ("negative_drop", "single_channel"),
    ("negative_drop", "multi_channel_temporal_cluster"),
)
CHANNELS = [f"SYN.RIC.{number:04d}" for number in range(1011, 1018)]


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _filename(event_type: str, scope: str) -> str:
    return f"{event_type}__{scope}.json"


def _observed(event_type: str, scope: str) -> list[dict]:
    paths = [REPO / "eventcard/output/A1_1_aggregated_cards.json", REPO / "eventcard/output/A1_1_snapshot_aggregated_cards.json"]
    available = [event for path in paths for event in _read(path) if event["event_type"] == event_type and event["scope"] == scope]
    if len(available) < 10:
        return []
    selected = evenly_spaced_stratified_sample(available, 10)
    return [deepcopy(event) for event in selected]


def _template(event_type: str, scope: str) -> list[dict]:
    cards = []
    base = datetime(2030, 1, 1)
    for ordinal in range(1, 11):
        start = base + timedelta(minutes=ordinal * 7)
        if event_type == "short_zero":
            samples, duration = 1 + ordinal % 2, 1 + ordinal % 2
        else:
            samples, duration = 4 + ordinal, 4 + ordinal
        count = 1 if scope == "single_channel" else 2 + ordinal % 4
        channels = [CHANNELS[(ordinal + offset) % len(CHANNELS)] for offset in range(count)]
        end = start + timedelta(seconds=duration - 1)
        cards.append(
            {
                "event_id": f"SYN-{event_type}-{scope}-E{ordinal:04d}",
                "record_id": "goldencard_template_v1",
                "event_taxonomy_version": "v1",
                "event_type": event_type,
                "time_start": start.isoformat(sep=" "),
                "time_end": end.isoformat(sep=" "),
                "channels": channels,
                "channel_count": count,
                "scope": scope,
                "operating_context": "operation_context_unknown",
                "context_source": None,
                "observed_facts": [
                    f"模板事件：{count} 个通道在 {start.isoformat(sep=' ')} 至 {end.isoformat(sep=' ')} 出现 {event_type} 观测。"
                ],
                "source_channel_card_ids": [f"SYN-{event_type}-{scope}-C{ordinal:04d}-{index:02d}" for index in range(1, count + 1)],
                "provenance": {
                    "kind": "gold_standard_template",
                    "template_version": "v1",
                    "run_samples": samples,
                    "duration_seconds": duration,
                },
                "limitations": [
                    "该卡只记录可观测事件状态，不确认失效机理或因果关系。",
                ],
            }
        )
    return cards


def main() -> None:
    manifest = {"group_version": "v1", "groups": []}
    for event_type, scope in GROUPS:
        cards = _observed(event_type, scope) or _template(event_type, scope)
        destination = OUTPUT / _filename(event_type, scope)
        destination.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["groups"].append({"event_type": event_type, "scope": scope, "count": len(cards), "path": str(destination.relative_to(REPO))})
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

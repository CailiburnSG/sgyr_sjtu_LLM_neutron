"""Command line entry points for the event-card pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eventcard.csv_events import extract_csv_observations
from eventcard.event_cards import (
    aggregate_channel_cards,
    build_channel_cards,
    load_zero_observations,
    validate_atomic_observations,
    validate_cards,
    validate_channel_cards,
    write_json,
)
from eventcard.reporting import render_template_report


def _write_layers(observations: list[dict], args: argparse.Namespace) -> int:
    channel_cards = build_channel_cards(observations, args.channel_merge_window_seconds)
    cards = aggregate_channel_cards(channel_cards, args.aggregate_window_seconds)
    errors = (
        validate_atomic_observations(observations)
        + validate_channel_cards(channel_cards)
        + validate_cards(cards)
    )
    if errors:
        raise SystemExit("Event-card validation failed:\n" + "\n".join(errors))
    write_json(observations, args.atomic_output)
    write_json(channel_cards, args.channel_cards_output)
    write_json(cards, args.output)
    print(
        json.dumps(
            {
                "atomic_observations": len(observations),
                "channel_cards": len(channel_cards),
                "event_cards": len(cards),
                "outputs": {
                    "atomic": args.atomic_output,
                    "channel_cards": args.channel_cards_output,
                    "event_cards": args.output,
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_cards(args: argparse.Namespace) -> int:
    return _write_layers(load_zero_observations(args.snapshot, args.record_id), args)


def build_cards_from_csv(args: argparse.Namespace) -> int:
    observations = extract_csv_observations(
        args.csv,
        args.record_id,
        zero_tolerance=args.zero_tolerance,
        max_isolated_zero_samples=args.max_isolated_zero_samples,
        spike_window=args.spike_window,
        spike_mad_multiplier=args.spike_mad_multiplier,
        spike_range_fraction=args.spike_range_fraction,
    )
    return _write_layers(observations, args)


def validate(args: argparse.Namespace) -> int:
    cards = json.loads(Path(args.cards).read_text(encoding="utf-8"))
    errors = validate_cards(cards)
    print(json.dumps({"cards": len(cards), "valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def render(args: argparse.Namespace) -> int:
    cards = json.loads(Path(args.cards).read_text(encoding="utf-8"))
    selected = [card for card in cards if not args.event_id or card["event_id"] == args.event_id]
    if not selected:
        raise SystemExit("No matching event card found.")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n---\n\n".join(render_template_report(card) for card in selected), encoding="utf-8")
    print(json.dumps({"reports": len(selected), "output": str(output)}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Neutron-current event-card pipeline")
    sub = root.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-cards", help="Build all three event-card layers from a historical snapshot")
    build.add_argument("--snapshot", required=True)
    build.add_argument("--record-id", required=True)
    _add_layer_outputs(build)
    build.set_defaults(func=build_cards)

    csv = sub.add_parser("build-cards-from-csv", help="Extract and write all three event-card layers from a CSV")
    csv.add_argument("--csv", required=True)
    csv.add_argument("--record-id", required=True)
    _add_layer_outputs(csv)
    csv.add_argument("--zero-tolerance", type=float, default=0.0)
    csv.add_argument("--max-isolated-zero-samples", type=int, default=2)
    csv.add_argument("--spike-window", type=int, default=31)
    csv.add_argument("--spike-mad-multiplier", type=float, default=5.0)
    csv.add_argument("--spike-range-fraction", type=float, default=0.05)
    csv.set_defaults(func=build_cards_from_csv)

    check = sub.add_parser("validate-cards", help="Validate an event-card JSON file")
    check.add_argument("--cards", required=True)
    check.set_defaults(func=validate)

    report = sub.add_parser("render-template", help="Render deterministic pre-screening report(s)")
    report.add_argument("--cards", required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--event-id")
    report.set_defaults(func=render)
    return root


def _add_layer_outputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("--atomic-output", required=True, help="Unified single-channel atomic-event table")
    command.add_argument("--channel-cards-output", required=True, help="Per-channel event-card table")
    command.add_argument("--output", required=True, help="Cross-channel aggregated event-card table")
    command.add_argument("--channel-merge-window-seconds", type=int, default=1)
    command.add_argument("--aggregate-window-seconds", type=int, default=1)


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

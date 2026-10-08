"""Command line entry points for the pre-screening pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from precheck.csv_events import extract_csv_observations
from precheck.event_cards import aggregate_observations, load_zero_observations, validate_cards, write_cards
from precheck.reporting import render_template_report


def build_cards(args: argparse.Namespace) -> int:
    observations = load_zero_observations(args.snapshot, args.record_id)
    cards = aggregate_observations(observations, args.merge_window_seconds)
    errors = validate_cards(cards)
    if errors:
        raise SystemExit("Event-card validation failed:\n" + "\n".join(errors))
    write_cards(cards, args.output)
    print(json.dumps({"atomic_observations": len(observations), "event_cards": len(cards), "output": args.output}, ensure_ascii=False))
    return 0


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
    cards = aggregate_observations(observations, args.merge_window_seconds)
    errors = validate_cards(cards)
    if errors:
        raise SystemExit("Event-card validation failed:\n" + "\n".join(errors))
    write_cards(cards, args.output)
    counts: dict[str, int] = {}
    for observation in observations:
        counts[observation["event_type"]] = counts.get(observation["event_type"], 0) + 1
    print(json.dumps({"atomic_observations": counts, "event_cards": len(cards), "output": args.output}, ensure_ascii=False))
    return 0


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
    root = argparse.ArgumentParser(description="Neutron-current pre-screening pipeline")
    sub = root.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-cards", help="Build v1 zero-observation event cards from a snapshot")
    build.add_argument("--snapshot", required=True)
    build.add_argument("--record-id", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--merge-window-seconds", type=int, default=1)
    build.set_defaults(func=build_cards)

    csv = sub.add_parser("build-cards-from-csv", help="Extract v1 observations from a CSV and build event cards")
    csv.add_argument("--csv", required=True)
    csv.add_argument("--record-id", required=True)
    csv.add_argument("--output", required=True)
    csv.add_argument("--merge-window-seconds", type=int, default=1)
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


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

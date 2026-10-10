"""Build and validate frozen goldencard annotation drafts."""

from __future__ import annotations

import argparse
import json

from evidencecard.workflow import load_cards, read_jsonl
from goldencard.workflow import add_assistant_initial_proposals, load_events, make_drafts, make_quota_drafts, validate_draft, write_jsonl


def build(args: argparse.Namespace) -> int:
    events = []
    for event_path in args.events:
        for event in load_events(event_path):
            item = dict(event)
            item["goldcard_event_source"] = event_path
            events.append(item)
    cards = load_cards(args.cards, args.catalog)
    quotas = None
    if args.sampling_plan:
        plan = json.loads(open(args.sampling_plan, encoding="utf-8").read())
        quotas = {(item["event_type"], item["scope"]): item["count"] for item in plan["strata"]}
    drafts = make_quota_drafts(events, cards, quotas, args.top_k) if quotas else make_drafts(events, cards, args.per_stratum, args.top_k)
    errors = [error for draft in drafts for error in validate_draft(draft)]
    if errors:
        raise SystemExit("Draft validation failed:\n" + "\n".join(errors))
    write_jsonl(drafts, args.output)
    print(json.dumps({"draft_cards": len(drafts), "quotas": bool(quotas), "per_stratum": args.per_stratum if not quotas else None, "top_k": args.top_k, "output": args.output}, ensure_ascii=False))
    return 0


def validate(args: argparse.Namespace) -> int:
    cards = read_jsonl(args.cards)
    errors = {card.get("goldcard_id", "unknown"): validate_draft(card) for card in cards}
    errors = {key: value for key, value in errors.items() if value}
    print(json.dumps({"cards": len(cards), "valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def propose(args: argparse.Namespace) -> int:
    events = {event["event_id"]: event for path in args.events for event in load_events(path)}
    cards = add_assistant_initial_proposals(read_jsonl(args.cards), events)
    errors = [error for card in cards for error in validate_draft(card)]
    if errors:
        raise SystemExit("Proposal validation failed:\n" + "\n".join(errors))
    write_jsonl(cards, args.output)
    print(json.dumps({"cards": len(cards), "proposals": sum(len(card.get("assistant_initial_proposals", [])) for card in cards), "output": args.output}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="goldencard draft workflow")
    sub = root.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("build-drafts", help="freeze event-stratified candidate evidence packages")
    draft.add_argument("--events", required=True, nargs="+")
    draft.add_argument("--cards", required=True, nargs="+")
    draft.add_argument("--catalog")
    draft.add_argument("--output", required=True)
    draft.add_argument("--per-stratum", type=int, default=25)
    draft.add_argument("--sampling-plan", help="JSON file containing explicit event_type × scope quotas")
    draft.add_argument("--top-k", type=int, default=8)
    draft.set_defaults(func=build)
    check = sub.add_parser("validate", help="validate goldencard drafts or confirmed cards")
    check.add_argument("--cards", required=True)
    check.set_defaults(func=validate)
    proposal = sub.add_parser("add-assistant-proposals", help="add review-required initial event-evidence-action proposals")
    proposal.add_argument("--cards", required=True)
    proposal.add_argument("--events", required=True, nargs="+", help="event-group JSON files used to resolve event_id")
    proposal.add_argument("--output", required=True)
    proposal.set_defaults(func=propose)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

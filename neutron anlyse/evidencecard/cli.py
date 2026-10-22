"""CLI for controlled event--evidence candidate packages and report contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidencecard.workflow import (build_llm_contract, build_sampling_plan, candidate_case, load_cards, read_jsonl,
                                   select_candidate_events, stable_case_id, validate_llm_report, write_jsonl)


def _events(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Event-card input must be a JSON array.")
    return payload


def plan(args: argparse.Namespace) -> int:
    print(json.dumps(build_sampling_plan(_events(args.events), args.target), ensure_ascii=False, indent=2))
    return 0


def make_cases(args: argparse.Namespace) -> int:
    cards = load_cards(args.cards, args.catalog)
    events = select_candidate_events(_events(args.events), args.target)
    cases = [candidate_case(stable_case_id(event["event_id"]), event, cards, args.top_k) for event in events]
    write_jsonl(cases, args.output)
    print(json.dumps({"candidate_packages": len(cases), "status": "pending_human_review", "output": args.output}, ensure_ascii=False))
    return 0


def contract(args: argparse.Namespace) -> int:
    cases = {case["event_id"]: case for case in read_jsonl(args.cases)}
    if args.event_id not in cases:
        raise SystemExit("No matching event_id in case file.")
    evidence = {card["evidence_id"]: card for card in load_cards(args.cards, args.catalog)}
    links = read_jsonl(args.links)
    payload = build_llm_contract(cases[args.event_id], evidence, links)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event_id": args.event_id, "confirmed_direct_evidence": len(payload["evidence"]), "output": args.output}, ensure_ascii=False))
    return 0


def validate_report(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    contract_payload = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    errors = validate_llm_report(report, contract_payload)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Controlled event--evidence workflow")
    sub = root.add_subparsers(dest="command", required=True)
    sample = sub.add_parser("sampling-plan", help="inspect feasibility of the 100-case stratified plan")
    sample.add_argument("--events", required=True); sample.add_argument("--target", type=int, default=100); sample.set_defaults(func=plan)
    cases = sub.add_parser("make-candidate-cases", help="freeze retrieval candidates; no relevance labels are generated")
    cases.add_argument("--events", required=True); cases.add_argument("--cards", required=True, nargs="+"); cases.add_argument("--catalog"); cases.add_argument("--output", required=True); cases.add_argument("--target", type=int, default=100); cases.add_argument("--top-k", type=int, default=8); cases.set_defaults(func=make_cases)
    prompt = sub.add_parser("build-llm-contract", help="build a bounded LLM input from confirmed direct-support links")
    prompt.add_argument("--cases", required=True); prompt.add_argument("--cards", required=True, nargs="+"); prompt.add_argument("--catalog"); prompt.add_argument("--links", required=True); prompt.add_argument("--event-id", required=True); prompt.add_argument("--output", required=True); prompt.set_defaults(func=contract)
    check = sub.add_parser("validate-llm-report", help="validate citations and boundary rules in structured LLM output")
    check.add_argument("--contract", required=True); check.add_argument("--report", required=True); check.set_defaults(func=validate_report)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

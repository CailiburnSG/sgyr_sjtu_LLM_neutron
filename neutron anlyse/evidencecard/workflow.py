"""Controlled retrieval, review-case construction, and report-contract checks.

This module intentionally does not infer a fault.  It turns an observable event
card into a versioned query, retrieves *candidate* evidence cards, and keeps the
human review decision separate from retrieval and generation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from math import log
from pathlib import Path
from typing import Any
import hashlib
import json
import re


QUERY_MAPPING_VERSION = "v1"
RETRIEVER_VERSION = "lexical_bm25_v1"
LABELS = {"direct_support", "related_but_insufficient", "not_relevant"}

_EVENT_QUERY = {
    "short_zero": (["brief zero output", "signal dropout", "missing signal"], ["missing_data_check"]),
    "sustained_zero": (["sustained zero output", "signal loss", "channel availability"], ["missing_data_check", "stuck_signal_screening"]),
    "positive_spike": (["positive transient spike", "signal transient", "abnormal fluctuation"], ["spike_data_qualification", "data_qualification", "calibration_activity_check"]),
    "negative_drop": (["negative transient drop", "signal transient", "abnormal fluctuation"], ["spike_data_qualification", "data_qualification", "historian_sampling_check"]),
    "upward_trend": (["sustained rise", "increasing trend", "signal drift"], ["baseline_reference_selection", "signal_quality_context"]),
    "downward_trend": (["sustained fall", "decreasing trend", "signal drift"], ["baseline_reference_selection", "signal_quality_context"]),
    "transient_deviation": (["signal transient", "temporary deviation", "abnormal fluctuation"], ["data_qualification", "signal_quality_context"]),
}
_SCOPE_QUERY = {
    "single_channel": ["single channel", "channel comparison"],
    "multi_channel_temporal_cluster": ["multiple channels", "temporal cluster", "data acquisition"],
}
_TOKEN = re.compile(r"[a-z0-9]+")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(items: list[dict[str, Any]], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items), encoding="utf-8")


def load_cards(paths: list[str | Path], catalog_path: str | Path | None = None) -> list[dict[str, Any]]:
    cards = [card for path in paths for card in read_jsonl(path)]
    # Manual cards retain source identity; some document-level applicability is
    # deliberately held in the catalog. Merge it at read time, not by editing
    # the reviewed 300-card corpus.
    catalog = {entry["doc_id"]: entry for entry in read_jsonl(catalog_path)} if catalog_path else {}
    inherited = ("measurement_scope", "neutron_current_relevance", "transfer_note", "scope_note")
    for card in cards:
        source = catalog.get(card.get("doc_id"), {})
        for field in inherited:
            if card.get(field) is None and field in source:
                card[field] = source[field]
    ids = [card.get("evidence_id") for card in cards]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Evidence cards require unique non-empty evidence_id values.")
    return cards


def build_query(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("event_type")
    scope = event.get("scope")
    if event_type not in _EVENT_QUERY or scope not in _SCOPE_QUERY:
        raise ValueError("Unsupported event_type or scope for controlled retrieval.")
    patterns, applicability = _EVENT_QUERY[event_type]
    terms = ["neutron current", "nuclear instrumentation", *patterns, *_SCOPE_QUERY[scope], "online monitoring", "data quality", "verification"]
    return {
        "query_id": "Q-" + event["event_id"],
        "event_id": event["event_id"],
        "query_text": " ".join(terms),
        "event_facts": {key: event.get(key) for key in ("event_type", "scope", "channel_count", "time_start", "time_end")},
        "filters": {"source_tier": ["core", "domain"], "preferred_applicability": applicability},
        "mapping_version": QUERY_MAPPING_VERSION,
    }


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def rank_candidates(query: dict[str, Any], cards: list[dict[str, Any]], top_k: int = 8) -> list[dict[str, Any]]:
    """Return a deterministic BM25 candidate package, never a relevance label."""
    usable = [card for card in cards if card.get("source_tier") in query["filters"]["source_tier"]]
    documents = [_tokens(" ".join([card.get("text", ""), " ".join(card.get("topic_tags", [])), " ".join(card.get("applicability", []))])) for card in usable]
    df = Counter(token for doc in documents for token in set(doc))
    q_tokens = _tokens(query["query_text"])
    average_length = sum(map(len, documents)) / max(1, len(documents))
    preferred = set(query["filters"]["preferred_applicability"])
    scored: list[tuple[float, dict[str, Any]]] = []
    for card, document in zip(usable, documents):
        freq = Counter(document)
        score = 0.0
        for token in q_tokens:
            if token in freq:
                idf = log(1 + (len(documents) - df[token] + 0.5) / (df[token] + 0.5))
                score += idf * freq[token] * 2.2 / (freq[token] + 1.2 * (0.25 + 0.75 * len(document) / average_length))
        score += 0.15 * len(preferred.intersection(card.get("applicability", [])))
        if card.get("neutron_current_relevance") == "direct":
            score += 0.10
        scored.append((score, card))
    return [{"evidence_id": card["evidence_id"], "rank": index, "score": round(score, 6)} for index, (score, card) in enumerate(sorted(scored, key=lambda item: (-item[0], item[1]["evidence_id"]))[:top_k], 1)]


def candidate_case(case_id: str, event: dict[str, Any], cards: list[dict[str, Any]], top_k: int = 8) -> dict[str, Any]:
    query = build_query(event)
    candidates = rank_candidates(query, cards, top_k)
    return {
        "case_id": case_id,
        "case_status": "candidate_package_pending_human_review",
        "event_id": event["event_id"],
        "event_snapshot": event,
        "retrieval_request": query,
        "candidate_evidence": candidates,
        "annotations": [
            {"evidence_id": item["evidence_id"], "label": None, "evidence_role": None,
             "supported_precheck_statement": None, "boundary_note": None, "review_status": "pending_user_review"}
            for item in candidates
        ],
        "retriever_version": RETRIEVER_VERSION,
    }


def _duration_seconds(event: dict[str, Any]) -> float:
    parse = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    return max(0.0, (parse(event["time_end"]) - parse(event["time_start"])).total_seconds())


def build_sampling_plan(events: list[dict[str, Any]], target: int = 100) -> dict[str, Any]:
    """Plan a balanced candidate set without inventing absent event strata."""
    desired = [(event_type, scope) for event_type in _EVENT_QUERY for scope in _SCOPE_QUERY]
    observed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if (event.get("event_type"), event.get("scope")) in desired:
            observed[(event["event_type"], event["scope"])].append(event)
    allocation = {"%s|%s" % key: target // len(desired) + (index < target % len(desired)) for index, key in enumerate(desired)}
    availability = {"%s|%s" % key: len(observed[key]) for key in desired}
    return {"target_cases": target, "strata": allocation, "available_events": availability,
            "missing_strata": [key for key, value in availability.items() if value == 0],
            "rule": "Use only as a candidate-package plan; do not call reviewed cases gold standard until every candidate annotation is confirmed."}


def select_candidate_events(events: list[dict[str, Any]], target: int = 100) -> list[dict[str, Any]]:
    plan = build_sampling_plan(events, target)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[f"{event.get('event_type')}|{event.get('scope')}"] .append(event)
    for bucket in grouped.values():
        bucket.sort(key=lambda event: (event.get("record_id", ""), event["time_start"], event["event_id"]))
    selected: list[dict[str, Any]] = []
    # Round-robin prevents one high-frequency stratum from silently taking all cases.
    active = [key for key, items in grouped.items() if items]
    positions = Counter()
    while len(selected) < target and active:
        next_active = []
        for key in active:
            quota = plan["strata"].get(key, 0)
            if positions[key] < len(grouped[key]) and sum(1 for item in selected if f"{item['event_type']}|{item['scope']}" == key) < quota:
                selected.append(grouped[key][positions[key]])
                positions[key] += 1
            if positions[key] < len(grouped[key]) and sum(1 for item in selected if f"{item['event_type']}|{item['scope']}" == key) < quota:
                next_active.append(key)
            if len(selected) == target:
                break
        active = next_active
    # A pilot may lack whole strata.  Backfill only its *candidate* packages so
    # reviewers can exercise the workflow; the sampling plan still records why
    # this set is ineligible to be called the final stratified gold standard.
    active = [key for key, items in grouped.items() if positions[key] < len(items)]
    while len(selected) < target and active:
        next_active = []
        for key in active:
            selected.append(grouped[key][positions[key]])
            positions[key] += 1
            if positions[key] < len(grouped[key]):
                next_active.append(key)
            if len(selected) == target:
                break
        active = next_active
    return selected


def validate_review_case(case: dict[str, Any], require_confirmed: bool = False) -> list[str]:
    errors: list[str] = []
    candidate_ids = [item["evidence_id"] for item in case.get("candidate_evidence", [])]
    if not case.get("event_id") or not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        errors.append("case needs an event_id and unique fixed candidate evidence")
    for annotation in case.get("annotations", []):
        if annotation.get("evidence_id") not in candidate_ids:
            errors.append("annotation evidence_id is not in fixed candidate package")
        if annotation.get("label") is not None and annotation["label"] not in LABELS:
            errors.append("invalid annotation label")
        if require_confirmed and (annotation.get("review_status") != "confirmed" or annotation.get("label") not in LABELS):
            errors.append("gold-standard case contains unconfirmed annotation")
    if require_confirmed and case.get("case_status") != "gold_standard_confirmed":
        errors.append("gold-standard case must be explicitly marked gold_standard_confirmed")
    return errors


def build_llm_contract(case: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]], confirmed_links: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a bounded model input from confirmed direct-support links only."""
    event_id = case["event_id"]
    usable = [link for link in confirmed_links if link.get("event_id") == event_id and link.get("label") == "direct_support" and link.get("review_status") == "confirmed"]
    evidence = []
    for link in usable:
        card = evidence_by_id.get(link["evidence_id"])
        if card:
            evidence.append({"evidence_id": card["evidence_id"], "text": card["text"], "section_path": card.get("section_path", []),
                             "markdown_lines": [card.get("markdown_line_start"), card.get("markdown_line_end")],
                             "source_tier": card.get("source_tier"), "neutron_current_relevance": card.get("neutron_current_relevance"),
                             "transfer_note": card.get("transfer_note"), "allowed_statement": link.get("supported_precheck_statement"), "boundary_note": link.get("boundary_note")})
    return {"contract_version": "v1", "event": case["event_snapshot"], "evidence": evidence,
            "required_output_schema": {"event_id": "string", "observed_facts": ["string"], "evidence_based_notes": [{"statement": "string", "evidence_ids": ["string"]}], "recommended_checks": [{"action": "string", "evidence_ids": ["string"]}], "unconfirmed": ["string"]},
            "instructions": ["Describe observations only from event fields.", "Use only supplied evidence IDs.", "Each note/check must cite supplied evidence.", "Do not diagnose a fault, confirm a mechanism, infer causality, or invent values.", "When evidence is empty, state that evidence is insufficient for a specific recommendation."]}


def validate_llm_report(report: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("event_id") != contract["event"]["event_id"]:
        errors.append("event_id does not match input event")
    allowed = {item["evidence_id"] for item in contract["evidence"]}
    cited: set[str] = set()
    for field in ("evidence_based_notes", "recommended_checks"):
        for item in report.get(field, []):
            ids = item.get("evidence_ids", [])
            if not ids:
                errors.append(f"{field} item has no evidence citation")
            cited.update(ids)
    if not cited.issubset(allowed):
        errors.append("report cites evidence outside the confirmed evidence package")
    joined = json.dumps(report, ensure_ascii=False).lower()
    prohibited = ("confirmed fault", "root cause", "共同原因", "故障原因为", "已确认故障", "因果关系")
    if any(phrase in joined for phrase in prohibited):
        errors.append("report contains a prohibited diagnostic or causal assertion")
    if not allowed and (report.get("evidence_based_notes") or report.get("recommended_checks")):
        errors.append("report supplies evidence-based content although no confirmed direct support exists")
    return errors


def stable_case_id(event_id: str) -> str:
    return "GS-" + hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:12].upper()

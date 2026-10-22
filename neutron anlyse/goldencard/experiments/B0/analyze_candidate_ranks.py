#!/usr/bin/env python3
"""Explain candidate-size effects by locating the first correct-category card."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
TOP_K_VALUES = (3, 5, 8, 10, 12, 15, 20)
sys.path.insert(0, str(HERE.parent))

from result_csv import write_csv  # noqa: E402


def main() -> None:
    spec = importlib.util.spec_from_file_location("b0", HERE / "b0_bm25_tag_vote_baseline.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    cases = [json.loads(line) for line in module.GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = module.load_cards(module.CARD_PATHS, module.CATALOG)
    tiers = sorted({card.get("source_tier") for card in cards if card.get("source_tier")})
    acceptable = defaultdict(set)
    for case in cases:
        action = case["gold_action_links"][0]["action_id"]
        acceptable[action].update(item["evidence_id"] for item in case["evidence"])
    rows = []
    for case in cases:
        action = case["gold_action_links"][0]["action_id"]
        ranked = module.rank_candidates(module.query_for(case, tiers), cards, top_k=len(cards))
        first_rank = next(item["rank"] for item in ranked if item["evidence_id"] in acceptable[action])
        rows.append({"goldcard_id": case["goldcard_id"], "gold_action_id": action, "first_acceptable_evidence_rank": first_rank})
    by_action = defaultdict(list)
    for row in rows:
        by_action[row["gold_action_id"]].append(row["first_acceptable_evidence_rank"])
    payload = {
        "first_acceptable_rank_counts": dict(sorted(Counter(row["first_acceptable_evidence_rank"] for row in rows).items())),
        "cumulative_hit_at_k": {str(k): sum(row["first_acceptable_evidence_rank"] <= k for row in rows) / len(rows) for k in TOP_K_VALUES},
        "by_action": {
            action: {
                "rank_counts": dict(sorted(Counter(ranks).items())),
                "cumulative_case_count_at_k": {str(k): sum(rank <= k for rank in ranks) for k in TOP_K_VALUES},
            }
            for action, ranks in by_action.items()
        },
    }
    results = HERE / "results"
    (results / "b0_first_acceptable_rank_analysis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(results / "b0_first_acceptable_rank_cases.csv", rows, ["goldcard_id", "gold_action_id", "first_acceptable_evidence_rank"])
    hit_rows = [{
        "retrieval_top_k": k,
        "case_count": len(rows),
        "cumulative_hit_case_count": sum(row["first_acceptable_evidence_rank"] <= k for row in rows),
        "cumulative_hit_rate": sum(row["first_acceptable_evidence_rank"] <= k for row in rows) / len(rows),
    } for k in TOP_K_VALUES]
    write_csv(results / "b0_first_acceptable_rank_hit_at_k.csv", hit_rows, list(hit_rows[0]))
    action_hit_rows = [{
        "gold_action_id": action,
        "retrieval_top_k": k,
        "case_count": len(ranks),
        "cumulative_hit_case_count": sum(rank <= k for rank in ranks),
        "cumulative_hit_rate": sum(rank <= k for rank in ranks) / len(ranks),
    } for action, ranks in by_action.items() for k in TOP_K_VALUES]
    write_csv(results / "b0_first_acceptable_rank_by_action_at_k.csv", action_hit_rows, list(action_hit_rows[0]))
    lines = [
        "# B0：正确建议类别首张证据的 BM25 排名分析", "",
        "首张可接受证据是指：在该案例正确建议类别的 5 张人工确认直接支持卡中，BM25 排名最高的一张。", "",
        "| K | 累计命中案例 | Hit@K |", "| ---: | ---: | ---: |",
    ]
    for k in TOP_K_VALUES:
        count = sum(row["first_acceptable_evidence_rank"] <= k for row in rows)
        lines.append(f"| {k} | {count}/80 | {count / 80:.3f} |")
    lines += ["", "## 各建议的首张可接受证据排名", "", "| 建议 | 排名分布 |", "| --- | --- |"]
    for action, ranks in by_action.items():
        distribution = "；".join(f"第 {rank} 名：{count} 例" for rank, count in sorted(Counter(ranks).items()))
        lines.append(f"| `{action}` | {distribution} |")
    (results / "b0_first_acceptable_rank_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

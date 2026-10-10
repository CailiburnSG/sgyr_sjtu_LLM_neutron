#!/usr/bin/env python3
"""Freeze a self-contained B1 train/validation package.

This preparation step does not retrieve again and never changes B0.  It copies
the seven frozen B0 top-K rankings, expands every candidate with the reviewed
evidence-card fields that an LLM needs to read, and separates gold labels from
model inputs.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[2]
GOLD_PATH = NEUTRON_ROOT / "goldencard" / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"
B0_RESULTS = NEUTRON_ROOT / "goldencard" / "experiments" / "B0" / "results"
EVIDENCE_PATHS = [
    NEUTRON_ROOT / "evidencecard" / "cards" / "core_seed_evidence.jsonl",
    NEUTRON_ROOT / "evidencecard" / "cards" / "neutron_current_seed_evidence.jsonl",
]
CATALOG_PATH = NEUTRON_ROOT / "evidencecard" / "catalog" / "core_sources.jsonl"
OUT = HERE / "data"
TOP_KS = (3, 5, 8, 10, 12, 15, 20)

A1 = "on_site_operation_or_calibration_check"
A2 = "cross_channel_similar_anomaly_comparison"
A3 = "record_processing_and_timestamp_check"
A4 = "signal_transmission_path_check"
ACTIONS = (A1, A2, A3, A4)

# Five validation cases per action; each event-combination size appears five
# times in validation and fifteen times in training.  The IDs are fixed rather
# than sampled at run time, so all models see the same split.
VALIDATION_IDS = {
    "GC-B80-001", "GC-B80-002", "GC-B80-006", "GC-B80-011", "GC-B80-016",
    "GC-B80-021", "GC-B80-026", "GC-B80-027", "GC-B80-031", "GC-B80-036",
    "GC-B80-041", "GC-B80-046", "GC-B80-051", "GC-B80-052", "GC-B80-056",
    "GC-B80-061", "GC-B80-066", "GC-B80-071", "GC-B80-076", "GC-B80-077",
}

ACTION_DEFINITIONS = [
    {
        "action_id": A1,
        "short_name": "查同一时段现场是否有操作或校准",
        "action": "将事件起止时间与运行操作、切换、维护、通道检查、功能试验和校准等现场记录对齐，核对是否存在时间重叠。",
        "check_objects": ["运行日志", "工作票", "维护记录", "试验/校准记录", "通道检查记录"],
        "boundary": "这只是核对记录，不表示操作或校准已经发生，更不表示它导致了事件。",
    },
    {
        "action_id": A2,
        "short_name": "横向对比其他传感器通道是否出现类似问题",
        "action": "在测量定义、量程、空间位置或关联过程变量已确认可比的前提下，比较受影响通道与其他传感器通道在同一时段是否出现同类异常、相同时间变化或显著差异。",
        "check_objects": ["其他可比传感器的原始记录/CSV", "冗余组记录", "经确认可用的相关过程量"],
        "boundary": "不保证任意两个 CSV 通道可比较，也不允许从差异自动归责某个通道。",
    },
    {
        "action_id": A3,
        "short_name": "查数据记录和时间戳在处理层面是否有问题",
        "action": "核对历史库/导出/CSV 的记录和时间戳处理，检查时间戳、时区、排序、采样间隔、字段映射、拼接、缺失/重复记录及解析过程是否可能改变事件的时间或数值表达；有条件时再与原始已记录数据交叉核对。",
        "check_objects": ["原始记录", "历史库查询结果", "导出任务配置", "CSV 字段定义", "时区/时间格式说明", "数据处理日志或脚本"],
        "boundary": "A3 处理原始记录产生之后的存储、导出与处理问题；不等于已确认 CSV 有错。",
    },
    {
        "action_id": A4,
        "short_name": "查信号/数据传输路径是否异常",
        "action": "核对传感器输出到原始记录输入端的信号/数据传输路径，包括线缆、接口、供电、电流—电压转换、隔离、增益/滤波调理、复用器和 ADC/采集输入；必要时核对相应状态或测试记录。",
        "check_objects": ["通道接线与接口记录", "供电/状态位", "调理和采集配置", "转换器/ADC 配置", "维护与功能测试记录"],
        "boundary": "A4 截止于原始记录输入端；不表示路径中任何部件已损坏。",
    },
]

OUTPUT_CONTRACT = {
    "contract_version": "B1-v1",
    "task_boundary": "预检建议，不做故障原因诊断或因果确认。",
    "selected_evidence_maximum": 3,
    "allowed_support_scores": [0, 1, 2],
    "allowed_action_ids": list(ACTIONS),
    "rules": [
        "只可选择输入 bm25_candidates 中出现的 evidence_id。",
        "selected_evidence 最多 3 张，evidence_id 不得重复。",
        "必须且只能输出一项 action_id。",
        "action_evidence_ids 必须非空、是 selected_evidence 的子集，且其 support_score 必须为 2。",
        "不得确认根因、部件损坏、因果关系或实际发生的现场操作。",
        "boundary_note 必须明确建议是待核查方向，而不是故障结论。",
    ],
    "output_schema": {
        "selected_evidence": [{"evidence_id": "string", "support_score": "integer 0|1|2"}],
        "action_id": "one of allowed_action_ids",
        "action_evidence_ids": ["evidence_id selected with support_score=2"],
        "boundary_note": "string",
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_cards() -> dict[str, dict]:
    catalog = {row["doc_id"]: row for row in read_jsonl(CATALOG_PATH)}
    cards = {}
    for path in EVIDENCE_PATHS:
        for card in read_jsonl(path):
            source = catalog.get(card.get("doc_id"), {})
            merged = dict(card)
            for field in ("measurement_scope", "neutron_current_relevance", "transfer_note", "scope_note"):
                if merged.get(field) is None and field in source:
                    merged[field] = source[field]
            cards[merged["evidence_id"]] = merged
    return cards


def public_card(card: dict, rank: int, score: float) -> dict:
    return {
        "rank": rank,
        "bm25_score": score,
        "evidence_id": card["evidence_id"],
        "text": card["text"],
        "doc_id": card.get("doc_id"),
        "source_org": card.get("source_org"),
        "source_tier": card.get("source_tier"),
        "measurement_scope": card.get("measurement_scope", []),
        "neutron_current_relevance": card.get("neutron_current_relevance"),
        "section_path": card.get("section_path", []),
        "markdown_lines": [card.get("markdown_line_start"), card.get("markdown_line_end")],
        "topic_tags": card.get("topic_tags", []),
        "applicability": card.get("applicability", []),
        "transfer_note": card.get("transfer_note"),
        "scope_note": card.get("scope_note"),
    }


def gold_target(case: dict) -> dict:
    action = case["gold_action_links"][0]
    evidence_ids = [item["evidence_id"] for item in case["evidence"]]
    return {
        "goldcard_id": case["goldcard_id"],
        "target": {
            "selected_evidence": [{"evidence_id": evidence_id, "support_score": 2} for evidence_id in evidence_ids],
            "action_id": action["action_id"],
            "action_evidence_ids": action["evidence_ids"],
            "boundary_note": "这是待核查的预检建议，不确认故障原因、部件损坏或因果关系。",
        },
    }


def model_input(case: dict, prediction: dict, cards: dict[str, dict], top_k: int) -> dict:
    candidates = []
    for item in prediction["retrieved_evidence"]:
        card = cards[item["evidence_id"]]
        candidates.append(public_card(card, item["rank"], item["score"]))
    return {
        "goldcard_id": case["goldcard_id"],
        "experiment_id": "B1_bm25_llm_selection_v1",
        "retrieval_top_k": top_k,
        "query_text": prediction["query_text"],
        "precheck_input": case["precheck_input"],
        "bm25_candidates": candidates,
    }


def main() -> None:
    cases = read_jsonl(GOLD_PATH)
    case_by_id = {case["goldcard_id"]: case for case in cases}
    if len(cases) != 80 or len(VALIDATION_IDS) != 20 or not VALIDATION_IDS.issubset(case_by_id):
        raise ValueError("80-case split is incomplete")
    train_ids = {case["goldcard_id"] for case in cases} - VALIDATION_IDS
    action_for = lambda cid: case_by_id[cid]["gold_action_links"][0]["action_id"]
    size_for = lambda cid: len(case_by_id[cid]["trace"]["source_event_ids"])
    if Counter(action_for(cid) for cid in VALIDATION_IDS) != Counter({action: 5 for action in ACTIONS}):
        raise ValueError("validation action balance failed")
    if Counter(size_for(cid) for cid in VALIDATION_IDS) != Counter({size: 5 for size in range(1, 5)}):
        raise ValueError("validation event-count balance failed")
    if Counter(action_for(cid) for cid in train_ids) != Counter({action: 15 for action in ACTIONS}):
        raise ValueError("training action balance failed")
    if Counter(size_for(cid) for cid in train_ids) != Counter({size: 15 for size in range(1, 5)}):
        raise ValueError("training event-count balance failed")

    # Do not delete the directory wholesale: it also contains the human-facing
    # README and may later contain manually reviewed run notes.  Generated
    # files are deterministically overwritten in place.
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "action_definitions.json").write_text(json.dumps(ACTION_DEFINITIONS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "output_contract.json").write_text(json.dumps(OUTPUT_CONTRACT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "split_version": "B1-v1",
        "method": "fixed stratified split by action and number of source events",
        "train_case_count": len(train_ids),
        "validation_case_count": len(VALIDATION_IDS),
        "validation_goldcard_ids": sorted(VALIDATION_IDS),
        "train_goldcard_ids": sorted(train_ids),
        "validation_action_counts": Counter(action_for(cid) for cid in VALIDATION_IDS),
        "validation_event_count_counts": Counter(size_for(cid) for cid in VALIDATION_IDS),
        "train_action_counts": Counter(action_for(cid) for cid in train_ids),
        "train_event_count_counts": Counter(size_for(cid) for cid in train_ids),
        "gold_source": str(GOLD_PATH.relative_to(NEUTRON_ROOT.parent)),
        "gold_source_sha256": digest(GOLD_PATH),
    }
    (OUT / "split_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_jsonl(OUT / "labels" / "train_gold_targets.jsonl", [gold_target(case) for case in cases if case["goldcard_id"] in train_ids])
    write_jsonl(OUT / "labels" / "validation_gold_labels.jsonl", [gold_target(case) for case in cases if case["goldcard_id"] in VALIDATION_IDS])

    cards = load_cards()
    copied_sources = []
    for top_k in TOP_KS:
        source = B0_RESULTS / f"top_k_{top_k:02d}" / "b0_bm25_tag_vote_predictions.jsonl"
        rows = read_jsonl(source)
        if len(rows) != 80:
            raise ValueError(f"B0 top-{top_k} is not an 80-case result")
        prediction_by_id = {row["goldcard_id"]: row for row in rows}
        if set(prediction_by_id) != set(case_by_id):
            raise ValueError(f"B0 top-{top_k} case IDs differ from gold set")
        output_rows = [model_input(case, prediction_by_id[case["goldcard_id"]], cards, top_k) for case in cases]
        folder = OUT / "candidate_packages" / f"top_k_{top_k:02d}"
        write_jsonl(folder / "train_inputs.jsonl", [row for row in output_rows if row["goldcard_id"] in train_ids])
        write_jsonl(folder / "validation_inputs.jsonl", [row for row in output_rows if row["goldcard_id"] in VALIDATION_IDS])
        raw_copy = folder / "b0_retrieval_predictions_original.jsonl"
        shutil.copy2(source, raw_copy)
        copied_sources.append({"top_k": top_k, "source": str(source.relative_to(NEUTRON_ROOT.parent)), "source_sha256": digest(source), "copied_to": str(raw_copy.relative_to(NEUTRON_ROOT.parent))})

    (OUT / "b0_copy_manifest.json").write_text(json.dumps(copied_sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train": len(train_ids), "validation": len(VALIDATION_IDS), "top_ks": TOP_KS, "candidate_cards": len(cards)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Build reviewable, card-level evidence-function classification drafts.

This script never edits the reviewed evidence cards.  It only groups their
existing manual applicability labels into broader provisional function families.
The resulting files are drafts for human semantic review, not final units.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent
EVIDENCECARD = ROOT.parent

FUNCTIONS = {
    "F01_observed_data_qualification": {
        "label": "观测异常与数据合格性核查",
        "applicability": {"data_qualification", "spike_data_qualification", "stuck_signal_screening", "missing_data_check"},
        "draft_summary": "针对缺失、零/近零、尖峰、离群、卡滞或不合理读数的识别、保留、剔除或进一步核查依据。",
    },
    "F02_reference_and_temporal_pattern": {
        "label": "基线、参考与时间模式比较",
        "applicability": {"baseline_reference_selection", "neutron_current_temporal_comparison"},
        "draft_summary": "针对参考窗口、基线、历史时间模式或变化过程比较的依据。",
    },
    "F03_acquisition_recording_integrity": {
        "label": "采样、时间戳与记录完整性",
        "applicability": {"historian_sampling_check"},
        "draft_summary": "针对采样频率、时间戳、压缩、导出、记录完整性或同步记录质量的依据。",
    },
    "F04_signal_path_and_conditioning": {
        "label": "信号链路、隔离与调理",
        "applicability": {"signal_path_context", "neutron_current_signal_path_context"},
        "draft_summary": "针对传感器至记录端之间的信号传输、隔离、调理、滤波、增益或链路配置的依据。",
    },
    "F05_cross_channel_consistency": {
        "label": "通道与可比测量一致性",
        "applicability": {"channel_comparison", "neutron_current_channel_comparison"},
        "draft_summary": "针对与其他通道、冗余/相关传感器或其他工厂指示进行一致性比较的依据。",
    },
    "F06_test_and_calibration_alignment": {
        "label": "测试、通道检查与校准活动",
        "applicability": {"calibration_activity_check"},
        "draft_summary": "针对测试、通道检查、校准活动及其时间对齐或数据排除条件的依据。",
    },
    "F07_neutron_measurement_context": {
        "label": "中子测量原理与仪表构型",
        "applicability": {"neutron_current_measurement_context"},
        "draft_summary": "针对中子电流测量原理、探测器/通道构型、量程或仪表解释边界的依据。",
    },
    "F08_detector_response_and_calibration": {
        "label": "探测器响应与标定特性",
        "applicability": {"detector_calibration_context", "detector_response_time_context"},
        "draft_summary": "针对探测器动态响应、响应时间、灵敏度、标定曲线或响应漂移的依据。",
    },
    "F09_gamma_and_mixed_field_context": {
        "label": "伽马与混合辐射场影响",
        "applicability": {"gamma_contribution_check"},
        "draft_summary": "针对伽马贡献、混合辐射场、干扰或补偿边界的依据。",
    },
    "F10_generic_signal_quality": {
        "label": "通用信号质量与监测边界",
        "applicability": {"signal_quality_context"},
        "draft_summary": "针对噪声、漂移、监测质量、模型适用范围或一般信号可信度的依据。",
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(items: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items), encoding="utf-8")


def load_cards() -> list[dict]:
    paths = [
        EVIDENCECARD / "cards/core_seed_evidence.jsonl",
        EVIDENCECARD / "cards/neutron_current_seed_evidence.jsonl",
    ]
    return [card for path in paths for card in read_jsonl(path)]


def function_codes(card: dict) -> list[str]:
    tags = set(card["applicability"])
    return [code for code, definition in FUNCTIONS.items() if tags.intersection(definition["applicability"])]


def main() -> None:
    cards = sorted(load_cards(), key=lambda item: item["evidence_id"])
    classification = []
    members: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        codes = function_codes(card)
        if not codes:
            raise ValueError(f"No function family mapped for {card['evidence_id']}")
        item = {
            "evidence_id": card["evidence_id"],
            "provisional_function_codes": codes,
            "existing_applicability": card["applicability"],
            "existing_topic_tags": card["topic_tags"],
            "classification_basis": "existing_manual_applicability_v1",
            "review_status": "pending_human_semantic_review",
        }
        classification.append(item)
        for code in codes:
            members[code].append(card)

    write_jsonl(classification, ROOT / "card_function_classification_draft.jsonl")

    groups = []
    for code, definition in FUNCTIONS.items():
        grouped = members[code]
        applicability_counts = Counter(tag for card in grouped for tag in card["applicability"])
        representative = sorted(
            grouped,
            key=lambda card: ({"core": 0, "authority": 1, "domain": 2}.get(card["source_tier"], 9), card["evidence_id"]),
        )[:3]
        groups.append(
            {
                "function_code": code,
                "label": definition["label"],
                "draft_function_summary": definition["draft_summary"],
                "source_applicability_tags": sorted(definition["applicability"]),
                "member_count": len(grouped),
                "member_evidence_ids": [card["evidence_id"] for card in grouped],
                "applicability_distribution": dict(sorted(applicability_counts.items())),
                "representative_evidence": [
                    {"evidence_id": card["evidence_id"], "text": card["text"]} for card in representative
                ],
                "review_status": "pending_human_semantic_summary",
            }
        )
    (ROOT / "function_groups_draft.json").write_text(json.dumps(groups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 证据功能归类草稿\n", "本文件由已有人工 `applicability` 标签机械归并生成；它不是最终语义单元。"
             "下一步须逐组审阅成员证据，确认、拆分或合并其实际支撑含义。\n"]
    for group in groups:
        lines.extend([
            f"## {group['function_code']}：{group['label']}\n",
            f"- 成员数：{group['member_count']}\n",
            f"- 来源标签：{', '.join(group['source_applicability_tags'])}\n",
            f"- 暂定功能总结：{group['draft_function_summary']}\n",
            "- 代表证据：\n",
        ])
        for card in group["representative_evidence"]:
            lines.append(f"  - `{card['evidence_id']}`：{card['text']}\n")
        lines.append("\n")
    (ROOT / "function_groups_draft.md").write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

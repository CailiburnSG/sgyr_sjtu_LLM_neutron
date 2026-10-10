#!/usr/bin/env python3
"""Freeze a first semantic-unit layer above the reviewed evidence cards.

This does not edit evidence text or split cards.  It turns the already-created
card-to-function-family draft into a controlled semantic vocabulary that can
be used to score equivalent evidence meaning instead of exact card IDs.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEUTRON_ROOT = HERE.parents[1]
FUNCTION_DRAFT = HERE / "card_function_classification_draft.jsonl"
GOLD = NEUTRON_ROOT / "goldencard" / "gold_standard_80_eventgroups" / "goldcase_balanced_80.jsonl"

UNITS = {
    "F01_observed_data_qualification": {
        "semantic_unit_id": "SU01_observed_anomaly_qualification",
        "semantic_unit_name": "观测异常与数据合格性",
        "definition": "关于尖峰、缺失、零值、卡滞、离群或不合理观测的识别、筛查与合格性判断。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_or_direct_support",
    },
    "F02_reference_and_temporal_pattern": {
        "semantic_unit_id": "SU02_reference_and_temporal_pattern",
        "semantic_unit_name": "参考基线与时间模式",
        "definition": "关于参考窗口、历史基线、时间变化模式及其可比条件的证据。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_support",
    },
    "F03_acquisition_recording_integrity": {
        "semantic_unit_id": "SU03_recording_timestamp_integrity",
        "semantic_unit_name": "记录、采样与时间戳完整性",
        "definition": "关于历史库、导出、采样、同步、压缩、时间戳或记录完整性的证据。",
        "compatible_action_ids": "record_processing_and_timestamp_check",
        "scoring_role": "direct_check_support",
    },
    "F04_signal_path_and_conditioning": {
        "semantic_unit_id": "SU04_signal_path_and_conditioning",
        "semantic_unit_name": "信号传输链路与调理",
        "definition": "关于传感器输出、接口、线缆、隔离、转换、滤波、增益、复用或采集输入链路的证据。",
        "compatible_action_ids": "signal_transmission_path_check",
        "scoring_role": "direct_check_support",
    },
    "F05_cross_channel_consistency": {
        "semantic_unit_id": "SU05_cross_channel_comparison",
        "semantic_unit_name": "可比通道与冗余测量比较",
        "definition": "关于冗余、同链、可比传感器或相关过程量之间同期比较与一致性的证据。",
        "compatible_action_ids": "cross_channel_similar_anomaly_comparison",
        "scoring_role": "direct_check_support",
    },
    "F06_test_and_calibration_alignment": {
        "semantic_unit_id": "SU06_operation_test_calibration_alignment",
        "semantic_unit_name": "现场操作、测试与校准时间对齐",
        "definition": "关于操作、通道检查、功能试验、维护或校准活动及其与事件时间对齐的证据。",
        "compatible_action_ids": "on_site_operation_or_calibration_check",
        "scoring_role": "direct_check_support",
    },
    "F07_neutron_measurement_context": {
        "semantic_unit_id": "SU07_neutron_measurement_architecture",
        "semantic_unit_name": "中子测量原理与仪表构型",
        "definition": "关于中子电流测量、探测器、通道构型、量程和仪表解释边界的证据。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_support",
    },
    "F08_detector_response_and_calibration": {
        "semantic_unit_id": "SU08_detector_response_and_calibration",
        "semantic_unit_name": "探测器响应与标定特性",
        "definition": "关于探测器响应时间、灵敏度、漂移、标定曲线与动态行为的证据。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_support",
    },
    "F09_gamma_and_mixed_field_context": {
        "semantic_unit_id": "SU09_gamma_and_mixed_field_context",
        "semantic_unit_name": "伽马与混合辐射场影响",
        "definition": "关于伽马贡献、混合场、干扰与补偿边界的证据。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_support",
    },
    "F10_generic_signal_quality": {
        "semantic_unit_id": "SU10_signal_quality_and_monitoring_limit",
        "semantic_unit_name": "通用信号质量与监测边界",
        "definition": "关于噪声、漂移、信号可信度、模型适用性与一般监测限制的证据。",
        "compatible_action_ids": "context_dependent",
        "scoring_role": "contextual_support",
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cards = read_jsonl(FUNCTION_DRAFT)
    relations = []
    units_by_evidence: dict[str, set[str]] = {}
    for card in cards:
        unit_ids = set()
        for function_code in card["provisional_function_codes"]:
            unit = UNITS[function_code]
            unit_ids.add(unit["semantic_unit_id"])
            relations.append({
                "evidence_id": card["evidence_id"],
                "semantic_unit_id": unit["semantic_unit_id"],
                "semantic_unit_name": unit["semantic_unit_name"],
                "source_function_code": function_code,
                "assignment_basis": "existing_manual_applicability_to_function_family_v1",
                "review_status": "semantic_unit_v1_provisional",
            })
        units_by_evidence[card["evidence_id"]] = unit_ids
    relations.sort(key=lambda row: (row["evidence_id"], row["semantic_unit_id"]))
    write_csv(HERE / "card_semantic_units_v1.csv", relations, list(relations[0]))

    registry = [
        {"semantic_version": "v1", "source_function_code": function_code, **unit,
         "review_status": "semantic_unit_v1_provisional"}
        for function_code, unit in UNITS.items()
    ]
    write_csv(HERE / "semantic_unit_registry_v1.csv", registry, list(registry[0]))

    gold_rows = []
    for case in read_jsonl(GOLD):
        action = case["gold_action_links"][0]["action_id"]
        for evidence_id in case["evidence_combination"]["evidence_ids"]:
            for unit_id in sorted(units_by_evidence[evidence_id]):
                gold_rows.append({
                    "goldcard_id": case["goldcard_id"],
                    "action_id": action,
                    "evidence_id": evidence_id,
                    "semantic_unit_id": unit_id,
                    "semantic_action_pair": f"{unit_id}::{action}",
                })
    write_csv(HERE / "gold_semantic_action_targets_v1.csv", gold_rows, list(gold_rows[0]))

    coverage = Counter(row["semantic_unit_id"] for row in relations)
    report = {
        "semantic_version": "v1",
        "unit_count": len(registry),
        "card_count": len(units_by_evidence),
        "card_unit_relation_count": len(relations),
        "unmapped_card_count": sum(not units for units in units_by_evidence.values()),
        "semantic_unit_relation_counts": dict(sorted(coverage.items())),
        "gold_semantic_action_pair_relation_count": len(gold_rows),
        "scope": "Semantic units are an equivalence layer for scoring evidence meaning. They do not alter reviewed evidence cards or replace fixed A1-A4 actions.",
        "review_status": "semantic_unit_v1_provisional",
    }
    (HERE / "semantic_unit_coverage_report_v1.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

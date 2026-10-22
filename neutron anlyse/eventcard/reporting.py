"""Deterministic report baseline for pre-screening event cards."""

from __future__ import annotations

from typing import Any


def render_template_report(card: dict[str, Any]) -> str:
    """Render facts without adding a diagnosis or an unsupported mechanism."""
    channels = "、".join(card["channels"])
    facts = "\n".join(f"- {fact}" for fact in card.get("observed_facts", [])) or "- 无"
    limits = "\n".join(f"- {item}" for item in card.get("limitations", [])) or "- 无"
    return f"""# 中子电流记录预检报告（模板基线）

## 事件标识

- 事件编号：{card['event_id']}
- 来源记录：{card['record_id']}
- 观测类别：{card['event_type']}
- 时间范围：{card['time_start']} 至 {card['time_end']}
- 涉及通道：{channels}
- 通道范围：{card['scope']}
- 运行工况：{card.get('operating_context', 'operation_context_unknown')}

## 已观测事实

{facts}

## 建议核查事项

- 回查上述时间窗的原始记录与采集链路状态。
- 对比相关通道在同一时间窗内的原始数值和数据完整性。
- 如需工程解释，应查阅可定位的仪表监测资料并由人工复核。

## 不能确认的结论

{limits}
"""

# 中子电流预检研究工作区

本目录集中保存论文重构所需的三层材料：事件观察、可定位文献证据，以及预检案例金标准。任务目标是
**中子电流数据异常的预检与证据辅助报告**，不自动诊断具体设备故障原因。

## 当前入口

重启后优先阅读 [`RESTART_HANDOFF.md`](RESTART_HANDOFF.md)；当前应从以下路径开始，而不是从历史草稿或旧单事件关联进入：

| 层 | 当前用途 | 入口 |
| --- | --- | --- |
| 事件层 | 原始 CSV 到原子/单通道/聚合事件卡 | [eventcard/README.md](eventcard/README.md) |
| 证据层 | 300 张人工证据卡、来源目录和暂定功能归类 | [evidencecard/README.md](evidencecard/README.md) |
| 金标准层 | 80 个事件组合、三证据组合和一项固定检查建议 | [goldencard/README.md](goldencard/README.md) |

## 当前正式金标准

当前唯一用于后续训练/验证设计的版本是：

[`goldencard/gold_standard_120_eventgroups/`](goldencard/gold_standard_120_eventgroups/)

其核心文件：

- `goldcase_combined_120.jsonl`：120 个结构化预检案例；
- `evaluation_60_ids.json`：冻结的 60 例评估 ID；
- `goldcase_combination_holdout_40.jsonl`：在原 80 例基础上补充的 40 例组合留出案例；
- `build_extension_40.py`：扩展案例的可重复构造脚本。

## 目录边界

- `eventcard/output/`：从 CSV 生成的事件卡输出；
- `evidencecard/cards/`：正式的人工证据卡库，不得按段落自动重切；
- `evidencecard/semantics/`：基于既有 `applicability` 标签生成的暂定功能归类，仅作筛选辅助；
- `goldencard/event_groups/`：80 个事件原子来源；
- `goldencard/gold_standard_120_eventgroups/`：当前正式 120 例金标准；
- `goldencard/gold_standard_80_eventgroups/`：120 例集的原始 80 例版本，供追溯；
- `goldencard/drafts/`：保留的历史试标/探索稿，具体状态见其中 README；
- `goldencard/archive/`：旧单事件候选和早期实验留档，不作为当前金标准输入；
- `archive/legacy_design_notes/`：顶层早期方案草案与过程记录，不作为当前依据。

仓库根目录的 `corpus/`、`evidence/`、`paper/` 和 `参考文献/` 仍是原始资料、旧实验和论文材料；本目录不复制它们。

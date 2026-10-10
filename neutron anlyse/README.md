# 中子电流预检研究工作区

本目录集中保存论文重构所需的三层材料：事件观察、可定位文献证据，以及预检案例金标准。任务目标是
**中子电流数据异常的预检与证据辅助报告**，不自动诊断具体设备故障原因。

## 当前入口

当前应从以下路径开始，而不是从历史草稿或旧单事件关联进入：

| 层 | 当前用途 | 入口 |
| --- | --- | --- |
| 事件层 | 原始 CSV 到原子/单通道/聚合事件卡 | [eventcard/README.md](eventcard/README.md) |
| 证据层 | 300 张人工证据卡、来源目录和暂定功能归类 | [evidencecard/README.md](evidencecard/README.md) |
| 金标准层 | 80 个事件组合、三证据组合和一项固定检查建议 | [goldencard/README.md](goldencard/README.md) |

## 当前金标准草稿

当前唯一用于继续人工审阅和后续训练/验证设计的版本是：

[`goldencard/drafts/precheck_case_balanced_80_eventgroups/`](goldencard/drafts/precheck_case_balanced_80_eventgroups/)

其核心文件：

- `goldcase_balanced_80.jsonl`：80 个结构化预检案例；
- `一页总览表.md`：人工快速审阅入口；
- `证据组合定义.md`：四项建议下的三证据组合规则；
- `证据引用审计.md`：当前证据用量及来源审计；
- `build_balanced_80.py`：可重复生成脚本。

## 目录边界

- `eventcard/output/`：从 CSV 生成的事件卡输出；
- `evidencecard/cards/`：正式的人工证据卡库，不得按段落自动重切；
- `evidencecard/semantics/`：基于既有 `applicability` 标签生成的暂定功能归类，仅作筛选辅助；
- `goldencard/event_groups/`：80 个事件原子来源；
- `goldencard/drafts/`：当前 80 例及保留的历史试标/探索稿，具体状态见其中 README；
- `goldencard/archive/`：旧单事件候选和早期实验留档，不作为当前金标准输入。

仓库根目录的 `corpus/`、`evidence/`、`paper/` 和 `参考文献/` 仍是原始资料、旧实验和论文材料；本目录不复制它们。

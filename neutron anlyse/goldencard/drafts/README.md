# 金标准草稿索引

本目录保留所有阶段性草稿，避免删除导致早期决策无法追溯。**只有一个目录是当前工作入口**。

## 当前入口

| 目录 | 状态 | 用途 |
| --- | --- | --- |
| [`precheck_case_balanced_80_eventgroups/`](precheck_case_balanced_80_eventgroups/) | 当前 | 80 个事件组合；四项建议各 20 例；每例 1--4 个事件、3 张同一检查意图的证据卡、1 项建议。 |

## 历史探索稿（保留，不作为当前训练/验证集）

| 目录/文件 | 原因 |
| --- | --- |
| `precheck_case_pilot_10/` | 最初的 10 例试标，采用早期结构。 |
| `precheck_case_draft_30/` | 30 例中间扩充稿，未采用当前事件组合与证据组合规则。 |
| `precheck_case_draft_80/` | 按原始时间簇构造的旧 80 例探索稿，已被当前 `event_groups` 组合方案替代。 |
| `first_diverse_36_*.jsonl` | 旧的多样性抽样候选，属于单事件阶段材料。 |

旧稿可以用于追溯设计过程，但不得与当前 `goldcase_balanced_80.jsonl` 混合统计、训练或评估。

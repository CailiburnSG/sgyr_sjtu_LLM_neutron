# 正式 B1 结果：Qwen 3.8 Flash，Top-3

本结果使用冻结验证集 20 例。每例输入均为 B0 已保存、并复制到 B1 材料包中的同一组 BM25 Top-3 候选证据卡。
B0 对完整三张卡的 `applicability` 标签机械投票；B1 在一次 LLM 调用中阅读完整三张卡后直接输出一项 A1--A4
预检行动。

| 方法 | 行动 Accuracy | 行动 Macro-F1 | 语义—行动对 F1@3 |
| --- | ---: | ---: | ---: |
| B0：BM25 Top-3 + 全卡标签投票 | 0.250 | 0.167 | 0.180 |
| B1：同一 Top-3 + Qwen 直接判断 | 0.250 | 0.227 | 0.180 |

完整可绘图统计见 `b0_b1_action_comparison.csv`、`b1_run_metrics.csv`、`b1_action_metrics.csv` 与
`b1_semantic_metrics.csv`；逐例原始结果见 `validation_predictions.jsonl`。候选证据包本身保留在上级 B1
`data/candidate_packages/top_k_03/`，不重复写入每例结果。

# 正式 B1 结果：Qwen 3.8 Flash，Top-8

本结果使用冻结验证集 20 例。每例输入均为 B0 已保存、并复制到 B1 材料包中的同一组 BM25 Top-8 候选证据卡。
B0 对完整八张卡的 `applicability` 标签机械投票；B1 在一次 LLM 调用中阅读完整八张卡后直接输出一项 A1--A4
预检行动。

| 方法 | 行动 Accuracy | 行动 Macro-F1 | 语义—行动对 F1@8 |
| --- | ---: | ---: | ---: |
| B0：BM25 Top-8 + 全卡标签投票 | 0.250 | 0.179 | 0.155 |
| B1：同一 Top-8 + Qwen 直接判断 | 0.350 | 0.251 | 0.209 |

完整可绘图统计见 `b0_b1_action_comparison.csv`、`b1_run_metrics.csv`、`b1_action_metrics.csv` 与
`b1_semantic_metrics.csv`；逐例原始结果见 `validation_predictions.jsonl`。候选证据包本身保留在上级 B1
`data/candidate_packages/top_k_08/`，不重复写入每例结果。

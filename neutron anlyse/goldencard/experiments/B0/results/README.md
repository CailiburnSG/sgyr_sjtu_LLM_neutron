# 已运行结果

- `top_k_XX/b0_bm25_tag_vote_predictions.jsonl`：该 K 下的逐例 BM25 检索、标签投票和行动预测；
- `top_k_XX/b0_bm25_tag_vote_metrics.json`：该 K 下的行动、严格金标准证据、金标准行动证据候选覆盖以及混淆矩阵指标；
- `b0_k_sweep_summary.json` / `.md`：`K={3,5,8,10,12,15,20}` 的汇总。
- `b0_k_sweep_by_action.md`：每个 K、每项行动的 Precision、Recall、F1 与 TP/FP/FN。
- `b0_first_acceptable_rank_analysis.json` / `.md`：正确建议类别首张可接受证据的 BM25 排名分布，用于解释候选覆盖@K 的变化。

B0 是 BM25 检索加既有证据标签投票，不使用 LLM，也不读取金标准行动标签或金标准证据。

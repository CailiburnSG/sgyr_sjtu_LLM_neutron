# 已运行结果

CSV 是后续分析、绘图和跨模型比较的主格式；JSON/JSONL 保留为嵌套检索信息和原始审计产物。

- `b0_k_sweep_metrics.csv`：所有 K 的一行一组运行级指标；
- `b0_k_sweep_action_metrics.csv`：所有 K × 行动的 Precision、Recall、F1 与 TP/FP/FN；
- `b0_semantic_k_sweep_metrics.csv`：所有 K 的语义候选检索及语义候选—行动对指标；
- `top_k_XX/b0_run_metrics.csv`、`b0_action_metrics.csv`、`b0_candidate_coverage_by_action.csv`：单次运行的指标拆表；
- `top_k_XX/b0_semantic_metrics.csv`、`b0_semantic_by_action.csv`：该 K 的语义候选指标；
- `b0_first_acceptable_rank_cases.csv`、`b0_first_acceptable_rank_hit_at_k.csv`、`b0_first_acceptable_rank_by_action_at_k.csv`：候选覆盖排名分析。

- `top_k_XX/b0_bm25_tag_vote_predictions.jsonl`：该 K 下的逐例 BM25 检索、标签投票和行动预测；
- `top_k_XX/b0_bm25_tag_vote_metrics.json`：该 K 下的行动、严格金标准证据、金标准行动证据候选覆盖以及混淆矩阵指标；
- `b0_k_sweep_summary.json` / `.md`：`K={3,5,8,10,12,15,20}` 的汇总。
- `b0_k_sweep_by_action.md`：每个 K、每项行动的 Precision、Recall、F1 与 TP/FP/FN。
- `b0_first_acceptable_rank_analysis.json` / `.md`：正确建议类别首张可接受证据的 BM25 排名分布，用于解释候选覆盖@K 的变化。

B0 的逐案例检索与预测保留在 `top_k_XX/b0_bm25_tag_vote_predictions.jsonl`。语义指标中的 `candidate` 表示 B0 的整个 top-K 候选集合；它并不等同于 B1 最多三卡的最终选择。B0 是 BM25 检索加既有证据标签投票，不使用 LLM，也不读取金标准行动标签或金标准证据。

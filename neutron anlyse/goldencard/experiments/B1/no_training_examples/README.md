# B1：未使用训练示例的 LLM 判断

本阶段模型只读取固定行动定义、输出合同、当前事件组及 B0 冻结的 top-K 候选卡；**不读取** 60 例训练标签，
也不使用训练示例或微调权重。

行动是对完整 Top-K 候选证据包的单次综合判断，不输出或截断为证据子集。每例结果保留输入的完整候选包；
主结果以 `retrieval_top_k`（例如 10）标明候选输入规模，并以行动 Accuracy / Macro-F1 比较 B0 与 B1。严格证据
P/R/F1@K 与候选覆盖@K 属于上游 BM25 检索质量，只需报告一次；语义—行动对 F1@K 则必须随每个模型 × K
保留，用于比较不同判断方法如何将相同候选包转化为行动。

逐案例模型输出保留为 JSONL；CSV 只用于可聚合的运行、行动和错误统计。

目录规则：

```text
B1/no_training_examples/
  <模型名>/
    top_k_XX/
      b1_run_metrics.csv         # 标量指标及 prompt/completion/total token
      b1_action_metrics.csv      # 每项行动的 P/R/F1 与 TP/FP/FN
      b1_semantic_metrics.csv    # 语义证据及语义—行动对 P/R/F1@K
      b1_semantic_by_action.csv  # 语义指标按正确行动拆分
      b1_error_counts.csv        # 格式/约束错误计数
      validation_predictions.jsonl # 每例预测与原始模型响应
      analysis.md
```

阶段根目录的 `summary_metrics.csv` 汇总所有模型 × K 运行，包含 prompt、completion 和 total token，以及单例延迟的
均值、P50 和 P95，供后续直接绘图、成本比较和结果比较。
语义指标使用 [`evidencecard/semantics/`](../../../../evidencecard/semantics/) 的 `semantic_unit_v1` 映射；该映射为
可审计的第一版评分粒度，不能替代严格卡号指标。

当前 Qwen 运行器为 [`run_no_training_qwen.py`](run_no_training_qwen.py)。通过 `--top-k` 读取对应的冻结 B0 候选包；
它会校验每例候选卡数与 K 一致，并保持同一输出合同、冻结验证集和 B0 候选包。

正式全 Top-K 协议的结果直接写入 `<模型名>/top_k_XX/`；例如 `qwen3.8-flash/top_k_10/`。

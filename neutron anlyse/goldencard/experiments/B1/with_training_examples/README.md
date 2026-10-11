# B1：固定训练示例上下文

这是少样本上下文学习实验，不更新模型参数；它与 `no_training_examples/` 并列，并复用零样本运行器的 API、冻结验证集、行动定义、输出合同和指标代码。

首个 Top-10 直接支持卡优先配置已保留为 `example_pools/top_k_10/n_08/pilot_direct_support/`，只作为机制可行性的先导结果，不混入随机池平均值。正式数量实验使用 `example_pools/top_k_10/n_08/pool_01.jsonl` 至 `pool_03.jsonl`：三组均为 A1--A4 各 2 例、事件组大小 1--4 各 2 例的分层随机冻结池。验证例及其标签绝不进入模型可见 JSONL。

案例 `goldcard_id` 仅在本地 manifest 和模型外评分记录中保留；由于编号区间与人工行动类别相关，它已从训练示例与验证提示中移除，防止编号捷径。

运行：

```bash
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/prepare_random_example_pools.py'
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/run_fixed_examples_qwen.py' \
  --top-k 10 --model qwen3.8-flash --pool-id 01 \
  --selection-mode stratified_random_frozen_v1 \
  --examples-file 'neutron anlyse/goldencard/experiments/B1/with_training_examples/example_pools/top_k_10/n_08/pool_01.jsonl'
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/summarize_example_pools.py'
```

结果写入 `<模型名>/top_k_10/n_08/pool_XX/`，而 `top_k_10/summary_by_pool.csv` 与 `summary_by_example_count.csv` 汇总同一 K 下的池级和均值/标准差指标。这应与同模型、同一 Top-10 候选包的零样本 B1 对照；唯一额外输入是固定的八个训练示例。

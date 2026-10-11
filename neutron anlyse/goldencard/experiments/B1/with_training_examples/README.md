# B1：固定训练示例上下文

这是少样本上下文学习实验，不更新模型参数；它与 `no_training_examples/` 并列，并复用零样本运行器的 API、冻结验证集、行动定义、输出合同和指标代码。

首个冻结配置为 Top-10 的 8 个训练例：A1--A4 各 2 个。选择规则与具体 ID 固化在 `data/fixed_examples_manifest.json`；完整可调用示例保存在 `data/fixed_examples_top_k_10.jsonl`。验证例及其标签绝不进入该文件。

案例 `goldcard_id` 仅在本地 manifest 和模型外评分记录中保留；由于编号区间与人工行动类别相关，它已从训练示例与验证提示中移除，防止编号捷径。

运行：

```bash
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/prepare_fixed_examples.py'
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/run_fixed_examples_qwen.py' --top-k 10 --model qwen3.8-flash
```

结果写入 `<模型名>/top_k_10/`。这应与同模型、同一 Top-10 候选包的零样本 B1 对照；唯一额外输入是固定的八个训练示例。

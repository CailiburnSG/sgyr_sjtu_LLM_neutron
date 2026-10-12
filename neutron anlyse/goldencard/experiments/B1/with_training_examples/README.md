# B1：固定示例上下文（现行入口）

这里做的是**少样本上下文学习**：每一次独立调用都输入固定的 `n` 个示例、当前事件组合和同一份 BM25 Top-K 候选证据包；不更新模型参数，也不保留不同验证例之间的对话历史。

现行程序只有三个：

- `materialize_same_id_pool_for_topk.py`：把已冻结的 Top-10 示例池原样迁移至目标 K；只改变每例的候选证据包，示例案例、答案和顺序不变。
- `run_fixed_examples_qwen.py`：对一个冻结池运行模型并生成该池的 JSON 个案结果和 CSV 指标。
- `summarize_example_pools.py`：汇总同一模型、K、n 的三次重复，写出均值和标准差。

`example_pools/top_k_XX/n_YY/pool_01..03.jsonl` 是模型实际可见的固定示例。每个 `pool_XX.manifest.json` 记录示例 ID（仅供审计，绝不进入模型提示）、来源和选择规则。

## 正式运行（以 K=3、n=16 为例）

在 B1 材料已按同一 K 准备并校验后，先生成目标 K 的固定示例池：

```bash
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/materialize_same_id_pool_for_topk.py' \
  --target-top-k 3 --example-count 16
```

依次运行三个冻结池（`pool-id`、示例文件和结果目录必须对应）：

```bash
for pool in 01 02 03; do
  python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/run_fixed_examples_qwen.py' \
    --top-k 3 --model qwen3.8-flash --pool-id "$pool" \
    --selection-mode same_case_ids_as_top_k_10_n_16_v1 \
    --examples-file "neutron anlyse/goldencard/experiments/B1/with_training_examples/example_pools/top_k_03/n_16/pool_${pool}.jsonl"
done

python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/summarize_example_pools.py'
```

结果位于 `<模型>/top_k_XX/n_YY/pool_XX/`。个案结果保留 JSON；可比较的池级和均值/标准差统计为同级的 CSV。

## 归档脚本

[`historical_pool_builders/`](historical_pool_builders/) 中是早期逐个构造 n=4、8、12… 或早期 Top-3 池时使用的专用脚本。它们仅用于复现既有历史结果；**新实验不要运行它们**，统一使用上述通用迁移器。

# B1 正式执行顺序

本页只描述当前正式流程。历史脚本和旧 20 例结果可保留审计，但不得与 60 例评估结果直接合并比较。

## 固定输入

```text
gold_standard_120_eventgroups/goldcase_combined_120.jsonl  # 120 个黄金案例
gold_standard_120_eventgroups/evaluation_60_ids.json       # 冻结的 60 个评估 ID
```

需要实验 K、模型名和（若少样本）示例数 n。每个 K 必须先完成以下材料阶段，禁止直接让 B1 读取金标准标签或重排 B0 候选。

## 1. B0 生成该 K 的候选证据包

```bash
python3 'neutron anlyse/goldencard/experiments/B0/b0_bm25_tag_vote_baseline.py' \
  --top-k K \
  --gold-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/goldcase_combined_120.jsonl' \
  --result-root 'neutron anlyse/goldencard/experiments/B0/results/evaluation_60'
```

输出：`B0/results/evaluation_60/top_k_XX/`。这里保留原始 BM25 排名、分数和 B0 基线结果；它是 B1 唯一允许使用的候选来源。

## 2. 冻结该 K 的 B1 输入

```bash
python3 'neutron anlyse/goldencard/experiments/B1/prepare_b1_materials.py' \
  --gold-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/goldcase_combined_120.jsonl' \
  --validation-ids-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/evaluation_60_ids.json' \
  --top-ks K \
  --b0-results-root 'neutron anlyse/goldencard/experiments/B0/results/evaluation_60'

python3 'neutron anlyse/goldencard/experiments/B1/validate_b1_materials.py' --top-ks K
```

输出：`B1/data/candidate_packages/top_k_XX/`、标签隔离文件、复制清单和拆分清单。校验未通过时不得调用模型。

## 3A. B1 零样本（可选）

不提供任何黄金示例，只将冻结评估输入逐例送进模型：

```bash
python3 'neutron anlyse/goldencard/experiments/B1/no_training_examples/run_no_training_qwen.py' \
  --top-k K --model qwen3.8-flash
```

输出：`B1/no_training_examples/<模型>/top_k_XX/`。

## 3B. B1 固定示例上下文

先从已冻结 Top-10 同 n 池复制相同的案例和答案到目标 K。仅替换每例的 BM25 候选包：

```bash
python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/materialize_same_id_pool_for_topk.py' \
  --target-top-k K --example-count N
```

然后分别运行 `pool_01`、`pool_02`、`pool_03`；每一池均对同一 60 个评估案例独立调用，不能串联对话：

```bash
for pool in 01 02 03; do
  python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/run_fixed_examples_qwen.py' \
    --top-k K --model qwen3.8-flash --pool-id "$pool" \
    --selection-mode same_case_ids_as_top_k_10_n_N_v1 \
    --examples-file "neutron anlyse/goldencard/experiments/B1/with_training_examples/example_pools/top_k_XX/n_NN/pool_${pool}.jsonl"
done

python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/summarize_example_pools.py'
```

将命令中的 `K` 改为整数、`N` 改为整数，并将 `top_k_XX` / `n_NN` 改为零填充后的实际目录，例如 `top_k_03/n_16`。`--selection-mode` 只是一条审计描述，必须与对应 pool manifest 一致。

## 4. 读取正式结果

- 每个池的个案输出和指标：`with_training_examples/<模型>/top_k_XX/n_NN/pool_XX/`；
- 三池汇总：`with_training_examples/<模型>/top_k_XX/summary_by_pool.csv` 与 `summary_by_example_count.csv`；
- B0 同 K 对照：`B0/results/evaluation_60/top_k_XX/`。

正式比较时，只有 **同一冻结评估集规模、同一个 K、同一个模型** 的结果可横向比较。当前已完整迁移并正式运行的是 K=3；其余 K 要先完成第 1、2 步。

# 重启会话交接：中子电流异常预检

## 先读这一页

本工作目标是**中子电流 CSV 异常的预检与证据辅助报告**，不是自动诊断具体故障原因。当前任务链为：

```text
事件组合 X + 全部候选证据 Y  →  一项固定人工检查建议 Z
```

模型只能从 A1--A4 中选一项；证据用于说明“为什么应优先核查”，不证明故障已经发生。

## 四项固定建议

| ID | 直观含义 |
| --- | --- |
| A1 `on_site_operation_or_calibration_check` | 查同一时段真实物理场是否有操作或校准 |
| A2 `cross_channel_similar_anomaly_comparison` | 横向比较其他传感器通道有无类似异常 |
| A3 `record_processing_and_timestamp_check` | 查数据记录、处理或时间戳是否有问题 |
| A4 `signal_transmission_path_check` | 查信号传输路径是否异常 |

定义与边界见 `goldencard/固定检查行为.md`。

## 当前正式数据

- 事件：`eventcard/README.md`；原始 CSV 已生成原子、单通道和聚合事件卡。
- 证据：`evidencecard/README.md`；300 张人工证据卡、39 份来源。禁止自动按段落重切证据卡。
- 语义单元：`evidencecard/semantics/card_semantic_units_v1.csv`，用于放宽证据卡逐张 Exact Match 的评估。
- 金标准：`goldencard/gold_standard_120_eventgroups/goldcase_combined_120.jsonl`。
  - 共 120 例；每例是 1--4 个事件原子组成的预检事件组合、3 张同一检查意图的证据卡和 1 项行动。
  - 60 例固定 few-shot 示例来源，60 例冻结评估集：`evaluation_60_ids.json`。
  - 不把 `goldcard_id` 传给模型，避免 ID 相关捷径。

## 实验定义与已完成内容

统一使用冻结的 60 例评估集、Qwen `qwen3.8-flash`、温度 0、B1-v3-all-topk 输出合同。

| 实验 | 输入与决策 | 状态 |
| --- | --- | --- |
| B0 | BM25 Top-K 检索 + 证据已有 applicability 标签机械投票 | K=3/5/8 已有正式 60 例结果 |
| B1 零样本 | 与 B0 相同 Top-K 候选包 + LLM 选行动 | K=3/5/8 已有正式 60 例结果 |
| B1 固定示例 | 相同候选包 + n 个冻结 few-shot 示例 + LLM 选行动；三池重复 | K=3、5、8 已跑 n=4/8/12/16/20（K=8 的 n=16/20 刚完成） |
| B2 | 全库 LLM 证据选择 + LLM 行动选择 | 未做 |
| B3 | 金标准证据 + LLM 行动选择消融 | 未做 |

关键结论：K 越大时零样本有所改善；有约 8--16 个固定示例后性能趋于饱和。K=8、n=20 与 n=16 指标相同而 token 成本更高，后续无需扩大 n。

最新 K=8 结果（60 例、三池均值）：

| n | Accuracy | Macro-F1 | 平均总 token/池 |
| --- | ---: | ---: | ---: |
| 16 | 0.9889 ± 0.0192 | 0.9888 ± 0.0193 | 2.739M |
| 20 | 0.9889 ± 0.0192 | 0.9888 ± 0.0193 | 3.364M |

完整可比统计在 `goldencard/experiments/B1/with_training_examples/qwen3.8-flash/top_k_XX/summary_by_example_count.csv`。

## 重启后推荐阅读顺序

1. 本文件；
2. `README.md`；
3. `goldencard/README.md` 和 `goldencard/gold_standard_120_eventgroups/README.md`；
4. `goldencard/experiments/B1/README.md` 与 `goldencard/experiments/B1/EXECUTION_ORDER.md`；
5. 仅在需要执行时，读 `goldencard/experiments/B1/with_training_examples/README.md`。

## 当前代码入口

`goldencard/experiments/B1/EXECUTION_ORDER.md` 是唯一正式执行顺序。核心脚本：

- `B0/b0_bm25_tag_vote_baseline.py`
- `B1/prepare_b1_materials.py`
- `B1/validate_b1_materials.py`
- `B1/no_training_examples/run_no_training_qwen.py`
- `B1/with_training_examples/materialize_same_id_pool_for_topk.py`
- `B1/with_training_examples/run_fixed_examples_qwen.py`
- `B1/with_training_examples/summarize_example_pools.py`

API key 位于 `goldencard/experiments/apikey.txt`，已被 Git 忽略，绝不可读取、展示或提交。

### 最小调用流程

以下命令都从仓库根目录执行，`K` 用实际整数替换（例如 `8`），`N` 用示例数替换（例如 `16`）。每次调用新 K 前先检查 `apikey.txt` 已在本地存在，**不要**把 key 写入命令、日志或 Git。

1. **B0：构造 BM25 Top-K 及机械投票基线。**

   ```bash
   python3 'neutron anlyse/goldencard/experiments/B0/b0_bm25_tag_vote_baseline.py' \
     --top-k K \
     --gold-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/goldcase_combined_120.jsonl' \
     --evaluation-ids-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/evaluation_60_ids.json' \
     --result-root 'neutron anlyse/goldencard/experiments/B0/results/evaluation_60'
   ```

2. **冻结 B1 输入并校验。**（首次使用某 K 时做一次。）

   ```bash
   python3 'neutron anlyse/goldencard/experiments/B1/prepare_b1_materials.py' \
     --gold-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/goldcase_combined_120.jsonl' \
     --validation-ids-path 'neutron anlyse/goldencard/gold_standard_120_eventgroups/evaluation_60_ids.json' \
     --top-ks K \
     --b0-results-root 'neutron anlyse/goldencard/experiments/B0/results/evaluation_60'
   python3 'neutron anlyse/goldencard/experiments/B1/validate_b1_materials.py' --top-ks K
   ```

3. **B1 零样本。**

   ```bash
   python3 'neutron anlyse/goldencard/experiments/B1/no_training_examples/run_no_training_qwen.py' \
     --top-k K --model qwen3.8-flash
   ```

4. **B1 固定示例（少样本上下文，不是参数微调）。**先生成同一案例 ID 的三组示例池，再逐池调用、汇总。

   ```bash
   python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/materialize_same_id_pool_for_topk.py' \
     --target-top-k K --example-count N
   for pool in 01 02 03; do
     python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/run_fixed_examples_qwen.py' \
       --top-k K --model qwen3.8-flash --pool-id "$pool" \
       --selection-mode same_case_ids_as_top_k_10_n_N_v1 \
       --examples-file "neutron anlyse/goldencard/experiments/B1/with_training_examples/example_pools/top_k_XX/n_NN/pool_${pool}.jsonl"
   done
   python3 'neutron anlyse/goldencard/experiments/B1/with_training_examples/summarize_example_pools.py' \
     --model qwen3.8-flash --top-k K --example-count N
   ```

   在第 4 步中，`top_k_XX` 和 `n_NN` 必须使用零填充的真实目录名，例如 K=8、N=16 时为 `top_k_08/n_16`；`same_case_ids_as_top_k_10_n_N_v1` 中的 `N` 要替换为实际数字。

结果位置：B0 在 `B0/results/evaluation_60/top_k_XX/`；零样本在 `B1/no_training_examples/<模型>/top_k_XX/`；少样本逐池 JSON/CSV 在 `B1/with_training_examples/<模型>/top_k_XX/n_NN/pool_XX/`，跨池均值与标准差在同一 `top_k_XX/summary_by_example_count.csv`。

## 当前建议的下一步

先停止扩大 Qwen 的 K/n 网格；整理 K=3/5/8 的 B0、B1 零样本与 B1 固定示例汇总表，确定论文展示的主比较。然后再设计 B2（LLM 全库语义检索）和 B3（金标准证据消融），以证明“理解证据”而非机械 BM25 投票的价值。

## 归档说明

顶层 `archive/legacy_design_notes/` 是早期草案和过程记录，只供追溯；不作为当前方法或实验依据。旧 20 例试验结果统一带 `_eval20` 后缀，也只供审计，不能与正式 60 例结果混合比较。

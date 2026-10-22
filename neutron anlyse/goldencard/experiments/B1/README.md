# B1：BM25 候选检索 + LLM 证据—行动选择

## 目的

B1 保留 B0 的同一 BM25 查询和候选库，但将“证据类型标签投票”替换为 LLM 阅读候选证据正文后的联合选择。
它直接检验 LLM 能否将事件组合、证据含义和固定检查建议联系起来。它位于以下四级主对照的第二级：

```text
B0：BM25 + 机械投票
B1：BM25 + LLM 选择
B2：全库 LLM 证据选择 + LLM 行动选择
B3：金标准证据 + LLM 行动选择（消融）
```

```text
事件组合
  → BM25 top-K（与 B0 相同）
  → LLM 阅读 K 张候选证据正文 + 四项行动定义
  → 对完整 Top-K 候选证据包直接给出 1 项固定检查建议
```

## 当前冻结数据与主流程

当前正式扩展集为 120 例：60 例可供固定示例池取样，60 例用于评估。黄金集、冻结评估 ID 和输出都保留在仓库中；模型提示不含 `goldcard_id` 和验证标签。各 K 的材料可以处于不同迁移阶段，因此每次运行必须以对应 `split_manifest.json` 和校验器的实际计数为准。

对任意一个尚未迁移至 60 例评估的 K，严格按以下顺序执行：

1. B0 在完整 120 例上生成该 K 的 BM25 候选结果；
2. `prepare_b1_materials.py` 从这份 B0 结果复制候选包并按冻结 ID 拆为 60/60；
3. `validate_b1_materials.py` 校验候选数量、标签隔离和 B1-v3 输出合同；
4. 运行零样本或固定示例 B1；固定示例设置使用三个冻结池重复；
5. 汇总个案 JSON 和池级/跨池 CSV。

可复制的完整命令见 [`EXECUTION_ORDER.md`](EXECUTION_ORDER.md)。

## 冻结实验矩阵

目标 K 网格为：

```text
K = {3, 5, 8, 10, 12, 15, 20}
```

每个 LLM × K 组合必须使用同一事件输入、同一 BM25 排名、同一行动定义、同一提示词结构、温度 0 和相同的单建议输出约束。不同 K 的正式数值只在它们均使用同一 60 例冻结评估集后才可横向比较。

## 可直接运行时读取的材料

[`data/`](data/) 是自包含的 B1 材料副本，而不是对上游目录的软引用：

- 对每个 K，`candidate_packages/top_k_XX/train_inputs.jsonl` 与 `validation_inputs.jsonl` 含完整候选卡正文、
  来源定位、主题标签、applicability 和 B0 的 BM25 排名/得分；
- 同目录 `b0_retrieval_predictions_original.jsonl` 是从 B0 逐字复制的原始检索中间产物，便于审计；
- `action_definitions.json` 给出 A1--A4 完整定义；`output_contract.json` 给出严格输出规则；
- `labels/train_gold_targets.jsonl` 是训练目标；`labels/validation_gold_labels.jsonl` 仅供评估器读取。

材料通过 `prepare_b1_materials.py` 从已冻结的 B0 结果复制并扩展。复制清单记录在 `data/b0_copy_manifest.json`；B0 原目录及其中间产物不被改写或删除。

## 多模型比较

至少配置三个可调用模型：

1. 强模型：作为主结果模型；
2. 较小或低成本模型：检验方法不只依赖最大模型；
3. 独立模型系列：检验结果是否跨模型系列稳定。

实际模型名、API 端点和凭据不写入本目录；复制 [`models.example.json`](models.example.json) 为本地配置文件后填写。
论文中报告模型名、版本/日期、温度、最大输出 token、是否使用 seed，以及每个组合的失败/重试次数。

## LLM 输入与输出

输入为结构化事件组合、K 张候选卡的 `evidence_id`、正文、主题标签、适用性标签和来源定位，以及四项行动定义。
输出仅允许：

```json
{
  "action_id": "on_site_operation_or_calibration_check",
  "boundary_note": "不确认故障原因"
}
```

模型不输出证据子集：完整 Top-K 候选包随结果一同保留并呈现；模型必须且只能在 A1--A4
中选择一个完整 `action_id`。禁止输出根因、故障确认或因果结论。机器可读的完整合同见
[`data/output_contract.json`](data/output_contract.json)。

## 指标与错误归因

每个模型 × K 分开报告三层指标：

1. **候选包质量**：严格 Evidence Precision/Recall/F1@K、语义 Evidence Precision/Recall/F1@K，以及
   金标准行动证据覆盖@K。这些指标说明正确资料是否进入完整 Top-K 包；相同候选包下 B0 与 B1 的数值相同。
2. **证据—行动连接**：语义—行动对 Precision/Recall/F1@K。将完整 Top-K 候选卡映射为语义单元，并与预测行动组成
   `(semantic_unit, action_id)` 对；它是后续所有实验必须保留的核心指标。
3. **最终行动与生成合规**：行动 Accuracy、Macro-F1、JSON 合法率和输出合同合规率。

候选覆盖只说明模型是否拿到了正确资料，不代表它已经得出正确结论。

错误按以下顺序归因：

1. **候选缺失**：top-K 不含正确建议类别的任一可接受证据；
2. **语义—行动连接失误**：候选包具有可接受证据，但预测行动未能与其语义正确连接；
3. **行动失误**：最终建议与金标准行动不同；
4. **约束失效**：格式或预检边界不合规。

## 实施状态

实验结果按“是否使用训练金标准”与模型名分开保存：

- [`no_training_examples/`](no_training_examples/)：未使用训练示例的模型。它不读取训练标签；正式结果按
  `no_training_examples/<模型名>/top_k_XX/` 保存。
- [`with_training_examples/`](with_training_examples/)：使用固定训练示例的少样本上下文阶段，现行入口见该目录 README；结果按
  `with_training_examples/<模型名>/top_k_XX/n_YY/pool_ZZ/` 保存。

两阶段均继续读取同一份 `data/candidate_packages/top_k_XX/`，即 B0 冻结的 BM25 候选包；不能改变上游检索。

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
  → 最多 3 张证据 + 1 项固定检查建议
```

## 冻结训练—验证分割

80 例不直接混用。B1 使用固定、分层的 60/20 分割：训练集 60 例，验证集 20 例；四项行动在两部分中分别为
15/5 例，1--4 个事件组成的案例也分别为 15/5 例。具体 ID、来源校验和计数在
[`data/split_manifest.json`](data/split_manifest.json)。

训练部分用于确定提示词示例、开发/微调方案和模型调用参数；最终报告仅以冻结的 20 例验证集计分。验证输入不得附带
`data/labels/validation_gold_labels.jsonl`。

## 冻结实验矩阵

所有模型均运行相同的 K 网格，不为特定模型挑选最有利的候选规模：

```text
K = {3, 5, 8, 10, 12, 15, 20}
```

每个 LLM × K 组合在 60 例训练集上开发，并在同一 20 例验证集上运行一次正式评估。模型必须使用同一事件输入、
同一 BM25 排名、同一行动定义、同一提示词结构、温度 0、相同的最多三卡/单建议输出约束。

## 可直接运行时读取的材料

[`data/`](data/) 是自包含的 B1 材料副本，而不是对上游目录的软引用：

- 对每个 K，`candidate_packages/top_k_XX/train_inputs.jsonl` 与 `validation_inputs.jsonl` 含完整候选卡正文、
  来源定位、主题标签、applicability 和 B0 的 BM25 排名/得分；
- 同目录 `b0_retrieval_predictions_original.jsonl` 是从 B0 逐字复制的原始检索中间产物，便于审计；
- `action_definitions.json` 给出 A1--A4 完整定义；`output_contract.json` 给出严格输出规则；
- `labels/train_gold_targets.jsonl` 是训练目标；`labels/validation_gold_labels.jsonl` 仅供评估器读取。

材料通过 `prepare_b1_materials.py` 从已冻结的 B0 结果复制并扩展。复制清单记录在 `data/b0_copy_manifest.json`；
B0 原目录及其中间产物不被改写或删除。

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
  "selected_evidence": [
    {"evidence_id": "...", "support_score": 2},
    {"evidence_id": "...", "support_score": 2},
    {"evidence_id": "...", "support_score": 1}
  ],
  "action_id": "on_site_operation_or_calibration_check",
  "action_evidence_ids": ["..."],
  "boundary_note": "不确认故障原因"
}
```

`selected_evidence` 最多 3 张；`action_evidence_ids` 只能引用候选包内且 `support_score=2` 的卡；必须且只能在 A1--A4
中选择一个完整 `action_id`。禁止输出根因、故障确认或因果结论。机器可读的完整合同见
[`data/output_contract.json`](data/output_contract.json)。

## 指标与错误归因

每个模型 × K 分开报告三层指标：候选层的**金标准行动证据覆盖@K / 候选 Precision@K**，证据选择层的
严格 Evidence Precision/Recall/F1@K，以及结论层的行动 Accuracy/Macro-F1、`(evidence_id, action_id)` 对 F1、
JSON 合法率、未知 ID 率和无依据行动率。候选覆盖只说明 LLM 是否拿到了正确资料，不代表它已经得出正确结论。

错误按以下顺序归因：

1. **候选缺失**：top-K 不含正确建议类别的任一可接受证据；
2. **LLM 选择失误**：候选中有可接受证据，但 LLM 未选择；
3. **LLM 行动失误**：LLM 选择了可接受证据，但建议错误；
4. **约束失效**：格式、ID、证据支撑或边界不合规。

## 实施状态

实验矩阵和输出合同已冻结，尚待确定实际可调用的 LLM/API 后实现运行器。

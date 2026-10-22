# 证据卡库

`evidencecard/` 是事件卡之外的资料证据层。它保存可定位的资料段落，以及某次事件预检中“事件卡—证据卡”的人工复核关联；不保存向量，也不替代原始 PDF/Markdown。

```text
corpus/md/                    原始资料的机器可读版本
  └── evidencecard/cards/     可引用证据段落
eventcard/output/             数据记录产生的聚合事件卡
  └── evidencecard/links/     事件—证据关联及人工复核标签
```

## 来源区分

每张证据卡必须有两个不同字段：

- `source_org`：来源机构，如 `IAEA`、`EPRI_DOE`、`NRC`；
- `source_tier`：在本预检任务中的使用优先级，取 `core`、`domain` 或 `supplementary`。

这不是“IAEA 正确、非 IAEA 不正确”的二元判断。`core` 仅表示其内容直接服务于在线监测、仪表通道和数据质量的预检说明；非 IAEA 的资料仍可成为核心或领域证据。

每张卡还必须继承来源文档的测量对象标记：

- `measurement_scope`：例如 `neutron_current`、`neutron_instrumentation`、`generic_instrument_channel`；
- `neutron_current_relevance`：`direct`、`contextual` 或 `generic_only`；
- `transfer_note`：当资料不是直接针对当前中子电流测量链路时，说明其只能提供何种可类比的预检原则。

报告生成时，优先使用 `direct` 卡。`contextual` 和 `generic_only` 卡只能支撑通用的数据质量、采集链路或核查步骤，必须保留其适用性限制，不能被表述为中子电流的专属结论。

## 三种对象

1. **证据卡**：一段按章节和自然段切分的原文，含稳定 `evidence_id`、文档路径、章节、Markdown 行号、原始 PDF 路径和主题标签。
2. **事件卡**：由 `eventcard/` 生成，记录观测到的时序现象。
3. **关联卡**：记录一个事件实际使用或被人工判定相关的证据。关联是多对多的，且应保留查询版本、判断标签和复核状态。

## 关联标签

| 标签 | 含义 |
|---|---|
| `direct_support` | 段落可直接支撑一条不越界的预检说明或核查建议 |
| `related_but_insufficient` | 主题相关，但不足以支持具体说明 |
| `not_relevant` | 对该事件的预检任务无关 |

首批关联由助手依据原文生成候选，均标为 `pending_user_review`；只有经你确认的关联才进入金标准评价集。

## 当前首批范围

当前先读三份在线监测 Core 文档，并补充直接面向中子仪表/中子电流的领域资料：

- IAEA《On-line Monitoring for Improving Performance of Nuclear Power Plants, Part 1: Instrument Channel Monitoring》；
- IAEA《On-line Monitoring of Instrumentation in Research Reactors》；
- EPRI TR-104965《On-Line Monitoring of Instrument Channel Performance》。
- Westinghouse《Excore Nuclear Instrumentation》；
- 《Reactor Core Monitoring》。
- IAEA《On-line Monitoring for Improving Performance of Nuclear Power Plants, Part 2: Process and Component Condition Monitoring and Diagnostics》；
- HFIR《Results in the Application of Pattern Recognition Methods to Nuclear Reactor Core Component Surveillance》。

此范围用于验证数据质量、尖峰、缺失数据、卡滞数据和多通道一致性相关的预检说明。它不用于确认具体装置故障原因。

## 数量与审核状态

目标证据卡总数为 **300**。当前已有 300 张人工阅读后编写的 `manual_seed` 卡，覆盖 39 份来源文档。后续卡片沿用同一简洁格式：原文段落、来源定位、主题标签和 `applicability` 受控标签，说明它可支持的预检方向。

`applicability` 使用 ASCII-only 的数组，避免冗长说明并便于检索过滤。v1 可用值为：`data_qualification`、`missing_data_check`、`spike_data_qualification`、`stuck_signal_screening`、`historian_sampling_check`、`channel_comparison`、`neutron_current_channel_comparison`、`neutron_current_temporal_comparison`、`signal_path_context`、`neutron_current_signal_path_context`、`calibration_activity_check`、`baseline_reference_selection`、`neutron_current_measurement_context`、`detector_response_time_context`、`gamma_contribution_check`、`detector_calibration_context`、`signal_quality_context`。事件标签统一使用 `short_zero`、`sustained_zero`、`positive_spike`、`negative_drop`，范围标签统一使用 `single_channel`、`multi_channel_temporal_cluster`。

后续卡片不允许仅按标题、自然段或固定长度自动切分。新增一张卡至少需要：阅读原文、确认其与中子电流预检的关系、写明它可支持什么，并保留章节与行号定位。未完成这些步骤的 Markdown 段落不计入 300 张正式证据卡。

## 受控关联、检索与报告合同

`python3 -m evidencecard.cli` 实现事件卡之后的可审计层。它使用版本化的
`event_type × scope` 词表构造查询，在 `core`、`domain` 卡中做确定性 BM25 候选召回，
并保存查询、排名、分数与检索器版本。排名仅是候选，不会自动赋予
`direct_support` 标签，也不会改写或切分现有证据卡。

LLM 只能消费由**已确认** `direct_support` 关联生成的报告合同。合同包含原始事件
快照、可引用证据正文和适用性限制，输出要求为结构化 JSON；验证器拒绝未知引用、无
引用的“证据说明/核查建议”及明显的故障/因果断言。这样 LLM 的作用是受约束的报告
组织，而不是故障诊断器。

```bash
python3 -m evidencecard.cli build-llm-contract \
  --cases evidencecard/gold_standard/confirmed_cases.jsonl \
  --cards evidencecard/cards/core_seed_evidence.jsonl \
          evidencecard/cards/neutron_current_seed_evidence.jsonl \
  --catalog evidencecard/catalog/core_sources.jsonl \
  --links evidencecard/links/confirmed_links.jsonl \
  --event-id EVENT_ID --output /tmp/llm_contract.json

python3 -m evidencecard.cli validate-llm-report \
  --contract /tmp/llm_contract.json --report /tmp/llm_response.json
```

没有经确认的直接证据时，合同会显式为空；报告只能说明“资料不足以支持具体核查建议”，
而不能用候选卡补全判断。

## 历史的 100 个单事件—证据案例设想

本节保留的是早期“单张事件卡”设计，不是当前金标准入口。当前已采用事件组合、三证据组合和固定检查建议的
80 例草稿，见 [`../goldencard/README.md`](../goldencard/README.md)。

`gold_standard/` 中的一个案例以**一张事件卡**为单位，而不是一条零散链接。每个案例将包含：

- 完整事件卡；
- 固定的候选证据包；
- 对每条候选的 `direct_support`、`related_but_insufficient` 或 `not_relevant` 判断；
- 可支撑的预检说明及其边界。

最终抽取 100 个案例时，应按事件类型（零值、持续零值、尖峰、突降）、范围（单通道/多通道）和持续时间分层。现有本地 CSV 样本主要产生尖峰候选，不能单独构成最终 100 例金标准；完整数据接入后再按此规则抽样。

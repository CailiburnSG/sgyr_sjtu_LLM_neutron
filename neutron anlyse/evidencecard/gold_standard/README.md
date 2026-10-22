# 事件—证据金标准案例

目标是建立 100 个**完整事件级**案例，而不是 100 条单独的正向关联。每个案例以一张聚合事件卡为中心，包含 5–10 条固定候选证据卡及其人工复核标签。

```json
{
  "case_id": "GS-0001",
  "event_id": "...",
  "event_snapshot": {"event_type": "...", "scope": "..."},
  "candidate_evidence_ids": ["..."],
  "annotations": [
    {
      "evidence_id": "...",
      "label": "direct_support | related_but_insufficient | not_relevant",
      "evidence_role": "data_qualification_check",
      "supported_precheck_statement": "...",
      "boundary_note": "...",
      "review_status": "confirmed"
    }
  ]
}
```

## 抽样原则

- 先从正式 CSV 生成的聚合事件卡中抽样，不以历史快照作为正式金标准来源；
- 按事件类型、单/多通道范围、持续时间和记录编号分层；
- 同一长记录不要被相邻的高度相似事件大量占据；
- 候选证据包在人工标注前固定，避免标注者无限浏览全文；
- `direct_support` 必须只支撑一条不越界的预检说明，不能用于确认故障机理。

100 个案例完成后，才可计算 Evidence Recall@K、Evidence Precision@K、证据可用率、报告证据支撑率和无证据断言率。

## 实施状态与冻结规则

当前 `A1_1_head5000` 试点有 191 张聚合事件卡，但只覆盖 `positive_spike` 和
`negative_drop`。因此它可用于生成 100 个**候选包**、调通检索和标注界面，不能
被称为最终的 100 个分层金标准案例；`short_zero`、`sustained_zero`、趋势和一般瞬态
类型必须等正式记录接入后补齐。

候选包的产生与人工复核严格分开：

```bash
python3 -m evidencecard.cli sampling-plan \
  --events eventcard/output/A1_1_aggregated_cards.json --target 100

python3 -m evidencecard.cli make-candidate-cases \
  --events eventcard/output/A1_1_aggregated_cards.json \
  --cards evidencecard/cards/core_seed_evidence.jsonl \
          evidencecard/cards/neutron_current_seed_evidence.jsonl \
  --output evidencecard/gold_standard/A1_1_head5000_candidate_packages.jsonl \
  --target 100 --top-k 8
```

该命令只冻结受控查询、检索器版本、排序及候选集合，并将每条标签留为
`pending_user_review`。人工应逐条写入标签、可支撑的预检说明和边界说明；只有案例
中的全部标签均为 `confirmed`，且案例状态显式变为 `gold_standard_confirmed`，才能进入
检索和报告指标计算。候选包可在缺失分层时为凑足 100 条而回填已有类型，但元数据会
保留分层缺口，防止论文把试点覆盖误写为完整评价集。

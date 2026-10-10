# goldencard：预检案例—证据—检查建议金标准

`goldencard/` 保存中子电流异常预检的**预检案例—证据—固定检查建议**金标准；它不保存
故障原因诊断，也不要求人工为每个案例撰写自然语言报告。

一个案例的核心关系是：

```text
事件组合：记录中观察到了什么
  + 证据卡：为何某项核查在此条件下合理
  → 固定检查建议：人工下一步优先核查什么
```

每个 v1 案例最多关联一项检查建议；证据卡支撑“建议核查”，不证明当前事件的具体原因。固定
建议的定义、A3/A4 边界和 v2 `action_id` 见[固定检查行为.md](固定检查行为.md)。

## 当前阶段

当前已冻结四项检查建议 v2 和预检案例结构。`event_groups/` 的八个事件组、每组 10 张事件原子是
当前 80 例的**来源材料**，但它们本身不是最终金标准案例，也不应复用其旧单事件候选关联。

10 个试标案例保留在 [`drafts/precheck_case_pilot_10/`](drafts/precheck_case_pilot_10/)，30 个中间扩充
草稿位于 [`drafts/precheck_case_draft_30/`](drafts/precheck_case_draft_30/)。此前的
`drafts/precheck_case_draft_80/` 是按原始时间簇切分的探索稿，不作为当前训练/验证金标准。

当前金标准草稿是
[`drafts/precheck_case_balanced_80_eventgroups/`](drafts/precheck_case_balanced_80_eventgroups/)：仅从
`event_groups/` 的 80 个事件原子组合而成，四项建议各 20 例；每个预检案例包含 1--4 个事件、3 张
同一检查意图的并列证据卡和 1 项建议。草稿状态总览见 [drafts/README.md](drafts/README.md)；正式任务、量化和单建议约束见
[预检案例金标准与量化设计.md](预检案例金标准与量化设计.md)。

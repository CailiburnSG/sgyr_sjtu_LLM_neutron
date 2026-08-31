# 实验室环境执行清单：论文补充实验与验证

## 总体原则

本清单只列当前论文仍需由实验室环境、完整 archive 或人工专家补足的证据。它不是“尽可能多跑模型”的列表；每项都对应一个明确的论文缺口。

| 优先级 | 任务 | 所需环境 | 论文用途 | 可否直接写入结果 |
|---|---|---|---|---|
| P0 | Query formulation × chunking 鲁棒性检查 | GPU 服务器 | 补足跨 chunk length 的横向比较 | 仅在结果完成并审核后 |
| P1 | 全 archive 的确定性流程覆盖核查 | 可访问完整 CSV archive 的实验室环境 | 证明 workflow 可批量运行并产生可审计 observation artifact | 仅报告流程覆盖与数据健康 |
| P2 | 小规模专家证据审查 | 具备领域知识的人工审核 | 连接 retrieval/source priority 与证据适切性 | 需先定义标注规则 |
| P3 | Reranker、metadata filter 或更多 encoder | GPU 可选 | 后续方法消融 | 非当前稿件必要条件 |

P0 是唯一需要立即做的 GPU 实验。P1 推荐做，但不应替代 P0。P2 是人工审核，不应错误地当作 GPU 任务。不要将生成式 LLM、agent trajectory 或 fault diagnosis accuracy 混入当前 retrieval benchmark。

---

## P0：Query formulation × chunking 鲁棒性检查（优先完成）

### 要回答的问题

人工编写的技术细节 query 与四条 baseline query 的 source-priority 差异，是否在短、中、长三档代表性字符级 chunking 下仍可观察到？

### 唯一执行说明

完整命令、输出目录、行数验证与结果表述边界见：

[SERVER_CURSOR_QUERY_CHUNKING_TASK.md](SERVER_CURSOR_QUERY_CHUNKING_TASK.md)

固定矩阵为：

- chunking：`800/80`、`1200/120`、`1500/150`；
- encoder：两个已用 MiniLM；
- queries：4 条 baseline + 6 条人工技术细节 query；
- corpus scope：13 篇 IAEA core 加受控 supplementary expansion；
- 每个非零 scope：10 次固定 seed 的随机文档抽样。

### 交付与边界

- 提交六个 `chunking × encoder` 输出目录、验证结果和失败日志（如有）。
- 生成 trajectory、heatmap 和两档 scope 的 summary。
- 在结果审核前不改 `main2.tex`。
- 不把 6 条技术细节 query 写成自动生成 query；不重跑完整 17 配置历史网格；不引入 LLM、API 或 DeepSeek Harness。

---

## P1：全 archive 的确定性流程覆盖核查（推荐）

### 要回答的问题

在完整原始 neutron-current archive 上，measurement-side workflow 是否能在不改变输入记录的情况下，为每个可处理记录建立 workspace、完成已注册 probe，并留下可审计输出？

### 最小执行范围

1. 对完整 archive 的每个 CSV 运行既有初始化、数据健康、形态/关联、异常事件、lag 与极值相关 probe。
2. 每个原始记录使用独立 workspace；不得覆写 raw CSV。
3. 汇总一个不含原始波形、精确时间或敏感路径的 manifest；每行至少记录：

   - 匿名或内部 record ID；
   - 是否读取、排序并成功建立 active record；
   - 已完成/失败的 probe；
   - 缺失值、inactive channel 等数据健康标记；
   - condition report / alert summary 的相对位置或哈希；
   - 若失败，失败类别与日志位置。

4. 输出 aggregate coverage summary：记录总数、完整完成数、失败类别数量，以及不含诊断含义的数据健康摘要。

### 论文边界

可以支持：“workflow 在所访问 archive 上完成了多少记录的可审计处理。”

不能支持：fault prevalence、设备可靠性、物理机制或 end-to-end diagnostic accuracy。spike、zero、lag、同步关系均仅为观测产物。

完整敏感输出留在实验室受控存储中。若需同步到论文仓库，只同步脱敏 aggregate coverage CSV、运行配置/version manifest 与不含敏感数据的 README。

---

## P2：小规模专家证据审查（人工任务）

### 要回答的问题

对于预先抽样的一组 alert-summary / query / retrieved passage，检索结果是否为人工认为可用于工程核查的证据？memo 中引用是否确实支持对应陈述？

### 最小设计

1. 运行检索前固定抽样规则与 review rubric。
2. 抽取有限数量的 query--passage 或 memo-claim--citation 对，覆盖 core-only 与 corpus-expanded 条件、中英文 query 和至少两个 cue family。
3. 每项由领域人员标注：

   - passage 是否与技术检索意图相关；
   - passage 是否可支持对应 memo claim；
   - 是否缺少关键限定条件；
   - 不确定或不适用。

4. 记录一致性与分歧处理。样本小也可以，但必须如实报告范围。

这项任务可连接 source-priority 与 evidence appropriateness；仍不能成为 fault-label accuracy benchmark。

---

## P3：仅在 P0/P2 后考虑的扩展

以下都不是当前稿件必须完成的实验：

- metadata filter 或 source-priority reranker 的受控消融；
- 更多多语 embedding encoder；
- 生成侧 citation correctness / factuality 评测；
- DeepSeek Harness 的 agent-trajectory 或 tool-use evaluation。

每个扩展开始前必须明确输入、固定变量、指标、人工审核边界与允许的论文主张；不能仅因“能够运行”就纳入结果。

---

## 交付顺序与论文对应

1. 优先完成 P0；提交输出目录、验证结果和失败日志。
2. 若完整 archive 可用，执行 P1；只提交脱敏 coverage manifest / summary。
3. 与导师或领域人员确认 P2 的抽样和 rubric 后，再开始人工审查。
4. P3 需要研究问题与资源确认后才可启动。

P0 成功结果可能补入第 3 节 Evaluation Protocol 与第 4 节 Results and Discussion；P1 只在第 2 节或补充材料报告流程覆盖；P2 是第 5 节“缺少 relevance / citation-support 人工审查”的直接补充。在这些任务完成并审核前，`main2.tex` 的当前结论保持不变。

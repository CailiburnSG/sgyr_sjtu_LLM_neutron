# 论文大修改订蓝图

> 本文件记录论文 V3 的定位、结构与验证决策，不是聊天纪要。`paper/v1/` 是最早稿存档，`paper/v2/` 是已完成的稳定稿，`paper/v3/` 是正在重构的新稿；三者不混用正文、图片或表格路径。

## 1. 这篇论文要回答的问题

### 1.1 核心问题

核电仪表历史档案包含大量无统一样本级故障标签的多通道中子电流时序。直接把原始 CSV 交给 LLM 做故障判定既不可审计，也越过了工程责任边界；但逐段人工审查又无法在 archive 规模上执行。

本文应回答：

> 如何将无统一故障标签的原始中子电流时序转化为可审计观测，并以受来源策略约束的技术证据支持工程师复核？

### 1.2 中心命题

```text
raw measurement
→ deterministic observation
→ structured evidence interface
→ authority-aware retrieval
→ citation-backed candidate interpretation
→ engineering review
```

本文是 **evidence-constrained diagnostic assistance**，不是自动 fault classifier，不是根因识别器，也不是普通“chat with PDF”系统。

### 1.3 三条长期原则

1. **Do not diagnose before you describe.** 先陈述可复核的数据现象，再讨论候选解释。
2. **Semantic relevance is not evidence authority.** 相似度高不等于指定权威来源可见，也不等于证据充分。
3. **LLM should organize evidence, not manufacture evidence.** 数值观测由确定性工具产生；LLM 仅负责受约束的编排、检索意图和证据化表达。

## 2. 责任边界与可写结论

| 层级 | 责任主体 | 可写主张 | 不可写主张 |
|---|---|---|---|
| 测量层 | 确定性 probes | spike、zero、lag、共变、数据健康等观测事实 | 已确认设备故障或物理机制 |
| 状态与追溯层 | workspace / runtime | 输入、动作、参数和产物可追溯 | 运行约束本身保证诊断正确 |
| 证据层 | retrieval + source policy | 检索行为、来源优先级和配置敏感性 | `Priority@k` 等于人类相关性或证据质量 |
| 语言层 | LLM / memo composer | 将观测和可定位证据组织为候选解释 | 自动确认根因、替代工程师决策 |
| 工程层 | 人类工程师 | 对机制、上下文与下一步检查作判断 | 将自动链的输出视为最终运行决策 |

术语上优先使用 *unlabeled archive*、*without a unified fault ground truth*、*label-free descriptive observation*。避免把 condition report 称为标签，也避免把 signal event 称为 confirmed fault。

## 3. 从参考论文得到的结构原则

导师意见位于 `导师意见/`。重点参照论文不应被照搬，而应各自承担一种结构功能：

| 参照 | 应借鉴的内容 | 本文中的对应实现 |
|---|---|---|
| ChatCAD | 专业模型输出先转为语言可用的中间表示，LLM 再整合 | deterministic observations → alert summary → retrieval intent |
| AgentMD | 先验证工具质量，再验证工具使用，最后验证真实场景价值 | observation audit → evidence retrieval → expert usefulness |
| RADIANT-LLM | provenance、authority policy、human-in-the-loop 是安全关键系统的一部分 | source metadata、citation trace、工程师复核边界 |
| RAGChecker | 检索器与生成器应分开诊断，错误要可归因 | retrieval metrics 与 claim--evidence support 分开报告 |
| ARES | context relevance、faithfulness、answer relevance 是不同评价维度 | passage relevance、memo support、工程可用性分层评价 |
| LLM-TSFD | 工业时序中的 human-in-the-loop 定位 | 不将无标签数据伪装成 fault-classification benchmark |

在正式引用前，所有文献的 DOI、作者、出版状态和可支撑的具体表述必须再次核验。

## 4. 拟采用的论文总结构

### 1. Introduction

按四步写作：

1. 说明无标签核仪表 archive 的工程现实与审计要求。
2. 说明监督式故障分类、自由 LLM 推断、单纯文档 RAG 各自不能解决的问题。
3. 提出 measurement-to-evidence 的分层框架与责任边界。
4. 列出贡献：可审计观测接口、受来源策略约束的 evidence retrieval、分层可靠性评价。

Related Work 不另行机械拆分为“LLM/RAG/Agent”；在引言中围绕以下三条研究线组织：

- label-scarce industrial time-series diagnosis；
- tool-augmented and human-in-the-loop diagnostic assistance；
- evidence-grounded RAG in safety-critical domains。

### 2. Evidence-Constrained Diagnostic Assistance Framework

本节应围绕一张总架构图展开，图中明确展示：

```text
Measurement layer → Evidence interface → Authority-aware evidence layer → Engineering review
```

建议子节：

- 2.1 Problem setting, data roles, and scope
- 2.2 Deterministic observation construction
- 2.3 Observation packet and structured alert summary
- 2.4 Authority-aware retrieval and citation-bearing memo
- 2.5 Runtime, provenance, and abstention / review boundary

现有的 registered probes、workspace、active record、fail-closed 行为和运行时约束都应保留，但服务于“measurement authority”和“traceability”，而不是写成工程实现细节清单。

### 3. Layered Evaluation Design

本节不再只像 retrieval benchmark 的方法章，而要明确每项评价对应哪一层主张：

- 3.1 Evaluation questions and evidence hierarchy
- 3.2 Measurement records, technical corpus, and source policy
- 3.3 Observation-audit protocol
- 3.4 Retrieval-governance protocol: corpus expansion, query, chunking, encoder
- 3.5 Claim--evidence support and usefulness audit
- 3.6 Metrics and interpretation boundaries

### 4. Results

推荐结果顺序：

- 4.1 One traceable measurement-to-evidence case
- 4.2 Observation-layer audit
- 4.3 Similarity--authority divergence under corpus expansion
- 4.4 Query, language, encoder, and chunking interactions (P0)
- 4.5 Claim--evidence support and expert usefulness
- 4.6 Deployment implications

### 5. Discussion and Limitations

讨论可部署性、source policy、metadata/filter/reranker 的必要性，以及当前没有统一 fault ground truth 的边界。明确本文是后续 physics-informed fault-hypothesis 层的前端，而不是完整物理诊断系统。

### 6. Conclusions

回到三条长期原则，避免重复罗列模型或编码器细节。

## 5. 验证闭环：已有证据与必须补强项

### 5.1 已有、可保留的证据

- deterministic probes、操作定义与可追溯 workspace；
- 代表性 condition-report event inventory；
- 64-document corpus 的受控扩展实验；
- similarity 上升但 IAEA `Priority@10` 下降的结果；
- P0 的 query family × language × encoder × chunking 交互；
- strict chunk matching 与 document-level matching 的区分；
- 固定词切块的 MiniLM cross-check。

### 5.2 必须优先补强的证据

1. **Observation correctness audit**：选取有限数量代表性记录，请合格领域人员核对 spike、zero、lag、co-movement 等描述是否正确；不要求虚构 fault label。
2. **Passage relevance audit**：在代表性 query、corpus scope 和配置上标注 retrieved passage 为 relevant / partially relevant / irrelevant，以区分 authority policy 与技术相关性。
3. **Claim--evidence support audit**：从 memo 中抽取关键主张，标注 fully supported / partially supported / unsupported。
4. **Expert usefulness audit**：评价 condition report 与 evidence memo 是否减少筛查负担、是否指向合理的下一步检查、是否可能误导。

### 5.3 有价值但排在后面的扩展

- metadata filtering、source-aware reranking 或 authority-aware retrieval 的消融；
- 更多 multilingual encoder、chunking 或 corpus；
- 生成模型差异、query 自动生成和 agent trajectory；
- 与维修历史、运行工况、物理退化模型结合的 mechanism-hypothesis 层。

没有上述实际实验时，不得将它们写成已经验证的结果；可作为 discussion 或 future work。

## 6. 图表重构原则

主文应由少数“承担论证责任”的图表组成，不应让 20 张图平铺为结果堆积。

建议保留或重构为：

1. **Fig. 1：四层总架构与责任边界。**
2. **Fig. 2：measurement-to-evidence 的代表性 trace case。** 观测 packet / alert / evidence card / memo excerpt 连续呈现。
3. **Fig. 3：observation audit 汇总。**
4. **Fig. 4：similarity--authority divergence。**
5. **Fig. 5：P0 configuration interaction。**
6. **Fig. 6：claim--evidence support / expert usefulness。**

探针公式说明图、完整 query heatmap、语言拆分轨迹和模型细节图可视篇幅移至附录或补充材料。每张图必须先在正文说明其要回答的问题，再展示结果；图注只说明对象、条件和限定边界。

## 7. 当前稿的迁移规则

| 当前资产 | 大修改订后的角色 |
|---|---|
| `v2/sections/03_measurement_observation.tex` 与 `03_operational_definitions.tex` | V3 框架第 2 节的 measurement layer 候选素材 |
| `v2/sections/04_report_retrieval.tex` | V3 evidence interface 与 authority-aware retrieval 候选素材 |
| `v2/sections/05_runtime_reliability.tex` | V3 provenance / runtime boundary 候选素材 |
| `v2/sections/04_evaluation.tex` | V3 retrieval-governance protocol 的候选素材 |
| `v2/sections/05_results.tex` | V3 trace case、retrieval governance 与新增 audits 的候选素材 |
| `v2/sections/06_limitations.tex` | V3 limitations 与下一验证阶段的候选素材 |
| `v2/figs/fig01`--`fig20` | 逐张决定是否重绘、移附录或仅作 V2 存档 |

V1 与 V2 的旧正文和旧图不应直接混入 V3；只有经过新论证审查的内容才可作为素材迁入。

## 8. 推荐实施顺序

1. 先锁定标题、摘要中心句、研究问题和四层总架构图。
2. 设计 observation / passage / claim / usefulness 四类审计表单与抽样方案。
3. 完成可获得的人工核查，再决定主文能够主张到何种程度。
4. 基于最终证据重写 Introduction、Framework、Evaluation 和 Results；不要先局部润色。
5. 最后处理图表压缩、Related Work、摘要、结论与投稿格式。

V2 需要复现时编译 `paper/v2/main.tex`；V3 建立 LaTeX 主文件后只在 `paper/v3/` 内编译。每轮稳定后提交 Git。SJTU LaTeX 协作项目仅同步发生变化的 `sections/`、`figs/`、`tables/`、`refs.bib` 或 `main.tex`，避免整包覆盖活跃协作内容。

## 9. 当前写作检查清单

- [ ] 摘要、引言、方法、结果与结论是否都使用同一研究问题？
- [ ] 每项自动输出是否被称为 observation，而非 confirmed fault？
- [ ] 每个来源优先级指标是否明确不等于 relevance？
- [ ] 每条 memo 主张是否可以回到具体证据段落？
- [ ] 每个图表是否服务于一项明确验证问题？
- [ ] 每项未做的人工审计是否诚实地列为限制或未来工作？
- [ ] 每条新引用的书目信息、DOI 与支撑范围是否已核验？

## 10. 场景披露与中文优先写作策略

### 10.1 当前场景披露边界

在未获得导师、数据所有方或项目管理方明确许可前，反应堆型号、厂站身份、具体仪表系统名称和其他可识别信息一律不写入正文，也不通过猜测补全。当前可以安全、准确地使用的场景表述是：

> A plant measurement archive contains 42 long, seven-channel neutron-current records from four instrumentation-bank groups collected during the same plant campaign.

与之对应的中文表述是：

> 本研究使用同一核电厂采集周期内四个仪表组的 42 条多通道中子电流记录；每条记录包含 7 个中子电流通道和时间列，典型记录为约 $6\times10^5$ 个、采样间隔约为 1 s 的连续样本。

这足以支撑 archive scale、multichannel structure、label scarcity 和工程审计需求的论述。后续仅在获得书面或明确口头授权后，再按允许范围补充反应堆类型、探测器类别、仪表系统角色或具体监测任务。

### 10.2 先中文论证、后英文投稿

大修阶段先写中文的“论证稿”，目标是把科学问题和证据边界讲清，而不是产出可逐句翻译的中文论文。推荐顺序：

1. 用中文确认场景、问题、唯一 idea、方法因果链、可验证主张和限制。
2. 维护固定的中英术语表，避免同一概念在不同章节漂移。
3. 在论证与图表结构稳定后，按英文期刊习惯重写英文正文；不逐句直译中文。
4. 标题、摘要、贡献、图注和关键术语较早形成英文工作版本，用于检查国际读者能否理解核心主张。

当前建议优先写成中文的四段骨架：

- **场景**：数据来自什么工程任务、哪些信息可写、哪些信息需匿名；
- **问题**：为什么无统一 fault ground truth 的 archive 不能被包装成普通监督分类任务；
- **idea**：为什么需要 auditable measurement-to-evidence interface；
- **主张与边界**：本文证明了什么，尚未证明 diagnostic accuracy、root-cause accuracy 或完整工程效用。

### 10.3 推荐的新旧稿管理方式

当前 `paper/v2/` 是已经编译、提交并推送的稳定稿，应保留为只读基线。V3 的中文研究问题、章节结构和总架构图在 `paper/v3/` 中确认：

```text
paper/
  v1/                                 # 最早稿存档
  v2/                                 # 已完成的 retrieval-robustness 稳定稿
  v3/                                 # 中文论证、重构后的英文 LaTeX 与图表
  PAPER_DISCUSSION_GUIDE_zh.md        # 跨版本的决策依据
```

V1 与 V2 都已被保留为可编译、可回溯的历史版本；V3 不与旧稿共用 `sections/`、`figs/` 或 `tables/` 路径。

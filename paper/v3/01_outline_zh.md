# V3 中文章节提纲

## 1. 引言：为什么需要 measurement-to-evidence interface

- 工程场景、无统一故障标签和可追溯性要求。
- 监督分类、自由 LLM 推断、单纯文档 RAG 的不足。
- 本文问题、中心 idea、贡献和边界。

## 2. 相关工作

- 工业时序与数据驱动故障诊断：简要说明其依赖预设任务、标签或故障场景的常见前提。
- 核工业时序与在线监测：重点说明仪表通道监测、中子噪声和特定场景验证的工程基础，以及无统一标签 archive 的差异。
- 工具增强诊断与人机协同：先交代通用语言代理/工具调用，再落到核工程中确定性测量与工程责任边界的需要。
- 证据约束 AI 与安全关键 RAG：先交代通用 retrieval-grounded generation，再重点讨论核工程中的来源、引用和人工复核。
- 研究缺口：收束到“无统一故障标签的核仪表原始时序”如何连接可追溯观察与受来源策略约束的证据侧解释。

## 3. 无标签中子电流档案的可追溯观测与证据约束解释

- 研究对象、数据结构与披露边界。
- 测量侧：逐记录初始化、数据健康核查，以及形态、事件、共变、滞后、极值和快照等预先定义的分析工具。
- observation packet：完整 condition report 与面向检索的 compact alert summary 的分工；操作性阈值与其非诊断属性。
- 证据侧：带来源 metadata 的资料库、由告警字段约束的检索意图、段落定位及 evidence-linked memo。
- 接口运行约束：active record、预先定义的分析工具、报告—摘要链接、引用关联与工程师复核边界。

## 4. 分层评价设计：验证接口，而非宣称诊断准确率

- 评价问题与证据层级。
- observation verification（观测核查）。
- retrieval-governance：corpus expansion、query、language、encoder、chunking；说明相似度与核心来源可见性为何不能混同。
- self-retrieval 作为检索单元与分块影响的辅助核查；段落相关性、claim--evidence support 与 expert usefulness 留作后续验证层次。

## 5. 结果：接口为什么需要来源治理

- 代表性 measurement-to-evidence trace case。
- 观测层核查。
- similarity--authority divergence。
- P0 configuration interaction（作为来源治理的支持性证据，而非普适配置排名）。
- claim--evidence support / expert usefulness。

## 6. 讨论与局限

- 安全关键部署中的来源策略与人机边界。
- 没有故障真值、人工 relevance 与 memo 专家复核的限制。
- 面向物理机理假设、运行历史和维护反馈的后续层次。

## 7. 结论

- 重申“先描述、后诊断”“相似度不等于权威性”“LLM 组织而不制造证据”。

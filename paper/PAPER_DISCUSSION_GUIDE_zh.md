# 论文修改决策指南（按正文结构对应）

> 本文件是 `main2.tex` 的长期修改依据，而不是按时间排列的聊天纪要。每一条讨论应归入其对应的论文节；若某项讨论已落实且不再影响后续写作，只在该节保留简短的“已落实”说明。原稿 `main.tex` 保持不动。

## 置顶：全篇长期要求

### A. 论文定位与主张边界

- **论文定位**：面向没有统一故障真值标注的原始中子电流时序数据，提出证据约束的诊断辅助工作流（evidence-constrained diagnostic assistance）。
- **不能宣称的事**：系统不自动确认故障、不证明根因、不替代工程师、更不直接支持运行决策。
- **应当强调的链条**：原始测量记录 → 可审计观测 → 结构化 alert summary → 技术手册证据 → 带引用的辅助诊断 memo → 人工复核。
- **术语约束**：避免把原始数据称为“弱标签数据”。更准确的说法是 *unlabeled / without a unified fault ground truth*；LLM 生成的 condition report 不是标签，也不是 ground truth。

### B. 数据、文件与证据边界

- 原始测量 archive 是整个工作流的输入；仓库中未包含全部 archive，只是 Git 传输限制，不意味着实验只处理少量文件。正文不得以仓库内的单个文件名代指整个方法或数据集。
- JSON condition report、alert summary 和 memo 都是工作流产物；它们可作为可审计中间结果，不能反向充当原始故障标注。
- 技术手册 corpus 同样是系统输入：它提供解释性证据，与测量 archive 的“观测来源”角色不同。
- 图表和结论只能来自已有 CSV、JSON、脚本或可定位文献。不得将合理外推写成实测事实。

### C. 写作与结果表达

- 用“观测事实”“候选机制”“手册支持的解释”“需人工核查”区分证据等级。
- `Priority@k` / core purity 衡量的是预设权威来源的优先级，不是通用 relevance，更不是诊断准确率。
- 信号事件统计（spike、zero dropout、共变等）不是设备故障计数。
- 结论必须带条件：限定在当前 corpus、query set、encoder 和 chunking grid 下；不作普适的语言、模型或分块优劣断言。

### D. 维护规则

- 新讨论优先写到对应章节的“待修改 / 待验证”下；跨章节原则写入本置顶区。
- 已落实且不再影响后续决策的临时推演删除，不保留为聊天流水账。
- 本阶段优先修改论证、组织、图表和可复现说明；不重构已跑通的 Agent、工具路由、原始实验资产或原始数据。

### E. 当前结构决定（2026-08-31）

- **保留六个一级章节**：Introduction → System Design and Methodology → Evaluation Protocol → Results and Discussion → Limitations and Threats to Validity → Conclusions。它们已经适合本研究，不应为了模仿 MCP-SIM 改成“Results / Methods”倒置的 Nature 式版式。
- **只做内部重排（已落实）**：总览工作流图与“转换契约”说明已从 Introduction 移至第 2 节开头；第 2.1 仍以 Data Resources 开始；第 2.2 已调整为“初始化 → probes → 操作定义 → observation packet / alert summary”的因果顺序。
- **第 3 节保持独立**：它负责验证阶梯，不和第 2 节的方法实现混写。
- **第 4 节加强而不拆分**：保留 Results and Discussion 合并形式，但让 4.1 成为完整 trace case，4.6 成为综合讨论与部署含义。

### F. 当前排版基线（2026-08-31）

- `main2.tex` 已采用 Elsevier `5p` 双栏版式，作为当前的阅读、图表密度和篇幅判断基线；原始 `main.tex` 不受影响。
- 双栏下的图、表和公式均应以单栏宽度优先设计；只有确有跨栏比较价值的图表才使用双栏浮动。当前 PDF 为 9 页，页数不应直接与先前 12pt 单栏预印本页数比较。
- `main2.tex` 当前采用数字上标文内引用和按首次出现顺序编号的参考文献表，以提高双栏阅读紧凑度。此为工作稿样式；确定目标期刊后，可将 `numbers` / `elsarticle-num` 切回期刊要求的作者--年份体例而不改变文献数据库。

---

## 1. Introduction

### 本节职责

说明问题背景、相关工作缺口、论文问题定义和贡献。Related Work 合并在本节，不单列章节。

**已落实的结构微调。** Introduction 现在只在贡献列表结尾回指系统转换契约，不承担 Fig. 1 的详细解释；Fig. 1 的主位置已移至第 2 节开头。这样引言只建立问题与承诺，系统章节再完整解释状态、产物和人工边界。

### 已确认的内容

- 研究问题不是“LLM 能否自动诊断故障”，而是：在标签不足且审计要求高的核工场景，如何使语言模型以可追溯方式参与诊断辅助。
- 三条贡献主线必须在引言中一次性提出：
  1. 受约束的零先验时序观测；
  2. 从 alert summary 到带引用 memo 的报告驱动 RAG；
  3. 对证据检索层在语料扩展、双语 query 与分块变化下的鲁棒性检验。
- 引言需要明确：检索评测不是附加 benchmark，而是系统“证据层是否可信”的压力测试。

**可迁移的研究问题写法。** 借鉴 MCP-SIM 的“不是一次生成，而是受控循环”的问题设定，本文可更明确地把贡献表述为一组可验证的转换契约：原始时序不能直接跳到诊断结论，必须依次转换为观测、检索意图和可定位证据。这样，Agent、RAG 与评测不再是三个并列模块，而是同一条证据转换链上的三个验证点。

### 待修改 / 待核对

- [ ] 检查摘要、引言首段、贡献列表和结论中的问题定义是否完全使用同一套表述。
- [ ] 将 related work 压缩为服务于上述缺口的比较，避免扩写泛泛的 LLM/RAG 背景。
- [ ] 根据目标期刊补足核工诊断、工具调用 Agent 与 evidence-grounded RAG 的代表性引用。

**新增参考：MCP-SIM。** Park, Moon and Ryu 的 MCP-SIM（npj Artificial Intelligence, 2026, DOI: `10.1038/s44387-025-00057-z`）可作为“多 Agent、共享持久状态与结构化中间产物用于科学工作流”的邻近工作引用。引言中应借其说明一般性 agentic scientific workflow 的趋势；同时必须立刻区分本文的对象是安全相关测量的证据约束辅助，而非从自然语言生成物理仿真或追求全自动闭环。

---

## 2. System Design and Methodology

### 第 2 节开头：workflow overview（已落实，无需新增编号）

在 `\section{System Design and Methodology}` 后、`2.1 Data Resources` 前已加入短的总览段并放置 Fig. 1。段落定义全链条的转换契约：measurement record → observation packet → alert summary → retrieved evidence → citation-bearing memo → engineering review。图中明确哪些对象是状态、哪些是派生产物，以及人工复核位于自动链之外。

### 2.1 Data Resources

#### 2.1.1 Neutron-current measurement archive

**本节应写什么。** 交代原始多通道中子电流 archive 的数据形态、时间字段、通道记录和适用范围；它是观测来源，不是标注数据集。

**必须保持的边界。** 完整 archive 受传输和运行敏感性限制而未全部纳入 Git；这不是正文中需要“自爆”的限制说明。正文应以整个 archive / workflow 为对象，避免出现 `A1_1`、`A2_1` 等仓库样例文件名。

**待补充的证据。** 若可公开获得测量布置或通道关系，应增加脱敏示意图和可核验说明：通道相对位置、CSV 列对应关系，以及图仅表示抽象测量关系、不代表具体厂站设计。没有该资料时，只写多通道统计共变与同步事件，不写“相邻探测器”“环向位置”等几何因果解释。

#### 2.1.2 Technical evidence corpus

**本节应写什么。** 将技术手册 corpus 作为系统的第二类输入，解释其提供的是可检索的解释性证据，而不是与原始时序混为一类的数据。

**已确认。** corpus 共 64 篇技术文档，其中固定 IAEA core 为 13 篇、same-domain supplementary documents 为 51 篇。补充资料不是无意义噪声；它们是受控扩展实验中真实的同领域证据源。

#### 2.1.3 Data roles and semantic boundary

**本节的核心桥梁。** 测量 archive 产生可观察现象；技术 corpus 回应结构化检索意图；condition report / alert summary 是二者之间的语义接口。它隔离自由文本解释与检索输入，最终 memo 仍由工程师审核。

**已落实。** 第二章已不再把语料库首次留到 Evaluation Protocol 才定义。

### 2.2 Measurement-side observation construction

#### 2.2.1 Objective and zero-prior scope

“零先验”指不以故障标签库、固定通道物理映射或手工频带作为推理前提；不等于没有领域知识，也不等于自动确认故障。

#### 2.2.2 Workspace initialization, data health, and deterministic probes

**本节应写什么。** 时间排序、数据健康检查、形态发现、异常/工况分段、时滞、极值、共线性、同步组和空间快照等可复核探针。

**表达要求。** 输出首先是 spike、zero dropout、共变或工况变化等观察事实。任何原因解释必须后置为候选机制，并附证据或人工核查需求。

#### 2.2.3 Operational definitions and auditable interface

**保留公式的原则。** 滚动中位数/MAD spike 规则、Pearson 共线性、事件定义和 alert-summary 构造公式应保留，因为它们将“工具分析”变成可复现的操作定义，而不是为了凑篇幅。

**待核对。** 每个公式旁应说明输入、阈值或统计含义，并让读者能将其与后续图表和 condition report 字段对应。

**可迁移的“中间契约”思路。** 将每次测量侧分析视为一个 observation packet：它至少保留数据时间范围、通道范围、所用确定性 probe、参数/阈值、观察到的事件和不确定性说明。condition report 是这个 packet 的机器可读表示，alert summary 是其受控压缩版。这样可把“Agent 做了分析”转化为可检查的输入—处理—输出契约；不需要新增模型，也不意味着将 report 误当作标签。

#### 2.2.4 Condition report and structured alert interface

condition report 是测量侧的派生产物，alert summary 是用于检索的受控摘要；二者均不是标签。需要持续检查是否有文件级样例名称渗入此处的通用流程表述。

**已落实的顺序调整。** 操作定义现已位于 report 输出接口之前：2.2.1 scope → 2.2.2 initialization/data health → 2.2.3 deterministic probes → 2.2.4 operational definitions → 2.2.5 observation packet, condition report and alert summary。没有删除内容；输出接口已扩展为 observation packet / report / summary。

### 2.3 Report-driven evidence retrieval

**本节职责。** 只回答“结构化观测如何成为检索意图并形成证据化 memo”：报告解析、术语增强查询、来源策略、证据组织与引用输出。

**主张边界。** 手册证据可以支持候选机制、核查路径或处置建议，不能仅凭检索结果确认具体设备故障。来源优先策略应表述为部署政策，而非“IAEA 结果天然更相关”。

**待修改 / 待验证。**

- [ ] 使 alert summary 字段与实际 retrieval query 构造一一对应。
- [ ] 使 memo 中每一条解释均能回指到检索片段或手册出处。
- [ ] 后续若增加 metadata filter、reranker 或术语扩展，应在本节作为方法变体介绍，并在第 3 节评估。

### 2.4 Constrained tool use and runtime reliability

**本节应保留，且不是开发抱怨。** workspace blackboard、唯一 CSV 文件入口、状态文件解析、注册工具 allowlist、brace-balanced JSON extraction、report/alert-summary 分离和 citation-bearing retrieval，构成运行时约束。

**论文命题。** 这些机制应被写成：在局部、弱约束的 LLM 工具调用环境中，如何维持多步时序分析的状态一致性、工具可控性、输出可审计性和证据约束。

**具体风险与对应措施。** 路径漂移、raw/sorted 文件混用、JSON fence 或截断、虚构工具、过长 condition text 与无证据诊断文本，都应与相应控制措施成对出现。最终审查和决策权始终属于人类工程师。

**可迁移的闭环，但应改为“安全停机式”而非全自动修复。** 适合本文的控制循环是 `detect → validate → repair-or-abstain → record`：发现状态或格式错误后，系统只可重建派生产物、重新调用注册工具，或标记为“需要人工复核”；不得自动改写原始记录、补造物理机制或绕过来源约束。该循环的价值是减少不可审计的流程失败，而非宣称自我纠正后就获得了正确诊断。

**从 MCP-SIM 可借鉴的呈现方式。** 用一张主流程图清楚标出状态拥有者、结构化交接物和每次失败后的回路；在文字中把每个控制机制写为“风险 → 状态/动作约束 → 可审计产物”。不能照搬其“全自动、自纠正、无人工干预”的定位，因为本研究必须保留工程师复核和证据约束边界。

---

## 3. Evaluation Protocol

### 3.1 评测对象与边界

评测对象是 **evidence-retrieval layer** 的行为，而不是诊断准确率、根因识别率或生成文本的事实正确性。应先说明：第 3 节检验的是当部署政策要求优先一组预定义权威来源时，检索能否在 corpus 扩展后维持该偏好。

**结构判断。** 第 3 节当前的“评测问题 → corpus/source policy → queries/expansion → metrics/self-retrieval → CPU comparison → interpretation boundary”顺序是正确的，应保留。需要加强的是开头的验证阶梯图或一张简表，使读者一眼知道此节只验证证据链的哪些层次。

### 3.2 Corpus、source policy 与实验变体

- 历史鲁棒性实验：`nomic-embed-text`，17 组 Markdown index configurations；chunk sizes 为 800、1000、1200、1500，overlaps 为 50、80、100、120、150 的有效组合。
- 独立 CPU encoder benchmark：240-word chunks、24-word overlap、两个 MiniLM encoder。
- 两套 index construction 的绝对 cosine 分数不可直接横比；CPU benchmark 用于检验 source-priority 现象是否在独立编码器与分块设置下仍出现。

### 3.3 Queries 与受控 corpus expansion

- 固定四个双语 queries：`中子`、`neutron`、`中子测量电流`、`neutron measurement current`。中文 phrase 不得换成未实际运行的同义表达。
- 以 13 篇 IAEA core 为固定池，supplementary documents 随 $m\in\{0,5,10,\ldots,51\}$ 受控加入。
- $m=0$ 为固定 core-only pool。历史实验中，$m>0$ 时每个 query、每个 index configuration 随机抽样 100 次；CPU benchmark 中每个规模、query、encoder 随机抽样 10 次。
- 检索返回 top-$10$ chunks。

### 3.4 Metrics、self-retrieval 与统计汇总

- corpus-scope retrieval 记录 top-1、top-3 mean、top-10 mean cosine、IAEA Priority@10 和 first-IAEA rank。
- `Priority@k` 是 source-priority policy adherence，不等于人工相关性。
- self-retrieval 使用 `first_sentence`、`title`、`random_window`、`domain_term` 四种 query mode；Fig. 5 仅展示 `first_sentence`。$m=0$ 使用 80 probes；$m>0$ 为 10 trials，每 trial 80 probes。
- strict Recall@k、document-level Recall@k 与 MRR 都应保留。strict/document 的区分避免将 overlap 带来的相邻 chunk 一概误判为无关。
- 历史 scope CSV 内的标准差是单一 configuration 中随机抽样的波动；Fig. 4/5 阴影带是先对每个 configuration 取均值、再跨 17 个 configurations 聚合的标准差。两者不得混用。CPU 结果的标准差来自其 10 次 document draws。

### 3.5 待补强但不能虚构的评估

- [ ] 小规模人工 query--document relevance / citation-support 标注，以连接 source priority 与真实证据适切性。
- [ ] generation-side factuality 或 citation correctness 评测。
- [ ] 在资源允许时测试 reranker、metadata filter 或更多多语 encoder；未实测前不能写入结果。

**从 MCP-SIM 可借鉴的评测结构。** 它将任务按难度分层、用一张表说明每层挑战和目标，并用 component ablation 将系统机制与结果连接起来。对本文，可迁移为“观测/检索场景矩阵”或“运行时约束消融”，例如比较是否使用 alert summary、source policy 或受控 workspace 时的可审计性与检索行为；只有在真实运行后才可写入正文。不能迁移其成功率或自动化程度指标，因为本文没有故障真值和同构 benchmark。

**推荐的验证阶梯。** 不要让所有验证都落在“最终诊断是否正确”这一项上。可依次验证：(1) 原始数据到 observation packet 的确定性和完整性；(2) packet 到 alert summary 的字段保留与语义压缩；(3) alert summary 到检索结果的来源优先与文档级命中；(4) memo 中每项陈述的 citation support；(5) 工程师对候选机制的复核。现有证据主要支撑第 (1)--(3)；第 (4)--(5) 是未来验证计划。这个阶梯能让已有结果被严谨使用，而不虚构端到端 fault accuracy。

---

## 4. Results and Discussion

### 4.1 Case study: from observation to evidence

**应呈现的链条。** 对代表性多通道记录展示：可复核的观测 → alert summary → 检索到的手册证据 → 带引用 memo → 仍需人工核查的部分。

**必须避免。** 不使用样例文件名代表整个 archive；不把 spike episode、isolated-zero 或共线性统计写成确认的设备故障。

**图表方向。** 代表性波形是必要但不充分的。后续可在已有统计支持下加入分布图、矩阵/热图、分象限图或九宫格式多面板图；每一幅图必须回答一个具体问题，不为“看起来丰富”而外推或造数。

**可迁移的“困难案例”设计。** 只保留一个最能暴露流程约束的代表性案例，但展示完整 trace，而不是只给漂亮波形：原始窗口与数据健康结果 → observation packet / alert summary → 检索证据卡片 → memo 中的候选解释与人工核查项。它在本文的作用是证明可审计链条如何工作，不是作为故障正确性的单例证明。

**已落实的结构调整。** 本小节保留为第 4 节第一节，标题已改为 `Traceable case study: from observation to evidence`；波形图被定位为 trace 的第一证据，而非独占案例。后续仍应加入一个 compact alert-summary / evidence-card / memo-excerpt 面板或表格，而不必增加更多无上下文的单例波形。

### 4.2 Similarity and source priority can diverge

**已支持的发现。** 在当前 `nomic-embed-text`、corpus 和 query 设置下，加入同领域补充资料可提高向量相似度，同时降低 IAEA priority；相似度不能单独作为证据层可靠性的代理指标。

**讨论要求。** 解释 non-core 排前不必然错误；本研究考察的是一项部署政策下的权威来源优先级。将其与一般 relevance 明确分开，并在第 5 节承认未进行人工 relevance 标注。

### 4.3 Language and query formulation dominate the tested chunking range

**已支持的发现。** 在已测试的 encoder、语料、queries 和 chunk/overlap grid 中，语言与 query 信息量的影响通常大于 overlap 的微调。

**表述边界。** 这是当前设置的经验发现；更换多语 embedding、查询模板或重排序器后可能改变，不能提升为普适结论。

### 4.4 Strict and document-level relevance answer different questions

应将 strict node matching 与 document-level matching 的差异解释为 overlap chunking 的评价问题：document-level Recall@10 较高并不自动证明检索内容完全正确，而是说明仅以 node-level 命中会低估同文档近邻片段的可用性。

### 4.5 Independent CPU embedding-model comparison

**写法要求。** 这是真实运行的独立 encoder 比较，不能称为外推。配置细节放在第 3 节；本节只解释测得结果、与历史 index 的可比性边界，以及对部署的意义。

### 4.6 Deployment implications

部署建议应从已有结果自然导出：术语增强、source-priority 策略、metadata filter / reranker 的后续验证、人工复核。不能把建议写成已经通过端到端故障准确率证实的方案。

**已落实的结构调整。** 标题已改为 `Discussion and deployment implications`。这一节应显式综合 4.2--4.5，而不是只列建议：为何 cosine 不够、为何 query 要术语化、为何 document-level matching 要与 strict matching 并报、为何人工复核仍不可省略。

**从 MCP-SIM 可借鉴的图表逻辑。** 它用“总览架构图 → 任务/复杂度设计 → 汇总定量图 → 一个高难案例 → 产物示例”形成由方法到证据的阅读路径。本文的对应顺序应是“工作流总览 → 数据与受控实验设计 → corpus-scope/self-retrieval 定量结果 → 一个观测—证据案例 → alert summary / citation-bearing memo 示例”。

---

## 5. Limitations and Threats to Validity

### 必须保留的局限性

- 没有统一 fault ground truth：案例证明流程可运行、输出可读，不独立证明诊断结论正确。
- retrieval corpus 与 relevance coverage 有限：core priority 不是通用 relevance，缺少人工相关性和引用支持标注。
- embedding、query、chunking 与 generation 的边界：当前实验不构成通用模型排名，也未完成 generation-side factuality benchmark。
- 当前测量结构资料不足：未公开验证的通道几何或物理映射不应写成机制结论。

**由 MCP-SIM 反向提醒的边界。** 即使一个系统拥有日志、回路和结构化中间状态，也只能证明流程可复现或在定义任务上运行成功，不能自动推出科学结论正确。本文应主动将“流程可靠性”“检索证据覆盖”和“工程诊断有效性”分层陈述，避免借用 Agent 论文常见的全自动/强泛化语气。

### 下一阶段验证优先级

1. 小规模专家核查观测事实、引文适切性和 memo 可操作性；
2. query--document relevance / citation-support 标注；
3. metadata filter、reranker 或多语 embedding 的受控消融；
4. 在可获得外部记录时，补充 observation-to-fault 的独立验证。

---

## 6. Conclusions

### 本节应回收的结论

- 工作贡献的是一条受运行时约束、证据约束且可审计的诊断辅助链条。
- 实验表明，证据层可靠性不能只由 cosine similarity 衡量；语料扩展、语言和 query formulation 会改变 source-priority 行为。
- 结尾应重申人工复核与后续验证需求，不把系统写成自动故障诊断器。

### 待核对

- [ ] 结论中的每一项贡献都能回指第 2--4 节的实际方法或结果。
- [ ] 删除超出当前证据范围的性能、因果或部署成熟度措辞。

---

## 附：当前修改范围与优先级

### 本阶段应修改

1. 统一摘要、引言、系统、评测、结果和结论的“证据约束诊断辅助”叙事。
2. 补足方法复现信息、指标解释、结果定量化与“观测—证据—人工核查”映射。
3. 改善图表的专业性和信息密度，但只使用已有证据可支持的统计与可复现脚本。

### 本阶段不修改

- 不重构 `code_ref/` 的 Agent、工具路由和 workspace 协议。
- 不改写或清理原始 archive、案例产物、向量索引和已有实验 CSV。
- 不补造故障标签、准确率、恢复率或未运行 embedding 结果。
- 不删除 non-core 资料来人为提高 core priority。

### 写作篇幅目标

在未确定期刊硬性要求前，正文可朝约 6,000--7,500 英文词推进。优先增加可复现细节、主要结果与不确定性、案例证据链和部署边界；不要用泛泛 LLM/RAG 背景凑篇幅。

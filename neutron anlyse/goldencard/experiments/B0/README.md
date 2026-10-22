# B0：BM25 检索 + 证据类型投票基线

## 目的

B0 是不使用 LLM 的传统对照方法。它检验“仅依靠关键词检索和已有证据类型标签，能否完成证据辅助的
预检行动选择”。它不读取任何案例的金标准建议或金标准证据作为预测输入。

## 方法

```text
事件组合摘要
  → 关键词查询
  → BM25 在 300 张证据卡中取 top-K
  → 保留并呈现全部 top-K 候选证据
  → 读取全部 top-K 的 applicability 标签
  → 对 A1--A4 归一化标签投票
  → 输出一项检查建议
```

### 查询

查询由案例内的 `event_type`、`scope` 和固定的 `neutron current`、`anomaly precheck` 串接而成。例如：

```text
neutron current positive spike single channel anomaly precheck
```

BM25 在每张卡的正文、`topic_tags` 和 `applicability` 中做词面匹配；检索范围为完整 300 卡库。

### 标签投票

| 建议 | 投票使用的证据标签 |
| --- | --- |
| A1 现场操作/校准核查 | `calibration_activity_check` |
| A2 横向通道比较 | `channel_comparison`、`neutron_current_channel_comparison` |
| A3 记录与时间戳处理 | `data_qualification`、`missing_data_check`、`stuck_signal_screening`、`historian_sampling_check` |
| A4 信号/数据传输路径 | `signal_path_context`、`neutron_current_signal_path_context` |

投票按每个行动的标签数归一化，防止标签更多的 A3 仅因集合较大而取得额外优势。这个映射来自四项
行动定义与证据卡既有 `applicability` 语义，不来自 80 个案例的正确标签。

## 正式对照口径

正式 B0/B1 对照固定使用同一个 Top-K 候选证据包，并将包内全部卡呈现给使用者。B0 对全部 Top-K 的
`applicability` 标签机械投票；B1 阅读同一完整包后直接输出行动。检索质量以严格 Evidence P/R/F1@K 与候选
覆盖@K 报告一次；B0/B1 的主比较是相同 K 下的行动 Accuracy 与 Macro-F1。

## 结果：候选规模 K 扫描

| 指标 | 结果 |
| --- | ---: |
| 案例数 | 80 |
| 证据库 | 300 张卡 |
| 候选规模 | `K={3,5,8,10,12,15,20}` |
| 最佳 Action Accuracy | 0.463（K=15） |
| 最佳 Action Macro-F1 | 0.360（K=15） |
| K=12 的金标准行动证据覆盖@K | 0.925 |

完整数值（含 Precision、Recall、F1）见 [`results/b0_k_sweep_summary.md`](results/b0_k_sweep_summary.md)，逐行动
分解见 [`results/b0_k_sweep_by_action.md`](results/b0_k_sweep_by_action.md)。严格 Evidence F1@K 要求命中
该案例指定的三张卡。**金标准行动证据覆盖@K**更宽松：只要 top-K 中有一张属于该案例正确建议类别下的
5 张可接受直接支持卡，即记为一次覆盖。它是事后使用金标准计算的候选可用性指标，不表示系统已经得出
正确行动结论。

## 结果分析

- K 增大后，正确建议类别的候选证据很快进入候选包：K=12 的金标准行动证据覆盖@K 已为 0.925；
  但即使 K=15，标签投票的 Action Macro-F1 仍只有 0.360。
- 因此候选覆盖与行动结论必须分开解释：例如 K=10 的覆盖率为 0.887，但行动 Macro-F1 仅为 0.196；
  K=15 的覆盖率仍是 0.925，行动 Macro-F1 才升至 0.360。候选中“有正确资料”只是投票器或 LLM
  做对的必要条件，不是充分条件。
- 关键词能找到主题相近的资料，却不能判定这些资料在当前事件组合下应支撑通道比较、记录处理还是传输路径
  核查。
- 这说明“词面检索到相关文献”不等于“理解证据应导向何种预检行动”。B0 的局限来自它不阅读正文含义、
  不整合多个事件、也不推理证据—行动关系。
- 因而后续 B1/B2 的增益应同时报告行动指标和两种证据指标，不能仅比较行动 Accuracy。

## 复现

在仓库根目录运行：

```bash
python3 'neutron anlyse/goldencard/experiments/B0/run_k_sweep.py'
```

结果会覆盖本目录 `results/` 下同名文件，不会改写正式金标准。

## 文件

- `b0_bm25_tag_vote_baseline.py`：单个 K 的实验代码；
- `run_k_sweep.py`：完整 K 网格运行器；
- `results/top_k_XX/`：各 K 的逐例查询、检索、投票分数与指标；
- `results/b0_k_sweep_summary.md`：K 扫描汇总表；
- `analyze_candidate_ranks.py`：解释 Hit@K 随 K 变化的排名分析脚本；
- `results/b0_first_acceptable_rank_analysis.md`：正确建议类别首张证据的 BM25 排名分布；
- `results/README.md`：结果文件说明。

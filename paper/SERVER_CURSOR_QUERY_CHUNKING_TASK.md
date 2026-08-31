# GPU 服务器任务：query formulation × chunking 鲁棒性检查

## 目的

在实验室 GPU 环境中运行一个**小规模、受控的检索鲁棒性检查**：检验已观察到的 query formulation sensitivity 是否在三档代表性的历史字符级 chunking 设置下仍存在。

这**不是**完整的 17 组配置 sweep，也**不是**历史 `nomic-embed-text` 实验的复现。

本任务只能支持如下条件性结论：

> 在所评估的语料库与 encoder 条件下，query wording 可能改变 IAEA source priority；这一现象应在短、中、长三档代表性 chunk length 下检查。

技术细节 query 是依据已记录观测、由人工编写的 query；不得声称由时序工作流自动生成。

## 禁止修改或声称的内容

- 在结果审核前，不修改 `paper/main2.tex`、论文已有图或正文结论。
- 不覆盖 `evidence/rag_results/output_mdselfcompare_*` 或 `evidence/rag_results/output_mdselfretrival_*`；它们是历史结果。
- 不运行 `--all-configs` 的完整 17 组网格。
- 不增加 LLM、API key 或外部服务；本任务仅为 embedding retrieval。
- 不编造缺失结果；若运行失败，保留 error log 并如实报告。

## 仓库中已具备的输入

| 项目 | 路径 | 作用 |
|---|---|---|
| 64 篇文档语料 | `corpus/md/` | 13 篇 IAEA core + 51 篇 supplementary documents |
| Query 说明 | `evidence/rag_results/query_formulation_sensitivity/technical_detail_query_pilot/query_set.json` | 4 条 baseline query + 6 条人工技术细节 query |
| 执行脚本 | `paper/scripts/run_query_formulation_old_chunk_grid.py` | 字符级 splitter、corpus expansion 与指标计算 |
| 已有轻量 pilot | `evidence/rag_results/query_formulation_sensitivity/technical_detail_query_pilot/` | 固定 240-word/24-word 的 MiniLM pilot；不得覆盖 |

十条 query：

- Baseline：`中子`、`neutron`、`中子测量电流`、`neutron measurement current`。
- 技术细节 query：重复 spike、跨通道同步 zero-value dropout、无明显 lag 的同步变化；每类均含中英文措辞。

## 固定实验矩阵

```text
Chunking（历史字符级 grid）：800 / 80，1200 / 120，1500 / 150
Embedding models：
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  sentence-transformers/all-MiniLM-L6-v2
Queries：4 baseline + 6 technical-detail = 10
Corpus scope：13 篇固定 IAEA core + m 篇 supplementary documents，
  m = 0, 5, 10, ..., 50, 51。
  m > 0 使用 10 次带固定 seed 的随机文档抽样；m = 0 仅运行一次。
```

本任务仅变化 chunking、encoder、query wording/language 与受控 corpus scope；文档内容不得编辑。

## 服务器准备

1. 使用 GPU 环境，并用 `nvidia-smi` 验证。
2. 使用隔离 Python 环境；不要修改系统或项目级 Python。
3. 若缺失依赖，安装：

   ```bash
   python -m pip install sentence-transformers torch numpy pandas llama-index-core
   ```

4. 当前 runner 将 `device="cpu"` 写死。做一处小而可审查的改动：增加 `--device` 参数，在可用时默认 `cuda`，否则为 `cpu`；将最终解析到的 device 写入每个 `metadata.json`。不得在论文正文、图注或结论中报告硬件条件。
5. 启动前运行：

   ```bash
   python -m py_compile paper/scripts/run_query_formulation_old_chunk_grid.py
   ```

## 运行命令

在完成并验证 device 参数后，运行：

```bash
python paper/scripts/run_query_formulation_old_chunk_grid.py \
  --config 800:80 \
  --config 1200:120 \
  --config 1500:150 \
  --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  --model sentence-transformers/all-MiniLM-L6-v2 \
  --device cuda \
  --batch-size 64
```

若 GPU 显存不足，只降低 batch size；不得静默更改语料、query set、chunk 参数、trial 数或 seed。

## 输出位置与完成验证

只能在以下路径写入输出：

```text
evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm/
  c800_o80/<model-slug>/
  c1200_o120/<model-slug>/
  c1500_o150/<model-slug>/
```

每个 model/configuration 目录必须包含 `scope_detail.csv`、`scope_summary.csv`、`metadata.json`。

报告完成前验证：

- 六个完整的 model/configuration 输出目录存在；
- 每个 summary 恰有 **120 行**：10 queries × 12 个 corpus-scope 值；
- 每个 detail 恰有 **1,110 行**：10 queries ×（一次 core-only run + 11 个 scope 值 × 10 trials）；
- metadata 记录 model、`chunk_size`、`chunk_overlap`、seed、trial count、corpus counts、resolved device 与 elapsed time；
- 没有历史结果目录被覆盖。

## 成功运行后的可视化输出

结果审核前，不修改论文。只在同一实验目录下增加：

1. **横向 trajectory 图**：IAEA priority@10 对 supplementary corpus size。保持 query family 可区分；必要时分 language/model panel。
2. **纵向 heatmap**：在 `m=10` 时，行是 10 个 query ID，列是 6 个 `chunking × encoder` 条件，颜色为 mean IAEA priority@10。
3. `m=10` 与 `m=51` 的 machine-readable summary table，保留 mean 与 standard deviation。

## 结果表述边界

可用：

- “Query formulation sensitivity 在所测试的代表性字符级 chunk 设置下仍然出现。”
- “该效应随 query type、language 与 encoder 而变化。”

不可用：

- “技术细节 query 普遍更优。”
- “工作流自动生成更好的 query。”
- “IAEA priority 衡量通用 relevance 或诊断准确率。”

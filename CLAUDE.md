# Claude：本仓库用于写论文，不用于重跑实验

## 论文是什么
核电中子电流测量 → zero-prior Agent 出工况报告 → RAG 检索 IAEA/同域手册 → 带引用的诊断备忘。投稿向 Elsevier 核工刊（`paper/`）。

## 材料地图
| 论文章节 | 看哪里 |
|----------|--------|
| §1–2 Intro / related | `paper/sections/01_*.tex` + `*_zh.md` |
| §3 System / data | `paper/sections/03_*.tex` + `evidence/data_samples/` + `code_ref/agents|tools` |
| §4 Evaluation | `paper/sections/04_evaluation.tex` + `evidence/rag_results/mdself*.py` |
| §5 Results / case | `paper/sections/05_results.tex` + `evidence/case_A1_1/` + `evidence/rag_results/output_*` |
| 语料与引用核对 | `corpus/md/` + `corpus/pdf/` + `corpus/manifest.jsonl` + `paper/refs.bib` |
| 索引/分块变体 | `corpus/storage_md_c*_o*`（17 套 MD 网格）+ `corpus/storage_pdf*` |

## 硬约束
- 完整多日 CSV、向量索引、Ollama 模型在**服务器原路径**，本包只有样本与已算好的结果表。
- 补数字：从 `evidence/rag_results/**/*summary*.csv`、`*table*.csv` 读，不要声称重新跑了 17 组索引。
- 改 case 叙述：以 `evidence/case_A1_1/*诊断书*` / `*工况报告*` 为准。

## 数据摘要（正文已写）
- 42 个系列：A1/A2/B1/B2；每系列 1 时间列 + 7 通道；样本见 `A1_1_head5000.csv`。
- 语料 59 篇 MD：core 13 IAEA + non-core 46；本包 `corpus/md` 已含全文 MD。

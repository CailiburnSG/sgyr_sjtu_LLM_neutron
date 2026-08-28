# paper_claude_pack — 写论文用预览包（约 11GB）

**用途**：给 Claude Code 写/改 `paper/` 直接用的材料。  
**不做**：假定必须在 Claude 侧重训模型；向量库已带齐，若环境能加载可做只读核对。

本目录是**拷贝出来的预览**，**没有**改动你原来的项目路径。

---

## 目录一览

| 路径 | 大小（约） | 写论文用来干什么 |
|------|------------|------------------|
| `paper/` | 0.8MB | LaTeX 工程、中文草稿、图、bib |
| `evidence/case_A1_1/` `case_A2_1/` | ~0.4MB | §5 case：工况报告、诊断书、JSON |
| `evidence/data_samples/` | 0.8MB | A1_1 样本 CSV + 全量清单 |
| `evidence/rag_results/` | 129MB | §4–§5 检索实验 CSV/图/脚本 |
| `corpus/pdf/` | 231MB | 手册 **PDF 原文**（62 个文件） |
| `corpus/md/` | 143MB | 手册 **Markdown**（64 个 `.md` + meta） |
| `corpus/storage_*` | ~11GB | 同一批手册的 **全部索引/分块变体**（21 套） |
| `corpus/manifest.jsonl` | 小 | 文档清单（doc_id / 路径 / 类别） |
| `code_ref/` | 0.2MB | Agent/tools/rag 源码摘录 |

**合计 ≈ 11GB**（仍远小于 Claude 侧约 70G）。

论文正文写「59 篇」；磁盘上实际为 **62 PDF / 64 MD**（含 meta 与个别多文件条目）。写稿时以 `manifest.jsonl` + 正文表述为准，不必强行改数。

---

## 手册「所有变体」对照

同一语料在本包中的形态：

1. **PDF**：`corpus/pdf/<类别>/...pdf` — 原始手册  
2. **MD + meta**：`corpus/md/<类别>/...md` 与 `*_meta.json` — 供检索与引用的文本版  
3. **Markdown 索引网格**（论文 Experiment：chunk × overlap）：  
   - `storage_md_c800_o{50,80,100,120,150}`  
   - `storage_md_c1000_o{80,100,120,150}`  
   - `storage_md_c1200_o{80,100,120,150}`  
   - `storage_md_c1500_o{80,100,120,150}`  
   - 另有空壳/占位 `storage_md`  
4. **PDF 路径索引变体**：  
   - `storage_pdf`  
   - `storage_pdf_c800_o80`  
   - `storage_pdf_c1200_o120`  

以上与服务器 `RAGTEST/rag_index/` 对齐拷贝。

---

## 仍未纳入（与「手册变体」无关）

| 原路径 | 原因 |
|--------|------|
| 完整中子电流 CSV / workspace 内 sorted CSV | 写稿用报告+样本即可 |
| `yjs_data_2026_2/data` | 测量存档，非手册 |
| Ollama / `archive/models` | 模型权重 |

---

## 建议 Claude 的用法

1. 改正文与数字：`paper/` + `evidence/rag_results/` + `evidence/case_*`  
2. 核对手册表述 / 引用：优先 `corpus/md/`，需要版式或图时查 `corpus/pdf/`  
3. 讨论 chunk 配置差异：对照 `corpus/storage_md_c*_o*` 与 `evidence/rag_results/output_*`  
4. 文档列表：`corpus/manifest.jsonl`

---

## GitHub 说明（重要）

远程仓库：https://github.com/CailiburnSG/sgyr_sjtu_LLM_neutron

- **会推送**：`paper/`、`evidence/`、`code_ref/`、`corpus/pdf/`、`corpus/md/`、`corpus/manifest.jsonl`、文档（约 520MB）
- **不推送（`.gitignore`）**：`corpus/storage_*`（约 11GB，且含大量 >100MB 文件，GitHub 会拒收）
- 索引变体仍在本机：`paper_claude_pack/corpus/storage_*` 与原路径 `RAGTEST/rag_index/storage_*`

## 状态

- 本地目录：`/home/sda/sgyr/paper_claude_pack`  
- 远程：`CailiburnSG/sgyr_sjtu_LLM_neutron`（空仓待推）  

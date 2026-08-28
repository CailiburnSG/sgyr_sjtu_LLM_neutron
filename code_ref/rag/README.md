# 操作手册 RAG 对比建库

PDF 库与 MD 库共用同一份 `manifest.jsonl`（`doc_id` 对齐），便于对比实验。

## 目录

| 路径 | 说明 |
|------|------|
| `操作手册/` | 原始 PDF（不动） |
| `rag_index/md/` | 由 PDF 导出的 Markdown |
| `rag_index/manifest.jsonl` | 文档清单与 metadata |
| `rag_index/storage_pdf/` | PDF 流水线向量库 |
| `rag_index/storage_md/` | MD 流水线向量库 |

## 环境

```bash
# 需已启动 Ollama，且已 pull embedding 模型
ollama pull nomic-embed-text

pip install -r /home/sda/sgyr/rag_compare/requirements.txt
```

## 终端里大量 `FloatObject` / `pypdf` WARNING？

那是 **旧版用 pypdf 读 PDF** 时的提示，**不等于向量化失败**。新版脚本已改为 **PyMuPDF** 读 PDF。

向量化阶段刷 `api/embed` 是正常的；2 份大 PDF 可能有 **两千+ chunk**，`both` 还要做两遍，**半小时～1 小时** 都常见。

### 加速（对比试跑）

```bash
# 只建 MD 库（内容与 PDF 同源，对比阶段常够用）
python build_index.py --pipeline md --limit 2 --force --fast

# 或手动调参：更大块 + 更大 batch
python build_index.py --pipeline md --limit 2 --force --chunk-size 1500 --embed-batch-size 16
```

若 `--embed-batch-size 16` 报 Ollama 400，改回 `--embed-batch-size 1`。

## 推荐流程

```bash
cd /home/sda/sgyr/rag_compare

# 若 MD 已导出，可先只建 MD 库（更快验证 Ollama）
python build_index.py --pipeline md --limit 2 --force

# 1) 试跑 2 份（确认路径、Ollama、依赖正常）
python build_index.py --pipeline both --limit 2 --force

# 2) 全量建库（62 份，耗时取决于机器与 Ollama）
python build_index.py --pipeline both

# 3) 检索对比
python query_compare.py "online monitoring of instrument channels"
```

## 常用参数

- `--export-md`：只导出 MD，不建索引
- `--pipeline pdf|md|both`：建指定库
- `--force`：删除旧 `storage_*` 后重建
- `--limit N`：只处理前 N 个 PDF

## 环境变量

- `OLLAMA_BASE_URL`（默认 `http://127.0.0.1:11434`）
- `RAG_EMBED_MODEL`（默认 `nomic-embed-text`）

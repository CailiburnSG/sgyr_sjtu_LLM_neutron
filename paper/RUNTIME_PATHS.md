# 本机运行时路径约定（不进论文正文）

## 怎么摆

| 用途 | 路径 | 是否进 Git |
|------|------|------------|
| 语料（64 MD） | `corpus/md/` | 是 |
| MiniLM 权重缓存 | `.cache/huggingface/sentence-transformers/` | 否（`.gitignore`） |
| 隔离 Python | `.venv/`（基于 envLLM 的 torch/CUDA，仅补装 sentence-transformers） | 否 |
| P0 输出 | `evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm/` | 完成后可推送结果 CSV |
| 历史 nomic 索引 | 服务器 `RAGTEST/rag_index/storage_*` 与本包 `corpus/storage_*` | 本任务**不使用** |
| Ollama | `my_apps/ollama_dir` | 本任务**不使用** |

## 为何这样

- HuggingFace 直连在本机 DNS 常失败；权重经 `hf-mirror.com` 预拉后，脚本用 `local_files_only` 读本地 snapshot。
- 不修改 `envLLM` 里已有包；用 `.venv --system-site-packages` 复用其 CUDA torch。
- 结果只写 MD 指定的 `historical_chunk_grid_minilm/`，不覆盖历史 `output_mdself*`。

## 启动

```bash
bash paper/scripts/run_p0_chunk_grid.sh
# 显存不足时：BATCH_SIZE=32 bash paper/scripts/run_p0_chunk_grid.sh
```

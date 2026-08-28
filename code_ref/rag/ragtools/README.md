# pdf2md — 操作手册 PDF 转 Markdown

使用 Marker 将 `操作手册/` 下所有 PDF（含子目录）转为 Markdown，输出到 `rag_index/md/`，**保持原有文件夹层次**。

## 运行

```bash
cd /home/sda/sgyr/pdf2md
/home/sda/sgyr/miniconda3/bin/python pdf2md.py
```

## 常用参数

```bash
# 试跑：只转前 2 个
python pdf2md.py --limit 2

# 显存不足时用 CPU
python pdf2md.py --cpu

# 已转换过的也重做
python pdf2md.py --force
```

## 输出示例

```text
操作手册/EPRI&DOE/报告.pdf
  → rag_index/md/EPRI&DOE/报告/报告.md
```

## 依赖

- `envLLM` 环境中的 `marker_single`（路径见脚本内 `DEFAULT_MARKER`）

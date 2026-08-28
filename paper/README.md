# 论文 LaTeX 工程（核电中子诊断 Agent + RAG 评测）

面向投稿 **Annals of Nuclear Energy / Progress in Nuclear Energy / NET** 等 Elsevier 核工刊的初稿骨架。

## 推荐平台：Overleaf（首选）

本机未装 TeX 时，用 Overleaf 最省事，也方便和导师协作。

1. 打开 [https://www.overleaf.com](https://www.overleaf.com) 注册/登录  
2. **New Project → Upload Project**，把整个 `paper_neutron_rag` 打成 zip 上传  
   ```bash
   cd /home/sda/sgyr
   zip -r paper_neutron_rag.zip paper_neutron_rag \
     -x 'paper_neutron_rag/.git/*'
   ```
3. 菜单 **Menu → Settings**：  
   - Compiler: **pdfLaTeX**  
   - Main document: **main.tex**  
4. 点 Recompile；缺宏包时 Overleaf 一般会自动装  

定刊后改 `main.tex` 里的 `\journal{...}`，并到期刊官网下载其 **Guide for Authors** 核对格式（有的要 `3p`/`5p`、有的要数字引用）。

## 目录结构

```
paper_neutron_rag/
  main.tex                 # 主文件（标题/摘要/结构）
  refs.bib                 # 参考文献
  sections/
    01_introduction.tex    # 绪论（含文献综述；核工应用文写法）
    01_introduction_zh.md  # 绪论中文副本
    02_related.tex         # 已并入绪论，仅存档
    03_system.tex
    04_evaluation.tex
    05_results.tex
    06_conclusions.tex
  figs/                    # 放 png/pdf 图，在正文 \includegraphics
  tables/                  # 可选：复杂表格拆文件
  README.md
```

正文现为五章：Introduction → System design → Evaluation protocol → Results and discussion → Conclusions。
## 本地编译（可选）

若已安装 TeX Live：

```bash
cd /home/sda/sgyr/paper_neutron_rag
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

中文全文若改投国内刊，可另建 `ctexart`/`ctexbook` 工程；当前骨架为**英文 Elsevier** 投稿向。

## 接下来你要做的

1. 改作者、单位、基金号  
2. 把 RAGTEST 曲线图拷进 `figs/`，取消 `01_introduction.tex` 里 figure 注释  
3. 按真实实验补全 §5 数字（引用 CSV/图）  
4. 用 Zotero/Overleaf 补全 `refs.bib`  
5. 与导师确认目标期刊后再微调 `\documentclass` 选项  

## 其他可选平台

| 平台 | 适用 |
|------|------|
| **Overleaf** | 首选：协作、模板、自动编译 |
| TeXstudio + TeX Live | 本地离线、大项目 |
| VS Code + LaTeX Workshop | 已在用 Cursor/VS Code 时 |
| 期刊官方模板 | 录用后按 camera-ready 替换 `elsarticle` 选项 |

# 当前论文稿

本目录是当前论文的独立 LaTeX 工程，可单独复制、压缩或同步到 Overleaf。

- 主文件：`main.tex`
- 编译器：pdfLaTeX
- 参考文献：`refs.bib`
- 正文章节：`sections/`
- 图片：`figs/`（按正文顺序编号为 `fig01`–`fig20`）
- 表格：`tables/`

本地完整编译：

```bash
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

上传 Overleaf 时只需上传本目录，并将主文档设为 `main.tex`。

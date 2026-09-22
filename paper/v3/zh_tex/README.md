# V3 中文 TeX 排版稿

该目录是 V3 中文的原生 LaTeX 排版稿。`main.tex` 通过 `sections/` 中的六个 `.tex` 文件组织正文，`refs.bib` 是从 V2 固定的书目库副本。中文 Markdown 仍是论证内容的来源稿；修改稳定后需同步迁入对应 TeX 小节。

使用 XeLaTeX 编译：`xelatex main.tex`（需要时重复运行一次以更新目录和交叉引用）。

已在本地完整 TeX Live 环境中以 XeLaTeX 编译验证。首次编译请依次运行 `xelatex main.tex`、`bibtex main`，再运行两次 `xelatex main.tex`；若另行安装 `latexmk`，也可使用 `latexmk -xelatex main.tex`。正式投稿前应改用目标期刊模板和指定字体。

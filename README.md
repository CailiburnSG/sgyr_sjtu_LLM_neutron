# 核电厂中子电流诊断辅助：项目说明

本仓库保存面向**无标签中子电流历史时序**的诊断辅助研究材料：确定性脚本首先从原始测量中生成可回溯的观测与结构化摘要，再以受来源策略约束的技术资料检索支持带引文的候选解释。它不是自动故障确认系统；工程判断保留给领域工程师。

当前写作主线是 `paper/v3/`：中文 Markdown 用于论证与修改，`paper/v3/zh_tex/` 用于本地排版预览。`paper/v2/` 是可独立编译的英文稳定稿，只作实验、图片和历史文字的回溯素材，不应与 V3 正文混用。

## 快速导航

| 位置 | 用途 | 是否是当前写作入口 |
| --- | --- | --- |
| `paper/v3/zh/` | V3 中文 Markdown 源稿与六章正文 | 是 |
| `paper/v3/zh_tex/` | V3 中文 LaTeX 排版稿，可生成本地 PDF | 是（排版预览） |
| `paper/v3/en/` | V3 英文镜像稿；仅翻译已确认的中文内容 | 否 |
| `paper/v2/` | V2 英文 LaTeX 稳定稿、图表与实验素材 | 否（历史参照） |
| `paper/PAPER_DISCUSSION_GUIDE_zh.md` | 跨版本写作决策与修改蓝图 | 参考 |
| `导师意见/` | 导师意见与推荐论文清单 | 参考 |
| `paper/scripts/` | V2 图表、实验结果的生成脚本 | 复现实验时使用 |
| `corpus/`、`evidence/` | 技术资料语料、检索实验配置与结果 | 复现实验时使用 |
| `code_ref/` | 早期代码参考，不是当前论文编译入口 | 参考 |

更细的论文目录说明见 [paper/README.md](paper/README.md)；V3 的写作与中英同步规则见 [paper/v3/README.md](paper/v3/README.md)。

## 本地环境

### 最小需求：阅读与编辑

- Git
- 任意 Markdown/LaTeX 编辑器（例如 VS Code）
- 仅阅读已有 PDF 时不需要安装 TeX。

### 论文编译

在 Debian/Ubuntu 环境中，下面的 TeX Live 组件可同时覆盖 V2 的 pdfLaTeX 与 V3 中文稿的 XeLaTeX：

```bash
sudo apt-get update
sudo apt-get install -y \
  texlive-latex-extra texlive-bibtex-extra \
  texlive-xetex texlive-lang-chinese
```

安装后应能找到以下命令：

```bash
pdflatex --version   # V2
xelatex --version    # V3 中文稿
bibtex --version     # 两者的参考文献
```

本仓库当前已在 Linux + TeX Live 环境中验证 V3 中文稿可编译。正式投稿时仍应切换到目标期刊的模板、字体与版式要求。

### 实验复现（按需）

只有在需要运行检索或向量化实验时，才需要 Python 环境及相应模型权重。项目已有运行路径约定与注意事项：

```bash
sed -n '1,220p' paper/RUNTIME_PATHS.md
```

不要将模型缓存、向量索引或运行日志提交到 Git；这些大型或可再生文件已在 `.gitignore` 中排除。

## 编译论文

### V3 中文排版预览（当前推荐）

```bash
cd paper/v3/zh_tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

输出文件为 `paper/v3/zh_tex/main.pdf`。中文论证内容应先在 `paper/v3/zh/sections/` 修改，确认后再同步到对应的 `.tex` 小节；不要把 TeX 排版稿作为唯一内容来源。

### V2 英文稳定稿

```bash
cd paper/v2
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

输出文件为 `paper/v2/main.pdf`。若上传到 Overleaf，应上传整个 `paper/v2/` 目录，并将 `main.tex` 设为主文档。

## 推荐协作流程

1. 在 `paper/v3/zh/sections/` 完成中文事实、论证和图表任务的修改。
2. 将稳定内容同步至 `paper/v3/zh_tex/sections/`，本地编译 PDF 检查排版。
3. 中文内容经确认后，才同步翻译到 `paper/v3/en/`。
4. 使用 `git status` 检查改动，再以小而语义明确的提交记录保存；只在确认后推送远端。

Markdown、TeX、图片和实验结果必须服务于同一版本，避免将 V2 的正文、编号或图片路径直接混入 V3。

## 数据与保密边界

- 不提交原始运行数据、设备标识、维护记录、账号密钥或其他未披露信息。
- 不将候选解释写成已确认故障；脚本输出、检索证据与工程判断必须保持可区分。
- 新增技术资料时记录来源、版本与使用边界，并遵守其版权与访问要求。

## Git 远端

仓库远端：<https://github.com/CailiburnSG/sgyr_sjtu_LLM_neutron>

```bash
git status
git add <明确的文件或目录>
git commit -m "简明说明本次变更"
git push origin main
```

推送前请先确认没有误加入本地缓存、构建中间文件或敏感资料。

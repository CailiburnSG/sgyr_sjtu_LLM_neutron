# V3 图表资产

本目录只存放 V3 正文或补充材料实际采用的图表，以及它们的可复现生成产物。

- 不直接在此复制 V2 的全部图片；每一张迁入前需确认其服务于 V3 的论证主张。
- 图表生成脚本可参考 `paper/v2/scripts/` 中的 V2 素材，但 V3 的改造脚本应单独记录其输入、参数与输出，并存放在 `../scripts/`。
- 图文件按全文连续编号命名：Fig.4 的两个子图为 `fig04a_scope_priority.pdf` 和 `fig04b_top1_cosine.pdf`；Fig.5(a)/(b) 为英文/中文 query 家族均值差图：固定 encoder--分块配置内，每条 query 先在 10 次随机抽样上取均值，再以 3 条技术细节 query 的家族均值减去 2 条基线 query 的家族均值。该图由 `build_query_effect_panels.py` 生成；Fig.6 为 `fig06_configuration_heatmap.pdf`。Fig.4 由 `build_scope_panels.py` 生成；Fig.6 的配置热图由 `build_configuration_heatmap.py` 生成。
- self-retrieval 曲线、完整扩库轨迹和来源保持散点图暂保留在 V3 正文的第 5.4 节之后，作为后置交叉核查图组；后续再根据篇幅决定是否移入补充材料。

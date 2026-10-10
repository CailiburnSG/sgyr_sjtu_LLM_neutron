# B1 自包含输入包

本目录由 `../prepare_b1_materials.py` 生成。它是 B1 的冻结输入副本，运行 B1 时**不再读取** B0 或金标准目录；B0 原始结果保留在其原目录不变。

- `split_manifest.json`：固定 60/20 分割。训练、验证分别在四项行动上为 15/5 例，并在 1、2、3、4 个事件组成的案例上分别为 15/5 例。
- `action_definitions.json`：A1--A4 的完整行动定义和边界。
- `output_contract.json`：模型必须遵守的 JSON 输出约束。
- `prompt_template.md`：每次 LLM 调用使用的固定任务说明和边界。
- `candidate_packages/top_k_XX/`：从 B0 复制的原始检索结果，以及扩展后的 LLM 输入。每张候选卡均含正文、来源定位、主题标签和 applicability。
- `labels/`：训练目标与保留的验证标签。标签文件不应提供给验证推理调用。

每份 `*_inputs.jsonl` 均只含模型可见内容：事件组合、BM25 查询和候选卡全文；不含正确行动或正确证据。`labels/` 才含金标准的三证据与唯一行动。

小 K 下金标准三张证据不一定都落入候选包。这正是 B1 需测量的候选缺失条件；不要把标签删改成迁就 top-K。

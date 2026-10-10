# 证据语义单元

这里的语义单元不是新证据，也不修改 300 张人工证据卡。它是一个可审计的等价层：

```text
evidence_id → semantic_unit_id
goldcase → (semantic_unit_id, action_id)
```

`v1` 从已存在的 10 个功能族归类草稿出发，保留多标签关系，并将其命名、定义为可评分的语义单元。
它的用途是评价“模型是否选到同等含义的证据”，而不是只评价是否逐字选中同一 `evidence_id`。

- `semantic_unit_registry_v1.csv`：10 个语义单元的定义与适用行动边界；
- `card_semantic_units_v1.csv`：300 张证据卡到语义单元的多对多映射；
- `gold_semantic_action_targets_v1.csv`：80 个金标准案例的语义单元—行动目标对；
- `semantic_unit_coverage_report_v1.json`：覆盖审计；
- `build_semantic_units_v1.py`：可重复生成脚本。

`v1` 是受控的第一版评分粒度，状态为 `provisional`：它已经能支持语义 F1 的实现，但在把指标写入论文主结论前，应结合具体误判例审阅是否需要细分过宽的单元。它不替代具体卡号严格 F1；后者继续作为辅助指标。

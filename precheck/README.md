# 中子电流预检管线（重写版）

该目录与 `code_ref/` 和旧检索实验隔离。它以事件卡为唯一接口，逐步接入：

```text
快照或 CSV → 原子观测 → 事件卡 → 证据检索 → 受约束 LLM 报告 → 评价
```

当前实现的第一条可运行链路是：从现有 JSON 快照中读取孤立零值、合并多通道同步观察、校验卡片，并生成不含诊断结论的模板预检报告。

正式入口直接读取 CSV，提取 v1 的孤立零值与尖峰原子观测，再进入同一聚合器；快照入口只用于历史案例和回归检查。

## 试点运行

在仓库根目录执行：

```bash
python3 -m precheck.cli build-cards \
  --snapshot evidence/case_A1_1/A1_1_sorted_进阶全局工况报告_数据快照.json \
  --record-id A1_1 \
  --output precheck/output/A1_1_zero_cards.json

# 直接从 CSV 生成事件卡（正式数据路径）
python3 -m precheck.cli build-cards-from-csv \
  --csv evidence/data_samples/A1_1_head5000.csv \
  --record-id A1_1_head5000 \
  --output precheck/output/A1_1_csv_cards.json

python3 -m precheck.cli validate-cards \
  --cards precheck/output/A1_1_zero_cards.json

python3 -m precheck.cli render-template \
  --cards precheck/output/A1_1_zero_cards.json \
  --output precheck/output/A1_1_template_reports.md
```

## 设计边界

- 事件卡只记录可观察现象，不声明故障机理、因果链或设备状态。
- 当前 JSON 快照有精确的孤立零值时间；尖峰只有汇总，后续应从详细报告或完整 CSV 输出结构化尖峰原子观测。
- 当前工作区没有完整 CSV、服务器向量索引和本地模型；后续实现必须通过配置路径接入它们，不能假装已在本地重跑。
- 后续模块将实现资料段落元数据、候选证据检索、LLM 提供方接口、报告忠实性和证据支撑评价。

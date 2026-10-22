# 中子电流事件卡管线

`eventcard/` 将长时序数据转换为可追溯的事件卡，供后续受控检索与预检报告使用。它不输出故障诊断、因果链或设备状态判断。

```text
原始 CSV
  → 单通道原子事件表
  → 单通道事件卡表
  → 跨通道聚合事件卡表
```

## 三层产物

1. **原子事件表**：一行代表一个通道的一段可观测模式。v1 事件名为 `short_zero`、`sustained_zero`、`positive_spike`、`negative_drop`、`upward_trend`、`downward_trend`、`transient_deviation`；含 `atomic_event_id`、通道、起止时间和检测规则。当前 CSV 检测器只实际输出前四类。
2. **单通道事件卡表**：将同一通道、同一类型且时间相邻的原子事件合并。含 `source_atomic_event_ids`，能回溯到原子表。
3. **聚合事件卡表**：将不同通道、同一类型、时间相邻的单通道卡聚合。含 `source_channel_card_ids`，只表示时间共现，不表示共同原因。

两个窗口分开设置：

- `--channel-merge-window-seconds`：同一通道的原子事件如何连成局部事件；
- `--aggregate-window-seconds`：多个通道的局部事件如何构成整体事件。

因此，后续如果只想修改“几秒内算同步”，只需重跑聚合层；原始 CSV 检测结果仍然保留。

聚合规则、孤立事件保留策略、可用于论文的表述和量化评价方案见[事件卡设计与评价说明](事件卡设计与评价说明.md)。事件卡如何连接技术资料、形成受控检索请求并约束 LLM 报告，见[证据库与事件驱动检索设计](证据库与事件驱动检索设计.md)。

事件模式、运行工况、聚合范围与证据适用性的统一英文命名见[受控术语表](受控术语表.md)。其中 `normal_operation_confirmed` 只能由外部运行记录确认；仅凭 CSV 平稳性得到的窗口使用 `steady_signal_baseline`。

## 试点运行

在仓库根目录执行：

```bash
python3 -m eventcard.cli build-cards-from-csv \
  --csv evidence/data_samples/A1_1_head5000.csv \
  --record-id A1_1_head5000 \
  --atomic-output eventcard/output/A1_1_atomic_events.json \
  --channel-cards-output eventcard/output/A1_1_channel_cards.json \
  --output eventcard/output/A1_1_aggregated_cards.json
```

历史快照入口仅为旧结果回归检查，不属于正式数据处理路径：

```bash
python3 -m eventcard.cli build-cards \
  --snapshot evidence/case_A1_1/A1_1_sorted_进阶全局工况报告_数据快照.json \
  --record-id A1_1 \
  --atomic-output eventcard/output/A1_1_snapshot_atomic_events.json \
  --channel-cards-output eventcard/output/A1_1_snapshot_channel_cards.json \
  --output eventcard/output/A1_1_snapshot_aggregated_cards.json
```

校验最终聚合卡及渲染模板报告：

```bash
python3 -m eventcard.cli validate-cards \
  --cards eventcard/output/A1_1_aggregated_cards.json

python3 -m eventcard.cli render-template \
  --cards eventcard/output/A1_1_aggregated_cards.json \
  --output eventcard/output/A1_1_template_reports.md
```

## 当前边界

- 当前 CSV 检测器区分短零值段与持续零值段，并以滚动中位数/MAD 检出正向尖峰和负向突降；阈值尚须以正式数据、标注集或专家规则冻结。
- 现阶段 `multi_channel_temporal_cluster` 仅表示同类型事件的时间邻近聚合，并不表示严格同步或共同原因；之后可明确加入“部分通道 / 广泛通道”的覆盖率分层。
- 完整原始数据与服务器模型不在本地工作区；接入时必须经配置路径运行并保存参数、数据版本和代码版本。

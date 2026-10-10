# 80 例配额冻结

本批的构造顺序是：先锁定四项建议各 20 例，并在每项建议内部锁定事件组规模，再从指定事件池构造。
不得根据已有证据检索结果回头改变类别数量或组规模。

| action_id | 显示建议 | 允许事件池 | 1 事件 | 2 事件 | 3 事件 | 4 事件 | 合计 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `on_site_operation_or_calibration_check` | 查同一时段现场是否有操作或校准 | `positive_spike` 单通道组 + 多通道组 | 5 | 5 | 5 | 5 | 20 |
| `cross_channel_similar_anomaly_comparison` | 横向对比其他传感器通道是否出现类似问题 | `negative_drop` 单通道组 + 多通道组 | 5 | 5 | 5 | 5 | 20 |
| `record_processing_and_timestamp_check` | 查数据记录和时间戳在处理层面是否有问题 | `short_zero` 多通道组 + `sustained_zero` 多通道组 | 5 | 5 | 5 | 5 | 20 |
| `signal_transmission_path_check` | 查信号/数据传输路径是否异常 | `short_zero` 单通道组 + `sustained_zero` 单通道组 | 5 | 5 | 5 | 5 | 20 |

因此全体 80 例中，分别有 20 个单事件、双事件、三事件、四事件案例。单事件案例在两事件池间轮换；
多事件案例至少覆盖两个池，以保留组合模式。事件原子在其所属建议的 20 个案例中均衡复用（每个 2--3 次），
但任何一个案例内不重复使用同一事件原子。

# B2-FS-RA：两个阶段均使用完整 golden 示例

每个完整示例包含“事件组合 + 3 张人工证据核心卡 + 固定行动 + boundary note”。同一冻结示例池同时进入全库选证调用与行动调用；但评估案例仍必须在当前运行中独立从 300 张卡选择 Top-K，不能复用任何既有选择结果。

先物化示例池：

```bash
python3 ../materialize_b2_full_golden_examples.py --top-k 5 --n 8 --pool-id 01
```

无 API 校验：

```bash
python3 run_both_qwen.py --top-k 5 --n 8 --pool-id 01 --examples-file ../training_example_pools/top_k_05/n_08/pool_01.jsonl --validate-only
```

正式运行时另加 `--run-id pool_01`。

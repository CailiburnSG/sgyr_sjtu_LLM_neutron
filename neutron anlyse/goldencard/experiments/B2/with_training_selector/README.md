# B2-FS-R：仅选证阶段使用完整 golden 示例

完整示例为“事件组合 + 3 张人工证据核心卡 + 固定行动 + boundary note”。示例仅进入全库选证调用；行动调用保持 zero-shot。每个验证案例仍在本次运行中从 300 张卡独立选择 Top-K，不能复用其他条件的选择结果。

先物化示例池：

```bash
python3 ../materialize_b2_full_golden_examples.py --top-k 5 --n 8 --pool-id 01
```

无 API 校验：

```bash
python3 run_selector_qwen.py --top-k 5 --n 8 --pool-id 01 --examples-file ../training_example_pools/top_k_05/n_08/pool_01.jsonl --validate-only
```

正式运行时另加 `--run-id pool_01`。

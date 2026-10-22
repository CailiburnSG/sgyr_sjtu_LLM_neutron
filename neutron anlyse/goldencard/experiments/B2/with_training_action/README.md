# B2-FS-A：仅行动阶段使用完整 golden 示例

完整示例为“事件组合 + 3 张人工证据核心卡 + 固定行动 + boundary note”。全库选证调用保持 zero-shot；示例仅进入读取本次新选 Top-K 证据后的行动调用。每个验证案例仍在本次运行中独立选择证据。

先物化示例池：

```bash
python3 ../materialize_b2_full_golden_examples.py --top-k 5 --n 8 --pool-id 01
```

无 API 校验：

```bash
python3 run_action_qwen.py --top-k 5 --n 8 --pool-id 01 --examples-file ../training_example_pools/top_k_05/n_08/pool_01.jsonl --validate-only
```

正式运行时另加 `--run-id pool_01`。

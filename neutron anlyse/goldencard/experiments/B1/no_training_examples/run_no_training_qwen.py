#!/usr/bin/env python3
"""Run the frozen B1 package through an OpenAI-compatible Qwen endpoint.

The key is read from DASHSCOPE_API_KEY or, for this local experiment only, the
first line of experiments/apikey.txt.  It is never written to results.
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import sys


HERE = Path(__file__).resolve().parent
B1_ROOT = HERE.parent
DATA = B1_ROOT / "data"
EXPERIMENTS = B1_ROOT.parent
sys.path.insert(0, str(EXPERIMENTS))

from result_csv import write_b1_csv, write_b1_semantic_csv, write_b1_stage_summary  # noqa: E402
from semantic_metrics import evaluate_b0_semantics, load_units  # noqa: E402
DEFAULT_KEY_FILE = EXPERIMENTS / "apikey.txt"
DEFAULT_BASE_URL = "https://maas.qianwenaiapi.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-flash"
ACTIONS = tuple(json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))["allowed_action_ids"])


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_key(key_file: Path | None) -> str:
    if os.getenv("DASHSCOPE_API_KEY"):
        return os.environ["DASHSCOPE_API_KEY"].strip()
    if key_file and key_file.exists():
        # The local file may have a human note on later lines; only its first
        # non-empty line is a credential.
        for line in key_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                return line.strip()
    raise RuntimeError("No DASHSCOPE_API_KEY and no usable local key file.")


def prompt_for(case: dict, actions: list[dict], contract: dict, template: str) -> list[dict]:
    return [
        {"role": "system", "content": template},
        {"role": "user", "content": json.dumps({
            "action_definitions": actions,
            "output_contract": contract,
            "case": case,
        }, ensure_ascii=False)},
    ]


def call_qwen(messages: list[dict], key: str, base_url: str, model: str) -> tuple[dict, dict]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "stream": False,
        "enable_thinking": False,
        "max_tokens": 900,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.loads(response.read().decode("utf-8"))
    elapsed = round(time.monotonic() - started, 3)
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    return raw, {"content": content, "elapsed_seconds": elapsed, "usage": raw.get("usage", {}), "model": raw.get("model", model)}


def parse_json(content: str) -> tuple[dict | None, str | None]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return (value, None) if isinstance(value, dict) else (None, "JSON top level is not an object")
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"


def validate_prediction(prediction: dict | None, contract: dict) -> list[str]:
    if prediction is None:
        return ["invalid_json"]
    errors: list[str] = []
    action = prediction.get("action_id")
    if action not in contract["allowed_action_ids"]:
        errors.append("invalid_action_id")
    if not isinstance(prediction.get("boundary_note"), str) or not prediction["boundary_note"].strip():
        errors.append("missing_boundary_note")
    return sorted(set(errors))


def action_scores(rows: list[dict]) -> tuple[dict, float]:
    details = {}
    for action in ACTIONS:
        tp = sum(row["prediction"].get("action_id") == action and row["gold"]["action_id"] == action for row in rows)
        fp = sum(row["prediction"].get("action_id") == action and row["gold"]["action_id"] != action for row in rows)
        fn = sum(row["prediction"].get("action_id") != action and row["gold"]["action_id"] == action for row in rows)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        details[action] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}
    return details, sum(item["f1"] for item in details.values()) / len(details)


def evaluate(rows: list[dict], metadata: dict) -> dict:
    valid_rows = [row for row in rows if not row["validation_errors"]]
    action_detail, macro_f1 = action_scores(rows)
    return {
        "experiment_id": "B1_bm25_topk_llm_action_v3_all_topk",
        **metadata,
        "case_count": len(rows),
        "json_valid_rate": len([row for row in rows if row["parse_error"] is None]) / len(rows),
        "constraint_valid_rate": len(valid_rows) / len(rows),
        "action_accuracy": sum(row["prediction"].get("action_id") == row["gold"]["action_id"] for row in rows) / len(rows),
        "action_macro_f1": macro_f1,
        "action_per_class": action_detail,
        "error_counts": dict(Counter(error for row in rows for error in row["validation_errors"])),
        "usage": {
            "prompt_tokens": sum(row["api"].get("usage", {}).get("prompt_tokens", 0) or 0 for row in rows),
            "completion_tokens": sum(row["api"].get("usage", {}).get("completion_tokens", 0) or 0 for row in rows),
            "total_tokens": sum(row["api"].get("usage", {}).get("total_tokens", 0) or 0 for row in rows),
        },
    }


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--limit", type=int, default=0, help="0 means all frozen validation cases")
    args = parser.parse_args()
    candidate_dir = DATA / "candidate_packages" / f"top_k_{args.top_k:02d}"
    input_path = candidate_dir / "validation_inputs.jsonl"
    if not input_path.exists():
        raise FileNotFoundError(f"No frozen B0 candidate package for top_k={args.top_k}: {input_path}")
    inputs = read_jsonl(input_path)
    invalid_counts = [case["goldcard_id"] for case in inputs if len(case.get("bm25_candidates", [])) != args.top_k]
    if invalid_counts:
        raise ValueError(f"Candidate-count mismatch for top_k={args.top_k}: {', '.join(invalid_counts[:5])}")
    labels = {row["goldcard_id"]: row["target"] for row in read_jsonl(DATA / "labels" / "validation_gold_labels.jsonl")}
    actions = json.loads((DATA / "action_definitions.json").read_text(encoding="utf-8"))
    contract = json.loads((DATA / "output_contract.json").read_text(encoding="utf-8"))
    template = (DATA / "prompt_template.md").read_text(encoding="utf-8")
    key = load_key(args.key_file)
    inputs = inputs[:args.limit] if args.limit else inputs
    rows = []
    for index, case in enumerate(inputs, 1):
        print(f"[{index}/{len(inputs)}] {case['goldcard_id']}", flush=True)
        try:
            raw, api = call_qwen(prompt_for(case, actions, contract, template), key, args.base_url, args.model)
            prediction, parse_error = parse_json(api["content"])
            errors = validate_prediction(prediction, contract)
        except Exception as exc:
            raw, api = None, {"content": None, "elapsed_seconds": None, "usage": {}, "model": args.model}
            prediction, parse_error, errors = {}, f"request_error: {type(exc).__name__}: {str(exc)[:300]}", ["request_error"]
        gold = labels[case["goldcard_id"]]
        rows.append({
            "goldcard_id": case["goldcard_id"], "retrieval_top_k": args.top_k,
            "prediction": prediction or {}, "parse_error": parse_error, "validation_errors": errors,
            "gold": {"action_id": gold["action_id"]},
            "api": api, "raw_response": raw,
        })
    result_dir = HERE / args.model / f"top_k_{args.top_k:02d}"
    write_jsonl(result_dir / "validation_predictions.jsonl", rows)
    metrics = evaluate(rows, {"model": args.model, "base_url": args.base_url, "retrieval_top_k": args.top_k, "split": "frozen_validation_20", "run_at_utc": datetime.now(timezone.utc).isoformat()})
    (result_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_b1_csv(result_dir, rows, metrics)
    input_by_case = {case["goldcard_id"]: case for case in inputs}
    gold_evidence_by_case = {
        case_id: target["action_evidence_ids"] for case_id, target in labels.items()
    }
    semantic_rows = [{
        "goldcard_id": row["goldcard_id"],
        "retrieved_evidence": input_by_case[row["goldcard_id"]]["bm25_candidates"],
        "predicted_action_id": row["prediction"].get("action_id"),
        "gold_action_id": row["gold"]["action_id"],
    } for row in rows]
    semantic_map = EXPERIMENTS.parents[1] / "evidencecard" / "semantics" / "card_semantic_units_v1.csv"
    write_b1_semantic_csv(result_dir, metrics, evaluate_b0_semantics(semantic_rows, gold_evidence_by_case, load_units(semantic_map)))
    write_b1_stage_summary(HERE)
    (result_dir / "README.md").write_text(
        f"# B1 {args.model} Top-{args.top_k} 验证\n\n"
        "由 `../../run_no_training_qwen.py` 在冻结的 20 例验证集上生成。原始模型响应逐例保存在 "
        "`validation_predictions.jsonl`；聚合指标保存在 `validation_metrics.json`。密钥未写入本目录。\n",
        encoding="utf-8",
    )
    print(json.dumps({key: metrics[key] for key in ("case_count", "json_valid_rate", "constraint_valid_rate", "action_accuracy", "action_macro_f1", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

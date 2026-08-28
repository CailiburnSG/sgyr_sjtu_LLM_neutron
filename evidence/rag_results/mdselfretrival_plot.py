#!/usr/bin/env python3
"""
从已有 selfretrieval_detail_*.csv 重算汇总表并画图，无需重跑检索实验。

示例:
  python mdselfretrival_plot.py              # 交互输入 chunk_size / chunk_overlap
  python mdselfretrival_plot.py 1200 120     # 对应 output_mdselfretrival_o120_c1200
  python mdselfretrival_plot.py --detail output_mdselfretrival_o80_c800/selfretrieval_detail_xxx.csv
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from mdselfcompare import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    resolve_chunk_params,
)
from mdselfretrival import ERROR_BAR_STYLE, export_reports_from_detail, load_detail_csv, out_dir_for

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR_RE = re.compile(r"output_mdselfretrival_o(\d+)_c(\d+)")
DETAIL_NAME_RE = re.compile(r"selfretrieval_detail_(\d{8}_\d{6})\.csv$")


def list_out_dirs_with_detail() -> list[tuple[int, int, Path]]:
    """返回 (chunk_size, chunk_overlap, out_dir)，仅含已有 detail 的目录。"""
    found: list[tuple[int, int, Path]] = []
    for p in sorted(SCRIPT_DIR.glob("output_mdselfretrival_o*_c*")):
        if not p.is_dir():
            continue
        m = OUT_DIR_RE.fullmatch(p.name)
        if not m or not list(p.glob("selfretrieval_detail_*.csv")):
            continue
        overlap, chunk_size = int(m.group(1)), int(m.group(2))
        found.append((chunk_size, overlap, p))
    return sorted(found)


def prompt_chunk_params_plot() -> tuple[int, int]:
    print("=" * 60)
    print("  自检索重画图 — 输入分块参数（与 mdselfretrival 实验一致）")
    print("=" * 60)
    ready = list_out_dirs_with_detail()
    if ready:
        print("  已有 detail 的输出目录（chunk_size / chunk_overlap）:")
        for cs, co, p in ready:
            n = len(list(p.glob("selfretrieval_detail_*.csv")))
            print(f"    {cs} / {co}  →  {p.name}（{n} 个 detail）")
    else:
        print("  （暂未发现含 selfretrieval_detail_*.csv 的 output_mdselfretrival_*）")

    while True:
        raw = input(
            f"\n>>> chunk_size（块长度，回车默认 {DEFAULT_CHUNK_SIZE}）: "
        ).strip()
        if not raw:
            chunk_size = DEFAULT_CHUNK_SIZE
            break
        if raw.isdigit():
            chunk_size = int(raw)
            break
        print("    ✗ 请输入正整数。")

    while True:
        raw = input(
            f">>> chunk_overlap（块重叠，回车默认 {DEFAULT_CHUNK_OVERLAP}）: "
        ).strip()
        if not raw:
            chunk_overlap = DEFAULT_CHUNK_OVERLAP
            break
        if raw.isdigit():
            chunk_overlap = int(raw)
            if chunk_overlap >= chunk_size:
                print(f"    ✗ overlap 须小于 chunk_size={chunk_size}，请重试。")
                continue
            break
        print("    ✗ 请输入正整数。")

    out_dir = out_dir_for(chunk_size, chunk_overlap)
    print(f"\n  【预览】输出目录: {out_dir.relative_to(SCRIPT_DIR)}")
    return chunk_size, chunk_overlap


def latest_detail_in_dir(out_dir: Path) -> Path:
    out_dir = out_dir.resolve()
    if not out_dir.is_dir():
        print(f"❌ 未找到目录: {out_dir}", file=sys.stderr)
        print("   请先运行 mdselfretrival.py 生成实验结果。", file=sys.stderr)
        sys.exit(1)
    candidates = sorted(
        out_dir.glob("selfretrieval_detail_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print(f"❌ {out_dir} 下无 selfretrieval_detail_*.csv", file=sys.stderr)
        sys.exit(1)
    if len(candidates) > 1:
        print(f"ℹ️  该目录有 {len(candidates)} 个 detail，已选最新: {candidates[0].name}")
    return candidates[0]


def infer_ts_from_detail(path: Path) -> str | None:
    m = DETAIL_NAME_RE.match(path.name)
    return m.group(1) if m else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 selfretrieval_detail_*.csv 重画图表（不调用 Ollama）",
    )
    parser.add_argument(
        "chunk_args",
        nargs="*",
        type=int,
        metavar="N",
        help="简写: chunk_size chunk_overlap（如 1200 120）",
    )
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    parser.add_argument(
        "--detail",
        type=Path,
        default=None,
        help="直接指定 detail CSV（指定后忽略 chunk 参数）",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录；默认由 chunk 参数或 detail 路径推断",
    )
    parser.add_argument(
        "--ts",
        default=None,
        help="输出文件名时间戳；默认沿用 detail 文件名中的时间戳",
    )
    args = parser.parse_args()

    if args.detail is not None:
        detail_path = args.detail.resolve()
        if not detail_path.is_file():
            print(f"❌ 未找到 detail 文件: {detail_path}", file=sys.stderr)
            sys.exit(1)
        out_dir = args.out_dir.resolve() if args.out_dir else detail_path.parent
    else:
        if args.chunk_args or args.chunk_size is not None or args.chunk_overlap is not None:
            try:
                chunk_size, chunk_overlap = resolve_chunk_params(
                    args.chunk_args, args.chunk_size, args.chunk_overlap
                )
            except SystemExit as exc:
                parser.error(str(exc))
        else:
            chunk_size, chunk_overlap = prompt_chunk_params_plot()

        out_dir = args.out_dir.resolve() if args.out_dir else out_dir_for(chunk_size, chunk_overlap)
        detail_path = latest_detail_in_dir(out_dir)

    ts = args.ts or infer_ts_from_detail(detail_path)

    print("=" * 60)
    print("  自检索 — 仅从 detail 重画图表")
    print("=" * 60)
    print(f"  detail    : {detail_path}")
    print(f"  out_dir   : {out_dir}")
    print(f"  ts        : {ts or '（新生成）'}")
    print(f"  误差棒    : {ERROR_BAR_STYLE}")

    detail_rows = load_detail_csv(detail_path)
    print(f"  行数      : {len(detail_rows)}")

    paths = export_reports_from_detail(detail_rows, out_dir, ts=ts)

    print("\n" + "=" * 60)
    print("  完成")
    for label, path in paths.items():
        print(f"  {label:<12}: {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

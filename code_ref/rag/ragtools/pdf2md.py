#!/usr/bin/env python3
"""
将「操作手册」目录下的 PDF 批量转为 Markdown（调用 Marker）。

输出目录结构与 PDF 相对路径一致，例如：
  操作手册/EPRI&DOE/报告.pdf  ->  rag_index/md/EPRI&DOE/报告/报告.md
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ==========================================
# 路径配置（可按需修改）
# ==========================================
ROOT = Path(__file__).resolve().parent.parent
PDF_ROOT = ROOT / "操作手册"
MD_ROOT = ROOT / "rag_index" / "md"

# Marker 可执行文件（与 manual_pdf2md.py 一致）
DEFAULT_MARKER = "/home/sda/sgyr/miniconda3/envs/envLLM/bin/marker_single"


def find_pdfs(pdf_root: Path) -> list[Path]:
    """递归收集所有 PDF。"""
    return sorted(pdf_root.rglob("*.pdf"))


def expected_md_path(pdf_path: Path, pdf_root: Path, md_root: Path) -> Path:
    """
    Marker 会在 output_dir 下创建「与 PDF 同名」的子目录，其中放同名 .md。
    """
    rel = pdf_path.relative_to(pdf_root)
    stem = pdf_path.stem
    parent = md_root / rel.parent
    return parent / stem / f"{stem}.md"


def run_marker(
    marker_exec: str,
    pdf_path: Path,
    output_dir: Path,
    use_cpu_only: bool,
) -> None:
    """调用 marker_single 转换单个 PDF。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [marker_exec, str(pdf_path), "--output_dir", str(output_dir)]
    env = os.environ.copy()
    if use_cpu_only:
        env["CUDA_VISIBLE_DEVICES"] = ""
    subprocess.run(cmd, check=True, env=env)


def batch_convert(
    pdf_root: Path,
    md_root: Path,
    marker_exec: str,
    *,
    force: bool = False,
    use_cpu_only: bool = False,
    limit: int | None = None,
) -> int:
    """批量转换，返回进程退出码（0=全部成功或无任务）。"""
    print("=" * 60)
    print("  PDF → Markdown 批量转换（操作手册）")
    print("=" * 60)
    print(f"【配置】PDF 源目录 : {pdf_root}")
    print(f"【配置】MD  输出目录: {md_root}")
    print(f"【配置】Marker 程序 : {marker_exec}")
    print(f"【配置】已存在则跳过: {'否（强制重转）' if force else '是'}")
    print(f"【配置】仅使用 CPU  : {'是' if use_cpu_only else '否（优先 GPU）'}")
    print("=" * 60)

    # ---------- 步骤 1：检查环境 ----------
    print("\n▶ 步骤 1/5：检查运行环境…")
    if not Path(marker_exec).is_file():
        print(f"  ❌ 未找到 Marker：{marker_exec}")
        print("  👉 请安装 marker 或修改脚本顶部 DEFAULT_MARKER 路径。")
        return 1
    print("  ✅ Marker 可执行文件存在")

    if not pdf_root.is_dir():
        print(f"  ❌ 未找到 PDF 目录：{pdf_root}")
        return 1
    print(f"  ✅ PDF 目录存在")

    md_root.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ 已确保输出目录存在：{md_root}")

    # ---------- 步骤 2：扫描 PDF ----------
    print("\n▶ 步骤 2/5：扫描 PDF 文件…")
    pdfs = find_pdfs(pdf_root)
    if limit is not None:
        pdfs = pdfs[:limit]
        print(f"  ℹ️  试跑模式：仅处理前 {limit} 个文件")

    if not pdfs:
        print("  ⚠️  未发现任何 .pdf 文件，任务结束。")
        return 0

    print(f"  ✅ 共发现 {len(pdfs)} 个 PDF（含子目录）")

    # ---------- 步骤 3：比对待转换列表 ----------
    print("\n▶ 步骤 3/5：比对已有 Markdown，生成任务列表…")
    todo: list[tuple[Path, Path, Path]] = []  # (pdf, output_dir, expected_md)
    skip = 0
    for pdf in pdfs:
        out_md = expected_md_path(pdf, pdf_root, md_root)
        out_dir = out_md.parent.parent  # marker 的 --output_dir
        if out_md.is_file() and not force:
            skip += 1
            continue
        todo.append((pdf, out_dir, out_md))

    print(f"  📋 待转换: {len(todo)} 个")
    print(f"  ⏭️  将跳过: {skip} 个（已存在且未加 --force）")

    if not todo:
        print("\n🎉 全部 PDF 均已转换，无需处理。")
        return 0

    # ---------- 步骤 4：逐个转换 ----------
    print("\n▶ 步骤 4/5：开始调用 Marker 转换（耗时较长，请耐心等待）…")
    success = 0
    fail = 0
    t0 = time.time()

    for i, (pdf, out_dir, out_md) in enumerate(todo, start=1):
        rel = pdf.relative_to(pdf_root)
        print("\n" + "-" * 60)
        print(f"  [{i}/{len(todo)}] 当前文件: {rel}")
        print(f"  📥 输入: {pdf}")
        print(f"  📤 预期输出: {out_md.relative_to(ROOT)}")
        print("  🚀 正在调用 Marker，请稍候…")

        try:
            run_marker(marker_exec, pdf, out_dir, use_cpu_only)
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Marker 返回错误（退出码 {e.returncode}），已跳过本文件")
            fail += 1
            continue
        except KeyboardInterrupt:
            print("\n\n🛑 用户中断（Ctrl+C），批量任务提前结束。")
            print_summary(success, skip, fail, len(todo) - i, md_root, time.time() - t0)
            return 130

        if out_md.is_file():
            size_kb = out_md.stat().st_size // 1024
            print(f"  ✅ 转换成功（约 {size_kb} KB）")
            success += 1
        else:
            print(f"  ⚠️  Marker 已结束，但未找到预期文件：{out_md}")
            print("  👉 请检查 Marker 输出目录结构是否与脚本预期一致。")
            fail += 1

    # ---------- 步骤 5：统计 ----------
    print("\n▶ 步骤 5/5：汇总结果…")
    print_summary(success, skip, fail, 0, md_root, time.time() - t0)
    return 0 if fail == 0 else 2


def print_summary(
    success: int,
    skip: int,
    fail: int,
    interrupted: int,
    md_root: Path,
    elapsed: float,
) -> None:
    print("\n" + "=" * 60)
    print("  批量转换任务结束")
    print("=" * 60)
    print(f"  ✅ 本次新成功: {success}")
    print(f"  ⏭️  此前已存在跳过: {skip}")
    print(f"  ❌ 失败: {fail}")
    if interrupted:
        print(f"  🛑 未处理（中断剩余）: {interrupted}")
    print(f"  ⏱️  本次耗时: {elapsed / 60:.1f} 分钟")
    print(f"  📂 Markdown 根目录: {md_root}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将操作手册中的 PDF 批量转为 Markdown（Marker）",
    )
    parser.add_argument(
        "--pdf-root",
        type=Path,
        default=PDF_ROOT,
        help=f"PDF 根目录（默认: {PDF_ROOT}）",
    )
    parser.add_argument(
        "--md-root",
        type=Path,
        default=MD_ROOT,
        help=f"MD 输出根目录（默认: {MD_ROOT}）",
    )
    parser.add_argument(
        "--marker",
        default=DEFAULT_MARKER,
        help="marker_single 可执行文件路径",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="已存在 .md 也强制重新转换",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="仅使用 CPU（设置 CUDA_VISIBLE_DEVICES= ）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅处理前 N 个 PDF（试跑）",
    )
    args = parser.parse_args()

    code = batch_convert(
        args.pdf_root.resolve(),
        args.md_root.resolve(),
        args.marker,
        force=args.force,
        use_cpu_only=args.cpu,
        limit=args.limit,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()

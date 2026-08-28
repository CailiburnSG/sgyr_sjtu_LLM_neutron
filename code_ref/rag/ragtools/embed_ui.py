"""MD/PDF 建库脚本共用的分块参数交互与校验。"""
from __future__ import annotations

import math
import os
import sys
from collections.abc import Callable

DEFAULT_EMBED_BATCH_SIZE = 8
# Ollama nomic-embed-text 等模型的安全字符上限（按字符计；超出会 400）
EMBED_MAX_CHARS = int(os.environ.get("RAG_EMBED_MAX_CHARS", "2048"))

SEC_PER_EMBED_REQUEST_LO = 0.35
SEC_PER_EMBED_REQUEST_HI = 1.0

CHUNK_SIZE_CHOICES: list[tuple[int, str]] = [
    (500, "细块：定位细、chunk 数量多"),
    (800, "默认量级，与 ragtest2 接近"),
    (1200, "中等块，建库更快"),
    (1500, "大块，适合长段落技术报告"),
]

CHUNK_OVERLAP_CHOICES: list[tuple[int, str]] = [
    (50, "低重叠，约 chunk 长度的 10%"),
    (80, "默认重叠，约 chunk 长度的 10%"),
    (100, "中等重叠"),
    (120, "中等偏高，适合较长的 chunk"),
    (150, "高重叠，衔接更稳、块数更多"),
    (160, "用于固定 chunk 长度、只扫 overlap 的对比实验"),
]

ALLOWED_CHUNK_SIZES = [v for v, _ in CHUNK_SIZE_CHOICES]
ALLOWED_CHUNK_OVERLAPS = [v for v, _ in CHUNK_OVERLAP_CHOICES]

MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 8000
MIN_CHUNK_OVERLAP = 0
MAX_CHUNK_OVERLAP = 2000
CUSTOM_MENU_INDEX = 0

CHUNK_SIZE_MEANING = (
    "把一篇 MD 或 pdf 切成多段时，每一段最多包含的字符数。越大段数越少、建库越快，"
    "但检索时定位可能更粗。"
)
CHUNK_OVERLAP_MEANING = (
    "相邻两个 chunk 之间重复保留的字符数。越大上下文衔接越好，"
    "但 chunk 总数会变多、embedding 更慢。"
)


def _desc_for_value(choices: list[tuple[int, str]], value: int) -> str:
    for v, d in choices:
        if v == value:
            return d
    return ""


def validate_chunk_size(value: int) -> None:
    if not MIN_CHUNK_SIZE <= value <= MAX_CHUNK_SIZE:
        print(
            f"❌ chunk_size 须在 {MIN_CHUNK_SIZE}~{MAX_CHUNK_SIZE} 之间，当前: {value}",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_chunk_overlap(value: int, chunk_size: int) -> None:
    if not MIN_CHUNK_OVERLAP <= value <= MAX_CHUNK_OVERLAP:
        print(
            f"❌ chunk_overlap 须在 {MIN_CHUNK_OVERLAP}~{MAX_CHUNK_OVERLAP} 之间，当前: {value}",
            file=sys.stderr,
        )
        sys.exit(1)
    if value >= chunk_size:
        print(
            f"❌ chunk_overlap({value}) 必须小于 chunk_size({chunk_size})",
            file=sys.stderr,
        )
        sys.exit(1)


def estimate_embed_minutes(
    node_count: int, embed_batch_size: int
) -> tuple[int, int, float, float]:
    batch = max(embed_batch_size, 1)
    requests = math.ceil(node_count / batch)
    lo = requests * SEC_PER_EMBED_REQUEST_LO / 60
    hi = requests * SEC_PER_EMBED_REQUEST_HI / 60
    return requests, batch, lo, hi


def validate_pair(chunk_size: int, chunk_overlap: int) -> None:
    validate_chunk_size(chunk_size)
    validate_chunk_overlap(chunk_overlap, chunk_size)
    if chunk_size > EMBED_MAX_CHARS:
        print(
            f"⚠️  chunk_size={chunk_size} 超过 embedding 建议上限 {EMBED_MAX_CHARS} 字符，"
            f"Ollama 可能报 context length 错误；可改用 ≤{EMBED_MAX_CHARS} 或调低 RAG_EMBED_MAX_CHARS",
            file=sys.stderr,
        )


def clamp_node_texts(nodes: list, *, max_chars: int | None = None) -> int:
    """截断超长 chunk，避免 Ollama embed 400。返回被截断的条数。"""
    cap = max_chars if max_chars is not None else EMBED_MAX_CHARS
    clipped = 0
    for node in nodes:
        text = node.get_content() if hasattr(node, "get_content") else node.text
        if len(text) > cap:
            if hasattr(node, "set_content"):
                node.set_content(text[:cap])
            else:
                node.text = text[:cap]
            clipped += 1
    return clipped


def apply_splitter_settings(splitter) -> None:
    """增量 refresh 时必须设置，否则会把整篇文档当作一个 chunk 送去 embedding。"""
    from llama_index.core import Settings

    Settings.node_parser = splitter
    try:
        Settings.transformations = [splitter]
    except Exception:
        pass


def print_presets(
    script_name: str,
    storage_dir_name: Callable[[int, int], str],
) -> None:
    print("\n【1】chunk 长度 chunk_size（每个文本块最多多少字符）\n")
    for i, (val, desc) in enumerate(CHUNK_SIZE_CHOICES, 1):
        print(f"  [{i}] {val}  — {desc}")

    print("\n【2】块重叠 chunk_overlap（相邻两块重复多少字符）\n")
    for i, (val, desc) in enumerate(CHUNK_OVERLAP_CHOICES, 1):
        print(f"  [{i}] {val}  — {desc}")

    print(
        f"\n【自定义】交互时输入 0，或直接输入范围内数字："
        f"chunk_size {MIN_CHUNK_SIZE}~{MAX_CHUNK_SIZE}，"
        f"chunk_overlap {MIN_CHUNK_OVERLAP}~{MAX_CHUNK_OVERLAP} 且 < chunk_size"
    )

    print("\n【3】预设组合示例（overlap 必须小于 chunk_size）\n")
    for sv, _ in CHUNK_SIZE_CHOICES:
        for ov, _ in CHUNK_OVERLAP_CHOICES:
            if ov >= sv:
                continue
            print(
                f"  --chunk-size {sv} --chunk-overlap {ov}  →  "
                f"rag_index/{storage_dir_name(sv, ov)}"
            )

    print(f"\n直接运行 python {script_name}。")
    print("  输入序号/预设数字，或 [0]、或直接输入自定义数字（须在提示范围内）。")
    print("⚠️  每次只建一种组合。\n")


def _prompt_custom_int(
    param_name: str,
    min_val: int,
    max_val: int,
    extra_hint: str = "",
) -> tuple[int, str]:
    print(f"\n  【自定义 {param_name}】")
    print(f"  【允许范围】{min_val} ~ {max_val}")
    if extra_hint:
        print(f"  【注意】{extra_hint}")
    while True:
        raw = input(f">>> 请输入自定义 {param_name}: ").strip()
        if not raw.isdigit():
            print("    ✗ 请输入正整数。")
            continue
        n = int(raw)
        if min_val <= n <= max_val:
            print(f"    ✓ 自定义 {param_name} = {n}")
            return n, f"自定义: {n}"
        print(f"    ✗ 须在 {min_val}~{max_val} 之间，请重试。")


def _prompt_number_choice(
    step: str,
    param_name: str,
    meaning: str,
    choices: list[tuple[int, str]],
    *,
    min_custom: int,
    max_custom: int,
    extra_hint: str = "",
) -> tuple[int, str]:
    allowed = {v for v, _ in choices}
    preset_nums = ", ".join(str(v) for v in allowed)

    print(f"\n{step}")
    print(f"  【这是什么】{meaning}")
    print(
        f"  【怎么输入】序号 1~{len(choices)}；预设值 {preset_nums}；"
        f"输入 0 自定义；或直接输入 {min_custom}~{max_custom} 内其他数字"
    )
    if extra_hint:
        print(f"  【注意】{extra_hint}")
    print("  【选项列表】")
    print(f"    [{CUSTOM_MENU_INDEX}]  自定义 — 手动输入 {min_custom}~{max_custom} 的数值")
    for i, (val, desc) in enumerate(choices, 1):
        print(f"    [{i}]  {val}  — {desc}")

    while True:
        raw = input(f"\n>>> 请输入 {param_name}: ").strip()
        if not raw.isdigit():
            print("    ✗ 请输入数字。")
            continue
        n = int(raw)

        if n == CUSTOM_MENU_INDEX:
            return _prompt_custom_int(param_name, min_custom, max_custom, extra_hint)

        if 1 <= n <= len(choices):
            val, desc = choices[n - 1]
            print(f"    ✓ 已选 {param_name} = {val}（{desc}）")
            return val, desc

        if n in allowed:
            desc = _desc_for_value(choices, n)
            print(f"    ✓ 已选 {param_name} = {n}（{desc}）")
            return n, desc

        if min_custom <= n <= max_custom:
            print(f"    ✓ 自定义 {param_name} = {n}（未在预设表中，但在允许范围内）")
            return n, f"自定义: {n}"

        print(
            f"    ✗ 无效：请填 0、1~{len(choices)}、预设值，或 {min_custom}~{max_custom} 内的数字。"
        )


def _prompt_yes_no(question: str, default_no: bool = True) -> bool:
    hint = "y/N" if default_no else "Y/n"
    raw = input(f"\n>>> {question} ({hint}): ").strip().lower()
    if not raw:
        return not default_no
    return raw in ("y", "yes", "是", "1")


def _prompt_optional_int(question: str, file_ext: str) -> int | None:
    print(f"\n>>> {question}")
    print(f"  # 类型: 正整数；直接回车表示不限制（处理全部 {file_ext}）")
    raw = input(">>> 输入: ").strip()
    if not raw:
        return None
    try:
        n = int(raw)
        if n < 1:
            raise ValueError
        return n
    except ValueError:
        print("  ⚠️  无效数字，将处理全部文件")
        return None


def interactive_select(
    *,
    mode_title: str,
    file_ext: str,
    storage_dir_name: Callable[[int, int], str],
) -> dict:
    print("=" * 60)
    print(f"  {mode_title}")
    print("=" * 60)
    print("  按提示输入即可；每次运行只建一种 size + overlap 组合。")

    chunk_size, size_desc = _prompt_number_choice(
        "【1/4】选择 chunk 长度",
        "chunk_size",
        CHUNK_SIZE_MEANING,
        CHUNK_SIZE_CHOICES,
        min_custom=MIN_CHUNK_SIZE,
        max_custom=MAX_CHUNK_SIZE,
    )
    max_overlap = min(MAX_CHUNK_OVERLAP, chunk_size - 1)
    while True:
        chunk_overlap, overlap_desc = _prompt_number_choice(
            "【2/4】选择块重叠",
            "chunk_overlap",
            CHUNK_OVERLAP_MEANING,
            CHUNK_OVERLAP_CHOICES,
            min_custom=MIN_CHUNK_OVERLAP,
            max_custom=max_overlap,
            extra_hint=f"必须小于当前 chunk_size={chunk_size}（即最多填 {max_overlap}）",
        )
        if chunk_overlap < chunk_size:
            break
        print(
            f"    ✗ overlap={chunk_overlap} 不能 ≥ chunk_size={chunk_size}，请重新选。"
        )
        max_overlap = min(MAX_CHUNK_OVERLAP, chunk_size - 1)

    out_dir = storage_dir_name(chunk_size, chunk_overlap)
    print(f"\n【预览】输出目录: rag_index/{out_dir}")

    limit = _prompt_optional_int(
        f"【3/4】试跑篇数（可选）—— 只处理前 N 个 {file_ext}？",
        file_ext,
    )

    dry_run = _prompt_yes_no(
        "【4/4】是否仅统计 chunk 数量（--dry-run），暂不调用 Ollama？",
        default_no=True,
    )
    force = False
    if not dry_run:
        force = _prompt_yes_no(
            "若该目录已有索引，是否强制删除后重建（--force）？",
            default_no=True,
        )

    if not dry_run and not _prompt_yes_no(
        f"确认开始建库？ chunk_size={chunk_size}, chunk_overlap={chunk_overlap}",
        default_no=False,
    ):
        print("\n已取消。")
        sys.exit(0)

    return {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "size_desc": size_desc,
        "overlap_desc": overlap_desc,
        "limit": limit,
        "force": force,
        "dry_run": dry_run,
        "embed_batch_size": DEFAULT_EMBED_BATCH_SIZE,
    }

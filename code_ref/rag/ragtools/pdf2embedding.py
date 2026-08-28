#!/usr/bin/env python3
"""
将 rag_index/pdf 下的 PDF 向量化并存入 rag_index/（每次只建一种分块配置）。

与 md2embedding.py 对齐，便于 PDF vs MD 对比实验：
  输入: rag_index/pdf/
  输出: rag_index/storage_pdf_c{chunk}_o{overlap}/

示例:
  python pdf2embedding.py
  python pdf2embedding.py --list-presets
  python pdf2embedding.py --chunk-size 800 --chunk-overlap 80
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("pypdf").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent
PDF_ROOT = ROOT / "rag_index" / "pdf"
RAG_INDEX = ROOT / "rag_index"

from embed_ui import (
    ALLOWED_CHUNK_OVERLAPS,
    ALLOWED_CHUNK_SIZES,
    CHUNK_OVERLAP_CHOICES,
    CHUNK_SIZE_CHOICES,
    DEFAULT_EMBED_BATCH_SIZE,
    MAX_CHUNK_OVERLAP,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_OVERLAP,
    MIN_CHUNK_SIZE,
    _desc_for_value,
    apply_splitter_settings,
    clamp_node_texts,
    estimate_embed_minutes,
    interactive_select as _interactive_select,
    print_presets as _print_presets,
    validate_pair,
)

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")


def _chars_as_tokens(text: str) -> list[str]:
    return list(text)


def make_doc_id(rel_path: str) -> str:
    slug = re.sub(
        r"[^\w\u4e00-\u9fff]+",
        "_",
        Path(rel_path).stem,
        flags=re.UNICODE,
    ).strip("_")[:48]
    digest = hashlib.md5(rel_path.encode("utf-8")).hexdigest()[:10]
    return f"{slug}_{digest}" if slug else digest


def parse_pdf_metadata(pdf_path: Path, pdf_root: Path) -> dict:
    rel = pdf_path.relative_to(pdf_root)
    parts = rel.parts
    category = parts[0] if len(parts) >= 2 else (parts[0] if parts else "")
    org = category.split("：")[0].split(":")[0].strip() if category else ""
    return {
        "source_path": f"rag_index/pdf/{rel.as_posix()}",
        "category": category,
        "org": org,
        "file_name": pdf_path.name,
    }


def storage_dir_name(chunk_size: int, chunk_overlap: int) -> str:
    return f"storage_pdf_c{chunk_size}_o{chunk_overlap}"


def find_pdf_files(pdf_root: Path, limit: int | None) -> list[Path]:
    files = sorted(pdf_root.rglob("*.pdf"))
    if limit is not None:
        files = files[:limit]
    return files


def _index_is_ready(storage_dir: Path) -> bool:
    if not storage_dir.is_dir():
        return False
    markers = ("docstore.json", "index_store.json", "default__vector_store.json")
    return any((storage_dir / name).exists() for name in markers)


def print_presets() -> None:
    _print_presets("pdf2embedding.py", storage_dir_name)


def interactive_select() -> dict:
    return _interactive_select(
        mode_title="PDF → Embedding 建库（交互模式）",
        file_ext=".pdf",
        storage_dir_name=storage_dir_name,
    )


def load_pdf_documents(pdf_files: list[Path], pdf_root: Path) -> list:
    try:
        import fitz  # pymupdf
    except ImportError:
        print("❌ 请先安装: pip install pymupdf", file=sys.stderr)
        sys.exit(1)

    from llama_index.core import Document

    documents = []
    for pdf in pdf_files:
        rel = pdf.relative_to(pdf_root).as_posix()
        meta = parse_pdf_metadata(pdf, pdf_root)
        meta["doc_id"] = make_doc_id(rel)
        meta["pipeline"] = "pdf"
        print(f"  📄 解析 PDF: {rel} ({pdf.stat().st_size // 1024} KB)")

        doc = fitz.open(pdf)
        parts = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                parts.append(f"## Page {i + 1}\n\n{text}")
        doc.close()

        if not parts:
            print(f"    ⚠️  未提取到文本，跳过: {pdf.name}")
            continue

        documents.append(
            Document(text="\n\n".join(parts), metadata=meta)
        )
    return documents


def _check_ollama() -> None:
    import urllib.error
    import urllib.request

    url = f"{OLLAMA_BASE.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                raise RuntimeError(f"status {resp.status}")
    except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
        print(f"❌ Ollama 不可用 ({url}): {e}", file=sys.stderr)
        sys.exit(1)


def build_index(
    documents: list,
    storage_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    embed_batch_size: int,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    from llama_index.core import Settings, VectorStoreIndex, StorageContext, load_index_from_storage
    from llama_index.core.node_parser import TokenTextSplitter
    from llama_index.embeddings.ollama import OllamaEmbedding

    if force and storage_dir.exists():
        import shutil

        shutil.rmtree(storage_dir)
        print(f"  🗑️  已删除旧索引: {storage_dir.name}")

    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE,
        embed_batch_size=embed_batch_size,
    )
    splitter = TokenTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer=_chars_as_tokens,
        separator="\n\n",
        backup_separators=["\n", "。", ".", " "],
    )

    apply_splitter_settings(splitter)

    nodes = splitter.get_nodes_from_documents(documents)
    clipped = clamp_node_texts(nodes)
    print(f"\n▶ 分块完成: 共 {len(nodes)} 个 chunk（{chunk_size} / {chunk_overlap}）")
    if clipped:
        print(f"  ⚠️  {clipped} 个 chunk 已截断至 embedding 安全长度")

    config = {
        "pipeline": "pdf",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embed_model": EMBED_MODEL,
        "embed_batch_size": embed_batch_size,
        "doc_count": len(documents),
        "chunk_count": len(nodes),
        "pdf_root": str(PDF_ROOT),
        "storage_dir": str(storage_dir),
    }
    config_path = storage_dir / "build_config.json"
    if dry_run:
        storage_dir.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"▶ --dry-run: 已写入配置预览 {config_path.relative_to(ROOT)}，未调用 embedding")
        return

    _check_ollama()

    if _index_is_ready(storage_dir):
        print(f"▶ 发现已有索引，尝试增量更新: {storage_dir.name}")
        ctx = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(ctx, embed_model=Settings.embed_model)
        refreshed = index.refresh_ref_docs(documents)
        if any(refreshed):
            index.storage_context.persist(persist_dir=str(storage_dir))
            print(f"  ✅ 增量更新 {sum(refreshed)} 篇")
        else:
            print("  ✨ 无变更，索引已是最新")
    else:
        n_req, batch, est_lo, est_hi = estimate_embed_minutes(len(nodes), embed_batch_size)
        print(
            f"▶ 开始向量化: {len(nodes)} chunks，约 {n_req} 次 Ollama 请求"
            f"（batch={batch}）"
        )
        print(
            f"  粗估耗时 {max(1, est_lo):.0f}~{max(1, est_hi):.0f} 分钟"
            f"（实际常接近上限，全库可能数小时）"
        )
        storage_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        index = VectorStoreIndex(nodes, show_progress=True)
        index.storage_context.persist(persist_dir=str(storage_dir))
        print(f"  ✅ 建库完成，耗时 {(time.time() - t0) / 60:.1f} 分钟")

    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  📝 配置已保存: {config_path.relative_to(ROOT)}")


def run_build(params: dict) -> None:
    chunk_size = params["chunk_size"]
    chunk_overlap = params["chunk_overlap"]
    size_desc = params.get("size_desc") or _desc_for_value(CHUNK_SIZE_CHOICES, chunk_size)
    overlap_desc = params.get("overlap_desc") or _desc_for_value(
        CHUNK_OVERLAP_CHOICES, chunk_overlap
    )
    storage_dir = RAG_INDEX / storage_dir_name(chunk_size, chunk_overlap)

    print("\n" + "=" * 60)
    print("  开始执行")
    print("=" * 60)
    print(f"  chunk_size    : {chunk_size}（{size_desc}）")
    print(f"  chunk_overlap : {chunk_overlap}（{overlap_desc}）")
    print(f"  输出目录    : {storage_dir.relative_to(ROOT)}")
    print(f"  limit       : {params['limit'] or '全部'}")
    print(f"  dry_run     : {params['dry_run']}")
    print(f"  force       : {params['force']}")

    if not PDF_ROOT.is_dir():
        print(f"\n❌ 未找到 PDF 目录: {PDF_ROOT}", file=sys.stderr)
        sys.exit(1)

    print(f"\n▶ 扫描 {PDF_ROOT.relative_to(ROOT)} …")
    pdf_files = find_pdf_files(PDF_ROOT, params["limit"])
    if not pdf_files:
        print("❌ 未找到 .pdf 文件", file=sys.stderr)
        sys.exit(1)
    print(f"  ✅ 共 {len(pdf_files)} 个 PDF 文件")

    print("\n▶ 加载并解析 PDF…")
    documents = load_pdf_documents(pdf_files, PDF_ROOT)
    if not documents:
        print("❌ 没有可索引的 PDF 文本", file=sys.stderr)
        sys.exit(1)

    print("\n▶ 分块与向量化…")
    build_index(
        documents,
        storage_dir,
        chunk_size,
        chunk_overlap,
        params["embed_batch_size"],
        force=params["force"],
        dry_run=params["dry_run"],
    )

    print("\n" + "=" * 60)
    print("  任务结束")
    print(f"  索引位置: {storage_dir}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF 向量化：交互输入 chunk 数字，或 --chunk-size / --chunk-overlap",
    )
    parser.add_argument("--list-presets", action="store_true", help="列出分块选项后退出")
    parser.add_argument(
        "--chunk-size",
        type=int,
        metavar="N",
        help=f"块长度（{MIN_CHUNK_SIZE}~{MAX_CHUNK_SIZE}，预设 {ALLOWED_CHUNK_SIZES}）",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        metavar="N",
        help=f"块重叠（须 < chunk_size，预设 {ALLOWED_CHUNK_OVERLAPS}）",
    )
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 个 .pdf（试跑）")
    parser.add_argument("--force", action="store_true", help="删除对应 storage 后重建")
    parser.add_argument("--dry-run", action="store_true", help="只分块统计，不 embedding")
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=DEFAULT_EMBED_BATCH_SIZE,
        help=f"Ollama 批量大小（默认 {DEFAULT_EMBED_BATCH_SIZE}）",
    )
    args = parser.parse_args()

    if args.list_presets:
        print_presets()
        return

    if args.chunk_size is not None and args.chunk_overlap is not None:
        validate_pair(args.chunk_size, args.chunk_overlap)
        run_build(
            {
                "chunk_size": args.chunk_size,
                "chunk_overlap": args.chunk_overlap,
                "limit": args.limit,
                "force": args.force,
                "dry_run": args.dry_run,
                "embed_batch_size": args.embed_batch_size,
            }
        )
        return

    if (args.chunk_size is None) ^ (args.chunk_overlap is None):
        print("❌ --chunk-size 与 --chunk-overlap 需同时指定，或都不指定（走交互）", file=sys.stderr)
        sys.exit(1)

    params = interactive_select()
    run_build(params)


if __name__ == "__main__":
    main()

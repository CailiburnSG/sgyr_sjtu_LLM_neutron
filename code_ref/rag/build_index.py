#!/usr/bin/env python3
"""
对比阶段建库：从 操作手册 构建 PDF 库与 MD 库（LlamaIndex + Ollama embedding）。

用法:
  python build_index.py --export-md          # 仅从 PDF 导出 MD（不建索引）
  python build_index.py --pipeline pdf --limit 2   # 试跑 2 份 PDF
  python build_index.py --pipeline both      # PDF + MD 两个库
  python build_index.py --pipeline both --force  # 删除旧库重建
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path

# 降低无关日志（embedding 时 httpx 每条 chunk 打一行 INFO 会刷屏）
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# 项目根目录（脚本在 rag_compare/ 下）
ROOT = Path(__file__).resolve().parent.parent
PDF_ROOT = ROOT / "操作手册"
MD_ROOT = ROOT / "rag_index" / "md"
MANIFEST_PATH = ROOT / "rag_index" / "manifest.jsonl"
STORAGE_PDF = ROOT / "rag_index" / "storage_pdf"
STORAGE_MD = ROOT / "rag_index" / "storage_md"

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")

# 默认 800 字/chunk；试跑可用 --chunk-size 1500 减少请求次数（对比实验可接受）
TEXT_CHUNK_CHARS = 800
TEXT_CHUNK_OVERLAP_CHARS = 80
DEFAULT_EMBED_BATCH_SIZE = 8


def _chars_as_tokens(text: str) -> list[str]:
    return list(text)


def make_doc_id(rel_path: str) -> str:
    rel = rel_path.replace("\\", "/")
    stem = Path(rel).stem
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", stem, flags=re.UNICODE).strip("_")[:48]
    digest = hashlib.md5(rel.encode("utf-8")).hexdigest()[:10]
    return f"{slug}_{digest}" if slug else digest


def parse_path_metadata(rel_path: str) -> dict:
    parts = Path(rel_path).parts
    # 操作手册 / <category> / ... / file.pdf
    category = parts[1] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
    org = category.split("：")[0].split(":")[0].strip() if category else ""
    return {
        "source_path": rel_path.replace("\\", "/"),
        "category": category,
        "org": org,
    }


def iter_pdfs(limit: int | None = None) -> list[Path]:
    files = sorted(PDF_ROOT.rglob("*.pdf"))
    if limit is not None:
        files = files[:limit]
    return files


def md_path_for_pdf(pdf: Path) -> Path:
    rel = pdf.relative_to(PDF_ROOT)
    return MD_ROOT / rel.with_suffix(".md")


def md_paths_for_pdfs(pdfs: list[Path]) -> list[Path]:
    """只处理本次 run 对应的 MD（与 --limit 一致），不扫整个 md 目录。"""
    paths = []
    for pdf in pdfs:
        md = md_path_for_pdf(pdf)
        if md.is_file():
            paths.append(md)
        else:
            print(f"  [md] 跳过（未导出）: {md.relative_to(ROOT)}")
    return paths


def _index_is_ready(storage_dir: Path) -> bool:
    """空目录不算已有索引，避免误走 load_index_from_storage。"""
    if not storage_dir.is_dir():
        return False
    markers = ("docstore.json", "index_store.json", "default__vector_store.json")
    return any((storage_dir / name).exists() for name in markers)


def build_manifest(pdfs: list[Path]) -> list[dict]:
    rows = []
    for p in pdfs:
        rel = p.relative_to(ROOT).as_posix()
        meta = parse_path_metadata(rel)
        rows.append(
            {
                "doc_id": make_doc_id(rel),
                "file_name": p.name,
                **meta,
            }
        )
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"manifest: {MANIFEST_PATH} ({len(rows)} docs)")
    return rows


def export_md_from_pdfs(pdfs: list[Path]) -> int:
    try:
        import fitz  # pymupdf
    except ImportError:
        print("请先安装: pip install pymupdf", file=sys.stderr)
        sys.exit(1)

    count = 0
    for pdf in pdfs:
        rel = pdf.relative_to(PDF_ROOT)
        out = MD_ROOT / rel.with_suffix(".md")
        out.parent.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf)
        rel_posix = pdf.relative_to(ROOT).as_posix()
        doc_id = make_doc_id(rel_posix)
        meta = parse_path_metadata(rel_posix)

        lines = [
            "---",
            f"doc_id: {doc_id}",
            f"source_path: {rel_posix}",
            f"category: {meta['category']}",
            f"org: {meta['org']}",
            "---",
            "",
        ]
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text:
                continue
            lines.append(f"## Page {i + 1}")
            lines.append("")
            lines.append(text)
            lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        count += 1
        print(f"  md export: {out.relative_to(ROOT)}")

    print(f"exported {count} markdown files under {MD_ROOT}")
    return count


def _check_ollama() -> None:
    import urllib.error
    import urllib.request

    url = f"{OLLAMA_BASE.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                raise RuntimeError(f"status {resp.status}")
    except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
        print(f"Ollama 不可用 ({url}): {e}", file=sys.stderr)
        print("请先启动 ollama，并确保已 pull:", EMBED_MODEL, file=sys.stderr)
        sys.exit(1)


def load_md_documents(md_files: list[Path], manifest_rows: list[dict]):
    from llama_index.core import Document

    meta_by_stem = {Path(r["source_path"]).stem: r for r in manifest_rows}
    documents = []
    for md in md_files:
        print(f"[md] 读取: {md.relative_to(ROOT)} ({md.stat().st_size // 1024} KB)")
        text = md.read_text(encoding="utf-8", errors="ignore")
        row = meta_by_stem.get(md.stem, {})
        documents.append(
            Document(
                text=text,
                metadata={
                    "file_name": md.name,
                    "pipeline": "md",
                    "doc_id": row.get("doc_id", ""),
                    "source_path": row.get("source_path", ""),
                    "category": row.get("category", ""),
                    "org": row.get("org", ""),
                },
            )
        )
    return documents


def load_pdf_documents(pdfs: list[Path], manifest_rows: list[dict]):
    """用 PyMuPDF 读 PDF，与 MD 导出一致，避免 pypdf 的 FloatObject 警告。"""
    import fitz
    from llama_index.core import Document

    doc_meta_by_file = {Path(r["source_path"]).name: r for r in manifest_rows}
    documents = []
    for pdf in pdfs:
        print(f"[pdf] 解析: {pdf.relative_to(ROOT)}")
        doc = fitz.open(pdf)
        parts = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                parts.append(f"## Page {i + 1}\n\n{text}")
        doc.close()
        if not parts:
            print(f"  [pdf] 警告: 未提取到文本，跳过 {pdf.name}")
            continue
        row = doc_meta_by_file.get(pdf.name, {})
        meta = {
            "file_name": pdf.name,
            "pipeline": "pdf",
            "doc_id": row.get("doc_id", ""),
            "source_path": row.get("source_path", ""),
            "category": row.get("category", ""),
            "org": row.get("org", ""),
        }
        documents.append(Document(text="\n\n".join(parts), metadata=meta))
    return documents


def _configure_settings(chunk_size: int, chunk_overlap: int, embed_batch_size: int):
    from llama_index.core import Settings
    from llama_index.core.node_parser import TokenTextSplitter
    from llama_index.embeddings.ollama import OllamaEmbedding

    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE,
        embed_batch_size=embed_batch_size,
    )
    Settings.node_parser = TokenTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer=_chars_as_tokens,
        separator="\n\n",
        backup_separators=["\n", "。", ".", " "],
    )
    return Settings.node_parser


def build_vector_index(
    storage_dir: Path,
    pipeline: str,
    manifest_rows: list[dict],
    force: bool,
    documents: list,
    chunk_size: int = TEXT_CHUNK_CHARS,
    chunk_overlap: int = TEXT_CHUNK_OVERLAP_CHARS,
    embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    dry_run: bool = False,
) -> None:
    from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage

    if force and storage_dir.exists():
        import shutil
        shutil.rmtree(storage_dir)
        print(f"removed {storage_dir}")

    splitter = _configure_settings(chunk_size, chunk_overlap, embed_batch_size)

    if not documents:
        print(f"未找到可索引文档: pipeline={pipeline}", file=sys.stderr)
        sys.exit(1)

    print(f"[{pipeline}] 已加载 {len(documents)} 个文档")

    nodes = splitter.get_nodes_from_documents(documents)
    for doc in documents:
        fname = doc.metadata.get("file_name", "?")
        n = sum(1 for nd in nodes if nd.metadata.get("file_name") == fname)
        print(f"  - {fname}: {n} chunks")

    if dry_run:
        print(f"[{pipeline}] --dry-run: 共 {len(nodes)} chunks，未调用 Ollama")
        return

    if _index_is_ready(storage_dir):
        print(f"[{pipeline}] loading existing index: {storage_dir}")
        ctx = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(ctx)
        refreshed = index.refresh_ref_docs(documents)
        if any(refreshed):
            index.storage_context.persist(persist_dir=str(storage_dir))
            print(f"[{pipeline}] refreshed {sum(refreshed)} docs")
        else:
            print(f"[{pipeline}] index up to date")
    else:
        print(f"[{pipeline}] building new index -> {storage_dir}")
        storage_dir.mkdir(parents=True, exist_ok=True)
        est_sec = len(nodes) * 0.05 / max(embed_batch_size, 1)
        print(
            f"[{pipeline}] 将向量化 {len(nodes)} 个 chunk，"
            f"batch={embed_batch_size}，粗估约 {max(1, est_sec/60):.0f} 分钟..."
        )
        index = VectorStoreIndex(nodes, show_progress=True)
        index.storage_context.persist(persist_dir=str(storage_dir))
        print(f"[{pipeline}] 完成 -> {storage_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="操作手册 RAG 对比建库 (PDF / MD)")
    parser.add_argument(
        "--pipeline",
        choices=("pdf", "md", "both"),
        default="both",
        help="建哪个库；both=两个都建",
    )
    parser.add_argument("--export-md", action="store_true", help="只把 PDF 导出为 MD，不建向量库")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只处理前 N 个 PDF；MD 索引也只处理这 N 个对应文件（不再扫全目录）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计 chunk 数量，不调用 Ollama",
    )
    parser.add_argument("--force", action="store_true", help="删除已有 storage 后重建")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=TEXT_CHUNK_CHARS,
        help="分块字符数，越大 chunk 越少、越快（默认 800）",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=TEXT_CHUNK_OVERLAP_CHARS,
        help="分块重叠字符数（默认 80）",
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=DEFAULT_EMBED_BATCH_SIZE,
        help="Ollama 批量 embedding（默认 8；若 400 错误改回 1）",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="试跑加速：chunk-size=1500, overlap=100, batch=16",
    )
    args = parser.parse_args()

    if args.fast:
        args.chunk_size = 1500
        args.chunk_overlap = 100
        args.embed_batch_size = 16
        print(
            f"快速模式: chunk={args.chunk_size}, overlap={args.chunk_overlap}, "
            f"batch={args.embed_batch_size}"
        )

    if not PDF_ROOT.is_dir():
        print(f"找不到目录: {PDF_ROOT}", file=sys.stderr)
        sys.exit(1)

    pdfs = iter_pdfs(args.limit)
    if not pdfs:
        print(f"没有 PDF: {PDF_ROOT}", file=sys.stderr)
        sys.exit(1)

    print(f"PDF 数量: {len(pdfs)} (limit={args.limit})")
    manifest_rows = build_manifest(pdfs)

    if args.export_md or args.pipeline in ("md", "both"):
        export_md_from_pdfs(pdfs)

    if args.export_md:
        return

    if not args.dry_run:
        _check_ollama()

    idx_kw = dict(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embed_batch_size=args.embed_batch_size,
    )

    idx_kw["dry_run"] = args.dry_run

    if args.pipeline in ("pdf", "both"):
        pdf_docs = load_pdf_documents(pdfs, manifest_rows)
        build_vector_index(STORAGE_PDF, "pdf", manifest_rows, args.force, pdf_docs, **idx_kw)

    if args.pipeline in ("md", "both"):
        md_files = md_paths_for_pdfs(pdfs)
        if not md_files:
            print("没有可索引的 MD，请先导出", file=sys.stderr)
            sys.exit(1)
        md_docs = load_md_documents(md_files, manifest_rows)
        build_vector_index(STORAGE_MD, "md", manifest_rows, args.force, md_docs, **idx_kw)

    print("\n完成。索引位置:")
    if args.pipeline in ("pdf", "both"):
        print(f"  PDF 库: {STORAGE_PDF}")
    if args.pipeline in ("md", "both"):
        print(f"  MD  库: {STORAGE_MD}")
    print(f"  清单:   {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

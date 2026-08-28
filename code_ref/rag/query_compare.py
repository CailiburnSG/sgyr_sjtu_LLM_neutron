#!/usr/bin/env python3
"""对 PDF / MD 两个库做检索对比（不调用 LLM 生成）。"""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORAGE_PDF = ROOT / "rag_index" / "storage_pdf"
STORAGE_MD = ROOT / "rag_index" / "storage_md"
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")


def load_engine(storage_dir: Path, top_k: int):
    from llama_index.core import StorageContext, load_index_from_storage
    from llama_index.embeddings.ollama import OllamaEmbedding

    embed = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE,
        embed_batch_size=1,
    )
    ctx = StorageContext.from_defaults(persist_dir=str(storage_dir))
    index = load_index_from_storage(ctx, embed_model=embed)
    return index.as_retriever(similarity_top_k=top_k)


def search(label: str, storage_dir: Path, question: str, top_k: int) -> None:
    if not storage_dir.exists():
        print(f"[{label}] 索引不存在: {storage_dir}")
        return
    retriever = load_engine(storage_dir, top_k)
    nodes = retriever.retrieve(question)
    print(f"\n=== {label} (top {top_k}) ===")
    for i, n in enumerate(nodes, 1):
        md = n.metadata or {}
        print(
            f"  [{i}] score={n.score:.4f} doc_id={md.get('doc_id','?')} "
            f"file={md.get('file_name', md.get('filename', '?'))}"
        )
        preview = (n.text or "")[:200].replace("\n", " ")
        print(f"      {preview}...")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question", help="检索问题")
    p.add_argument("-k", type=int, default=5)
    args = p.parse_args()
    search("PDF库", STORAGE_PDF, args.question, args.k)
    search("MD库", STORAGE_MD, args.question, args.k)


if __name__ == "__main__":
    main()

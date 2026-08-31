#!/usr/bin/env python3
"""Run technical-detail query sensitivity on the historical character-chunk grid.

This is a fresh MiniLM experiment. It reuses the historical *chunk-size/overlap
grid* and character-token splitter, but not the historical nomic-embed-text
vectors; every selected configuration is re-embedded with the chosen MiniLM model.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
from llama_index.core import Document
from llama_index.core.node_parser import TokenTextSplitter
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "md"
PILOT = ROOT / "evidence" / "rag_results" / "query_formulation_sensitivity" / "technical_detail_query_pilot"
QUERY_SET = PILOT / "query_set.json"
OUT = ROOT / "evidence" / "rag_results" / "query_formulation_sensitivity" / "historical_chunk_grid_minilm"
MODELS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
)
CONFIGS = ((800, 50), (800, 80), (800, 100), (800, 120), (800, 150),
           (1000, 80), (1000, 100), (1000, 120), (1000, 150),
           (1200, 80), (1200, 100), (1200, 120), (1200, 150),
           (1500, 80), (1500, 100), (1500, 120), (1500, 150))
TOP_K, TRIALS, SEED = 10, 10, 20260831


def record_documents() -> tuple[list[dict[str, str]], list[Document]]:
    records, documents = [], []
    for path in sorted(CORPUS.rglob("*.md")):
        rel = path.relative_to(CORPUS)
        category = rel.parts[0]
        record = {"doc_id": str(rel), "category": category,
                  "text": path.read_text(encoding="utf-8", errors="ignore")}
        records.append(record)
        documents.append(Document(text=record["text"], metadata={"doc_id": record["doc_id"], "category": category}))
    if len(records) != 64 or sum(record["category"] == "IAEA" for record in records) != 13:
        raise RuntimeError("Expected the checked-in 64-document corpus with 13 IAEA core documents")
    return records, documents


def split_documents(documents: list[Document], chunk_size: int, overlap: int) -> tuple[list[str], list[str]]:
    splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap,
                                 tokenizer=list, separator="\n\n",
                                 backup_separators=["\n", "。", ".", " "])
    nodes = splitter.get_nodes_from_documents(documents)
    texts = [node.get_content(metadata_mode="none") for node in nodes]
    doc_ids = [str(node.metadata["doc_id"]) for node in nodes]
    return texts, doc_ids


def encode(model: SentenceTransformer, model_name: str, texts: list[str], kind: str, batch_size: int) -> np.ndarray:
    if "multilingual-e5" in model_name:
        prefix = "query: " if kind == "query" else "passage: "
        texts = [prefix + text for text in texts]
    return model.encode(texts, batch_size=batch_size, show_progress_bar=True,
                        normalize_embeddings=True, convert_to_numpy=True)


def run_one(model_name: str, chunk_size: int, overlap: int, batch_size: int, overwrite: bool) -> None:
    slug = model_name.replace("/", "__")
    out_dir = OUT / f"c{chunk_size}_o{overlap}" / slug
    detail_path = out_dir / "scope_detail.csv"
    if detail_path.exists() and not overwrite:
        print(f"Skip existing result: {detail_path}")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    queries = spec["baseline_queries"] + spec["technical_detail_queries"]
    records, documents = record_documents()
    texts, doc_ids = split_documents(documents, chunk_size, overlap)
    print(f"{model_name}: chunking {chunk_size}/{overlap}; {len(texts)} chunks")
    model = SentenceTransformer(model_name, device="cpu")
    started = time.time()
    vectors = encode(model, model_name, texts, "passage", batch_size)
    qvectors = encode(model, model_name, [item["query"] for item in queries], "query", batch_size)
    category_by_doc = {record["doc_id"]: record["category"] for record in records}
    by_doc = {record["doc_id"]: [] for record in records}
    for index, doc_id in enumerate(doc_ids):
        by_doc[doc_id].append(index)
    core_docs = [record["doc_id"] for record in records if record["category"] == "IAEA"]
    other_docs = [record["doc_id"] for record in records if record["category"] != "IAEA"]
    core_indices = [index for doc_id in core_docs for index in by_doc[doc_id]]
    counts = [0] + list(range(5, len(other_docs) + 1, 5))
    if counts[-1] != len(other_docs):
        counts.append(len(other_docs))
    rows = []
    for query, qvec in zip(queries, qvectors, strict=True):
        for extra in counts:
            for trial in range(1 if extra == 0 else TRIALS):
                rng = random.Random(f"{SEED}|{model_name}|{chunk_size}|{overlap}|{query['query_id']}|{extra}|{trial}")
                selected = other_docs if extra == len(other_docs) else rng.sample(other_docs, extra)
                pool = core_indices + [i for doc_id in selected for i in by_doc[doc_id]]
                scores = vectors[pool] @ qvec
                top_local = np.argpartition(scores, -TOP_K)[-TOP_K:]
                top_local = top_local[np.argsort(scores[top_local])[::-1]]
                top_indices = [pool[int(i)] for i in top_local]
                top_categories = [category_by_doc[doc_ids[i]] for i in top_indices]
                rows.append({"model": model_name, "chunk_size": chunk_size, "chunk_overlap": overlap,
                             "query_id": query["query_id"], "query": query["query"],
                             "family": query["family"], "language": query["language"],
                             "extra_docs": extra, "trial": trial,
                             "top1_score": float(scores[top_local[0]]),
                             "top10_mean_score": float(scores[top_local].mean()),
                             "iaea_priority_top10": sum(c == "IAEA" for c in top_categories) / TOP_K,
                             "first_iaea_rank": next((rank for rank, c in enumerate(top_categories, 1)
                                                      if c == "IAEA"), TOP_K + 1)})
    detail = pd.DataFrame(rows)
    cols = ["model", "chunk_size", "chunk_overlap", "query_id", "query", "family", "language", "extra_docs"]
    summary = detail.groupby(cols, as_index=False).agg(
        n_trials=("trial", "count"), top1_score_mean=("top1_score", "mean"), top1_score_std=("top1_score", "std"),
        top10_mean_score_mean=("top10_mean_score", "mean"), top10_mean_score_std=("top10_mean_score", "std"),
        iaea_priority_top10_mean=("iaea_priority_top10", "mean"), iaea_priority_top10_std=("iaea_priority_top10", "std"),
        first_iaea_rank_mean=("first_iaea_rank", "mean"), first_iaea_rank_std=("first_iaea_rank", "std"))
    detail.to_csv(detail_path, index=False)
    summary.to_csv(out_dir / "scope_summary.csv", index=False)
    (out_dir / "metadata.json").write_text(json.dumps({
        "model": model_name, "documents": len(records), "core_documents": len(core_docs), "chunks": len(texts),
        "chunk_size": chunk_size, "chunk_overlap": overlap, "splitter": "LlamaIndex TokenTextSplitter with character tokenizer",
        "top_k": TOP_K, "trials": TRIALS, "seed": SEED, "elapsed_seconds": round(time.time() - started, 1),
        "query_set": str(QUERY_SET.relative_to(ROOT)),
        "scope": "fresh MiniLM re-embedding on the historical chunk-size/overlap grid; not the historical nomic index"
    }, indent=2), encoding="utf-8")


def parse_config(raw: str) -> tuple[int, int]:
    try:
        size, overlap = (int(part) for part in raw.split(":"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("configuration must be SIZE:OVERLAP, e.g. 800:80") from exc
    if (size, overlap) not in CONFIGS:
        raise argparse.ArgumentTypeError(f"configuration {size}:{overlap} is not in the 17 historical settings")
    return size, overlap


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=parse_config, action="append", help="Repeatable; defaults to 800:80 calibration")
    parser.add_argument("--all-configs", action="store_true", help="Run all 17 historical settings")
    parser.add_argument("--model", choices=MODELS, action="append", help="Repeatable; defaults to both MiniLM encoders")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    configs = CONFIGS if args.all_configs else (args.config or [(800, 80)])
    for config in configs:
        for model in args.model or MODELS:
            run_one(model, *config, args.batch_size, args.overwrite)


if __name__ == "__main__":
    main()

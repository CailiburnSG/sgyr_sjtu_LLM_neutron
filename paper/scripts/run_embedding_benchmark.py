#!/usr/bin/env python3
"""CPU benchmark of real multilingual embedding models on the checked-in corpus.

This is intentionally a new benchmark, not a reconstruction of the historical
nomic-embed-text/LlamaIndex index. It uses the same 64-document corpus, 13 IAEA
core documents, four fixed bilingual queries, top-10 retrieval, and controlled
supplement expansion, but uses 240-word chunks so every tested encoder sees its
full input within its sequence limit.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "md"
OUT = ROOT / "evidence" / "embedding_benchmark"
QUERIES = [("zh", "中子", "core_term"), ("en", "neutron", "core_term"),
           ("zh", "中子测量电流", "phrase"), ("en", "neutron measurement current", "phrase")]
CHUNK_WORDS = 240
OVERLAP_WORDS = 24
TOP_K = 10
TRIALS = 10
SEED = 20260828


def document_records() -> list[dict[str, str]]:
    records = []
    for path in sorted(CORPUS.rglob("*.md")):
        relative = path.relative_to(CORPUS)
        records.append({"doc_id": str(relative), "category": relative.parts[0],
                        "text": path.read_text(encoding="utf-8", errors="ignore")})
    core = [item for item in records if item["category"] == "IAEA"]
    if len(records) != 64 or len(core) != 13:
        raise RuntimeError(f"Expected 64 documents / 13 IAEA core documents; got {len(records)} / {len(core)}")
    return records


def chunk_text(text: str) -> list[str]:
    words = re.findall(r"\S+", text)
    stride = CHUNK_WORDS - OVERLAP_WORDS
    return [" ".join(words[i:i + CHUNK_WORDS]) for i in range(0, len(words), stride)
            if len(words[i:i + CHUNK_WORDS]) >= 24]


def corpus_chunks(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, list[int]]]:
    chunks, by_doc = [], {}
    for record in records:
        indices = []
        for number, text in enumerate(chunk_text(record["text"])):
            indices.append(len(chunks))
            chunks.append({"doc_id": record["doc_id"], "category": record["category"],
                           "chunk_id": f"{record['doc_id']}#{number}", "text": text})
        by_doc[record["doc_id"]] = indices
    return chunks, by_doc


def prefixed_texts(model_name: str, texts: list[str], kind: str) -> list[str]:
    if "multilingual-e5" in model_name:
        prefix = "query: " if kind == "query" else "passage: "
        return [prefix + text for text in texts]
    return texts


def encode(model: SentenceTransformer, model_name: str, texts: list[str], kind: str, batch_size: int) -> np.ndarray:
    return model.encode(prefixed_texts(model_name, texts, kind), batch_size=batch_size,
                        show_progress_bar=True, normalize_embeddings=True,
                        convert_to_numpy=True)


def run_scope(model_name: str, batch_size: int, overwrite: bool) -> None:
    slug = model_name.replace("/", "__")
    out_dir = OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "scope_summary.csv"
    if result_path.exists() and not overwrite:
        print(f"Skip existing benchmark: {result_path}")
        return

    records = document_records()
    chunks, by_doc = corpus_chunks(records)
    texts = [chunk["text"] for chunk in chunks]
    print(f"Loading {model_name}; {len(records)} docs, {len(chunks)} chunks")
    model = SentenceTransformer(model_name, device="cpu")
    t0 = time.time()
    vectors = encode(model, model_name, texts, "passage", batch_size)
    query_vectors = encode(model, model_name, [q for _, q, _ in QUERIES], "query", batch_size)
    np.save(out_dir / "chunk_embeddings.npy", vectors)

    core_docs = [record["doc_id"] for record in records if record["category"] == "IAEA"]
    other_docs = [record["doc_id"] for record in records if record["category"] != "IAEA"]
    core_indices = [index for doc_id in core_docs for index in by_doc[doc_id]]
    counts = [0] + list(range(5, len(other_docs) + 1, 5))
    if counts[-1] != len(other_docs):
        counts.append(len(other_docs))
    rows = []
    for query_index, (lang, query, query_tag) in enumerate(QUERIES):
        qvec = query_vectors[query_index]
        for extra in counts:
            repeats = 1 if extra == 0 else TRIALS
            for trial in range(repeats):
                rng = random.Random(f"{SEED}|{model_name}|{query}|{extra}|{trial}")
                selected = other_docs if extra == len(other_docs) else rng.sample(other_docs, extra)
                pool = core_indices + [index for doc_id in selected for index in by_doc[doc_id]]
                scores = vectors[pool] @ qvec
                top_local = np.argpartition(scores, -TOP_K)[-TOP_K:]
                top_local = top_local[np.argsort(scores[top_local])[::-1]]
                top_indices = [pool[int(i)] for i in top_local]
                top_chunks = [chunks[index] for index in top_indices]
                purity = sum(c["category"] == "IAEA" for c in top_chunks) / TOP_K
                first_rank = next((rank for rank, c in enumerate(top_chunks, 1) if c["category"] == "IAEA"), TOP_K + 1)
                rows.append({"model": model_name, "chunk_words": CHUNK_WORDS, "overlap_words": OVERLAP_WORDS,
                             "lang": lang, "query": query, "query_tag": query_tag, "extra_docs": extra,
                             "trial": trial, "pool_docs": len(core_docs) + extra, "pool_chunks": len(pool),
                             "top1_score": float(scores[top_local[0]]),
                             "top10_mean_score": float(scores[top_local].mean()),
                             "iaea_priority_top10": purity, "first_iaea_rank": first_rank})
    detail = pd.DataFrame(rows)
    summary = detail.groupby(["model", "chunk_words", "overlap_words", "lang", "query", "query_tag", "extra_docs"], as_index=False).agg(
        n_trials=("trial", "count"), pool_docs=("pool_docs", "mean"), pool_chunks=("pool_chunks", "mean"),
        top1_score_mean=("top1_score", "mean"), top1_score_std=("top1_score", "std"),
        top10_mean_score_mean=("top10_mean_score", "mean"), top10_mean_score_std=("top10_mean_score", "std"),
        iaea_priority_top10_mean=("iaea_priority_top10", "mean"), iaea_priority_top10_std=("iaea_priority_top10", "std"),
        first_iaea_rank_mean=("first_iaea_rank", "mean"), first_iaea_rank_std=("first_iaea_rank", "std"))
    detail.to_csv(out_dir / "scope_detail.csv", index=False)
    summary.to_csv(result_path, index=False)
    metadata = {"model": model_name, "device": "cpu", "documents": len(records), "core_documents": len(core_docs),
                "supplementary_documents": len(other_docs), "chunks": len(chunks), "chunk_words": CHUNK_WORDS,
                "overlap_words": OVERLAP_WORDS, "top_k": TOP_K, "trials": TRIALS,
                "queries": QUERIES, "elapsed_seconds": round(time.time() - t0, 1)}
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True, help="Hugging Face SentenceTransformer model")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for model_name in args.model:
        run_scope(model_name, args.batch_size, args.overwrite)


if __name__ == "__main__":
    main()

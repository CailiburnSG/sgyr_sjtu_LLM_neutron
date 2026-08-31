#!/usr/bin/env python3
"""Offline retrieval benchmark for expert-authored technical-detail queries.

The benchmark reuses the checked-in 64-document corpus and saved corpus embeddings
from the independent embedding comparison. It compares four existing short baseline
queries with six bilingual, expert-authored technical-detail queries informed by
documented signal observations. No LLM is called.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "md"
EMBEDDINGS = ROOT / "evidence" / "embedding_benchmark"
QUERY_SET = ROOT / "evidence" / "rag_results" / "query_formulation_sensitivity" / "technical_detail_query_pilot" / "query_set.json"
OUTPUT = ROOT / "evidence" / "rag_results" / "query_formulation_sensitivity" / "technical_detail_query_pilot" / "results"
CHUNK_WORDS, OVERLAP_WORDS, TOP_K, TRIALS, SEED = 240, 24, 10, 10, 20260831
MODELS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
)


def documents() -> list[dict[str, str]]:
    records = []
    for path in sorted(CORPUS.rglob("*.md")):
        relative = path.relative_to(CORPUS)
        records.append({"doc_id": str(relative), "category": relative.parts[0]})
    core_count = sum(record["category"] == "IAEA" for record in records)
    if len(records) != 64 or core_count != 13:
        raise RuntimeError(f"Expected 64 documents / 13 IAEA core documents; got {len(records)} / {core_count}")
    return records


def chunk_doc_ids() -> list[str]:
    """Reproduce the exact chunk order used by run_embedding_benchmark.py."""
    import re

    ids = []
    stride = CHUNK_WORDS - OVERLAP_WORDS
    for path in sorted(CORPUS.rglob("*.md")):
        words = re.findall(r"\S+", path.read_text(encoding="utf-8", errors="ignore"))
        count = sum(1 for i in range(0, len(words), stride) if len(words[i:i + CHUNK_WORDS]) >= 24)
        ids.extend([str(path.relative_to(CORPUS))] * count)
    return ids


def encode_queries(model: SentenceTransformer, model_name: str, queries: list[str]) -> np.ndarray:
    if "multilingual-e5" in model_name:
        queries = ["query: " + query for query in queries]
    return model.encode(queries, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True)


def run_model(model_name: str, overwrite: bool) -> None:
    slug = model_name.replace("/", "__")
    out_dir = OUTPUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    detail_path = out_dir / "scope_detail.csv"
    if detail_path.exists() and not overwrite:
        print(f"Skip existing result: {detail_path}")
        return

    query_spec = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    queries = query_spec["baseline_queries"] + query_spec["technical_detail_queries"]
    records = documents()
    chunk_ids = chunk_doc_ids()
    vectors = np.load(EMBEDDINGS / slug / "chunk_embeddings.npy")
    if len(vectors) != len(chunk_ids):
        raise RuntimeError(f"Embedding/chunk mismatch: {len(vectors)} != {len(chunk_ids)}")

    category_by_doc = {record["doc_id"]: record["category"] for record in records}
    by_doc: dict[str, list[int]] = {record["doc_id"]: [] for record in records}
    for index, doc_id in enumerate(chunk_ids):
        by_doc[doc_id].append(index)
    core_docs = [record["doc_id"] for record in records if record["category"] == "IAEA"]
    other_docs = [record["doc_id"] for record in records if record["category"] != "IAEA"]
    core_indices = [index for doc_id in core_docs for index in by_doc[doc_id]]

    print(f"Loading {model_name} to encode {len(queries)} queries")
    model = SentenceTransformer(model_name, device="cpu")
    qvectors = encode_queries(model, model_name, [entry["query"] for entry in queries])
    counts = [0] + list(range(5, len(other_docs) + 1, 5))
    if counts[-1] != len(other_docs):
        counts.append(len(other_docs))
    rows = []
    for query, qvec in zip(queries, qvectors, strict=True):
        for extra in counts:
            for trial in range(1 if extra == 0 else TRIALS):
                rng = random.Random(f"{SEED}|{model_name}|{query['query_id']}|{extra}|{trial}")
                selected = other_docs if extra == len(other_docs) else rng.sample(other_docs, extra)
                pool = core_indices + [idx for doc_id in selected for idx in by_doc[doc_id]]
                scores = vectors[pool] @ qvec
                top_local = np.argpartition(scores, -TOP_K)[-TOP_K:]
                top_local = top_local[np.argsort(scores[top_local])[::-1]]
                top_indices = [pool[int(index)] for index in top_local]
                top_categories = [category_by_doc[chunk_ids[index]] for index in top_indices]
                rows.append({
                    "model": model_name, "query_id": query["query_id"], "query": query["query"],
                    "family": query["family"], "language": query["language"], "extra_docs": extra,
                    "trial": trial, "pool_docs": len(core_docs) + extra,
                    "top1_score": float(scores[top_local[0]]), "top10_mean_score": float(scores[top_local].mean()),
                    "iaea_priority_top10": sum(category == "IAEA" for category in top_categories) / TOP_K,
                    "first_iaea_rank": next((rank for rank, category in enumerate(top_categories, 1)
                                             if category == "IAEA"), TOP_K + 1),
                })
    detail = pd.DataFrame(rows)
    group_cols = ["model", "query_id", "query", "family", "language", "extra_docs"]
    summary = detail.groupby(group_cols, as_index=False).agg(
        n_trials=("trial", "count"), pool_docs=("pool_docs", "mean"),
        top1_score_mean=("top1_score", "mean"), top1_score_std=("top1_score", "std"),
        top10_mean_score_mean=("top10_mean_score", "mean"), top10_mean_score_std=("top10_mean_score", "std"),
        iaea_priority_top10_mean=("iaea_priority_top10", "mean"),
        iaea_priority_top10_std=("iaea_priority_top10", "std"),
        first_iaea_rank_mean=("first_iaea_rank", "mean"),
        first_iaea_rank_std=("first_iaea_rank", "std"),
    )
    detail.to_csv(detail_path, index=False)
    summary.to_csv(out_dir / "scope_summary.csv", index=False)
    (out_dir / "metadata.json").write_text(json.dumps({
        "model": model_name, "documents": len(records), "core_documents": len(core_docs),
        "chunks": len(chunk_ids), "chunk_words": CHUNK_WORDS, "overlap_words": OVERLAP_WORDS,
        "top_k": TOP_K, "trials": TRIALS, "seed": SEED, "query_set": str(QUERY_SET.relative_to(ROOT)),
        "generation_mode": query_spec["generation_mode"],
    }, indent=2), encoding="utf-8")
    print(f"Wrote {detail_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", choices=MODELS, help="Run one model; defaults to both")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for model_name in args.model or MODELS:
        run_model(model_name, args.overwrite)


if __name__ == "__main__":
    main()

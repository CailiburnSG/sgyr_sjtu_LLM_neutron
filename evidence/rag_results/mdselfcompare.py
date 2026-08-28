#!/usr/bin/env python3
"""
MD 语料范围外推实验：固定向量索引，逐步扩大检索池，用相似度分数评价（对齐 ragtest2）。

流程:
  1. 基线: 仅 IAEA 13 篇文档的 chunks
  2. 在基线上随机附加 5/10/15/20/25 篇非 IAEA 文档（多次抽样取平均）
  3. 检索词: 中子 / 中子测量电流 / neutron / neutron measurement current
  4. 指标: top1/top3/top10 相似度、IAEA 在 top-k 中的占比与首位 IAEA 排名

示例:
  python mdselfcompare.py                    # 交互输入 chunk_size / chunk_overlap
  python mdselfcompare.py 800 80             # 命令行简写
  python mdselfcompare.py --chunk-size 1200 --chunk-overlap 120
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

import matplotlib.pyplot as plt

plt.rcParams["axes.unicode_minus"] = False

SCRIPT_DIR = Path(__file__).resolve().parent
RAGTEST_ROOT = SCRIPT_DIR.parent
RAG_INDEX = RAGTEST_ROOT / "rag_index"

# =============================================================================
# 实验参数（可直接改这里）
# =============================================================================
DEFAULT_TRIALS = 10  # 每个附加规模的随机重复次数（IAEA_only 固定 1 次）
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 80
TOP_K = 10
EXTRA_DOC_STEP = 5
EXTRA_DOC_MAX = 55  # 软上限；实际不超过非 IAEA 文档总数

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")

IAEA_CATEGORY = "IAEA"


def build_extra_doc_counts(n_other: int, *, step: int = EXTRA_DOC_STEP, max_extra: int = EXTRA_DOC_MAX) -> tuple[int, ...]:
    """附加规模: step, 2*step, … 直至 min(max_extra, n_other)；若上限不在步进点上则补最后一档。"""
    if n_other <= 0:
        return ()
    cap = min(max_extra, n_other)
    counts = list(range(step, cap + 1, step))
    if cap not in counts:
        counts.append(cap)
    return tuple(counts)

QUERIES: list[tuple[str, str, str]] = [
    ("中子", "neutron", "core_term"),
    ("中子测量电流", "neutron measurement current", "phrase"),
]


def plot_legend_label(query_tag: str, lang: str) -> str:
    """图例用英文标签，避免 matplotlib 无法显示中文。"""
    for _zh, en, tag in QUERIES:
        if tag == query_tag:
            role = "chinese" if lang == "zh" else "english"
            return f"{en}({role})"
    return f"{query_tag}({lang})"


def storage_dir_for(chunk_size: int, chunk_overlap: int) -> Path:
    return RAG_INDEX / f"storage_md_c{chunk_size}_o{chunk_overlap}"


def out_dir_for(chunk_size: int, chunk_overlap: int) -> Path:
    """输出目录: rag_compare/output_mdselfcompare_o{overlap}_c{chunk_size}/"""
    return SCRIPT_DIR / f"output_mdselfcompare_o{chunk_overlap}_c{chunk_size}"


def list_built_storages() -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    if not RAG_INDEX.is_dir():
        return found
    for p in RAG_INDEX.iterdir():
        m = re.fullmatch(r"storage_md_c(\d+)_o(\d+)", p.name)
        if m and p.is_dir() and (p / "docstore.json").is_file():
            found.append((int(m.group(1)), int(m.group(2))))
    return sorted(found)


def prompt_chunk_params() -> tuple[int, int]:
    print("=" * 60)
    print("  MD 外推实验 — 选择分块索引（交互）")
    print("=" * 60)
    built = list_built_storages()
    if built:
        print("  已建好的 MD 索引（chunk_size / chunk_overlap）:")
        for cs, co in built:
            print(f"    {cs} / {co}  →  storage_md_c{cs}_o{co}")
    else:
        print("  （rag_index 下暂未发现 storage_md_c*_o*）")

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

    print(f"\n  【预览】索引目录: rag_index/storage_md_c{chunk_size}_o{chunk_overlap}")
    return chunk_size, chunk_overlap


def resolve_chunk_params(
    chunk_args: list[int],
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> tuple[int, int]:
    if chunk_args:
        if len(chunk_args) != 2:
            raise SystemExit("位置参数须为两个整数: chunk_size chunk_overlap（例如 800 80）")
        return chunk_args[0], chunk_args[1]
    if chunk_size is not None or chunk_overlap is not None:
        if chunk_size is None or chunk_overlap is None:
            raise SystemExit("--chunk-size 与 --chunk-overlap 需同时指定")
        return chunk_size, chunk_overlap
    return prompt_chunk_params()


def resolve_storage_dir(chunk_size: int, chunk_overlap: int) -> Path:
    storage_dir = storage_dir_for(chunk_size, chunk_overlap)
    if not storage_dir.is_dir():
        print(
            f"❌ 未找到索引目录: {storage_dir}\n"
            f"   请先运行: python ../ragtools/md2embedding.py "
            f"--chunk-size {chunk_size} --chunk-overlap {chunk_overlap}",
            file=sys.stderr,
        )
        sys.exit(1)
    return storage_dir


@dataclass
class ChunkRecord:
    node_id: str
    doc_id: str
    category: str
    file_name: str
    text: str
    embedding: list[float]


@dataclass
class DocInfo:
    doc_id: str
    category: str
    file_name: str
    node_ids: list[str] = field(default_factory=list)


def _check_ollama() -> None:
    url = f"{OLLAMA_BASE.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            if resp.status != 200:
                raise RuntimeError(f"status {resp.status}")
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"❌ Ollama 不可用 ({url}): {exc}", file=sys.stderr)
        sys.exit(1)


def _load_embedder():
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE,
        embed_batch_size=1,
    )


def _parse_node(wrap: dict) -> tuple[str, dict, str]:
    data = wrap.get("__data__", wrap)
    meta = data.get("metadata", {}) or {}
    text = data.get("text", "") or ""
    return data.get("id_", ""), meta, text


def load_index_corpus(storage_dir: Path) -> tuple[list[ChunkRecord], dict[str, DocInfo], object | None, dict[str, list[int]]]:
    docstore_path = storage_dir / "docstore.json"
    vector_path = storage_dir / "default__vector_store.json"
    if not docstore_path.is_file() or not vector_path.is_file():
        print(f"❌ 索引不完整: {storage_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"▶ 加载 docstore / vector store …")
    t0 = time.time()
    docstore = json.loads(docstore_path.read_text(encoding="utf-8"))
    vector_store = json.loads(vector_path.read_text(encoding="utf-8"))
    embedding_dict: dict[str, list[float]] = vector_store.get("embedding_dict", {})

    nodes_raw = docstore.get("docstore/data", {})
    docs: dict[str, DocInfo] = {}
    chunks: list[ChunkRecord] = []
    doc_to_indices: dict[str, list[int]] = defaultdict(list)
    missing_emb = 0

    for node_id, wrap in nodes_raw.items():
        nid, meta, text = _parse_node(wrap)
        if not node_id:
            node_id = nid
        emb = embedding_dict.get(node_id)
        if emb is None:
            missing_emb += 1
            continue

        doc_id = meta.get("doc_id") or "unknown"
        category = meta.get("category") or ""
        file_name = meta.get("file_name") or ""

        if doc_id not in docs:
            docs[doc_id] = DocInfo(
                doc_id=doc_id,
                category=category,
                file_name=file_name,
            )
        docs[doc_id].node_ids.append(node_id)

        idx = len(chunks)
        doc_to_indices[doc_id].append(idx)
        chunks.append(
            ChunkRecord(
                node_id=node_id,
                doc_id=doc_id,
                category=category,
                file_name=file_name,
                text=text,
                embedding=emb,
            )
        )

    embed_matrix = None
    if np is not None and chunks:
        mat = np.asarray([c.embedding for c in chunks], dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        embed_matrix = mat / np.clip(norms, 1e-9, None)

    print(
        f"  ✅ {len(chunks)} chunks / {len(docs)} docs"
        f"（跳过无向量 {missing_emb} 条，耗时 {time.time() - t0:.1f}s）"
    )
    return chunks, docs, embed_matrix, doc_to_indices


def split_iaea_docs(docs: dict[str, DocInfo]) -> tuple[list[str], list[str]]:
    iaea = sorted(did for did, d in docs.items() if d.category == IAEA_CATEGORY)
    other = sorted(did for did, d in docs.items() if d.category != IAEA_CATEGORY)
    if not iaea:
        print(f"❌ 未找到 category={IAEA_CATEGORY!r} 的文档", file=sys.stderr)
        sys.exit(1)
    print(f"  IAEA {len(iaea)} 篇，其余 {len(other)} 篇")
    return iaea, other


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


def embed_queries(embedder, queries: list[str]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for q in queries:
        print(f"  ▶ embedding query: {q!r}")
        vec = embedder.get_query_embedding(q)
        out[q] = _normalize(vec)
    return out


def _cosine_batch(query: list[float], matrix: list[list[float]]) -> list[float]:
    if np is not None:
        q = np.asarray(query, dtype=np.float32)
        m = np.asarray(matrix, dtype=np.float32)
        return (m @ q).tolist()
    return [sum(a * b for a, b in zip(row, query)) for row in matrix]


def retrieve_scored(
    query_vec: list[float],
    pool: list[ChunkRecord],
    top_k: int,
    *,
    pool_indices: list[int] | None = None,
    embed_matrix: object | None = None,
) -> list[tuple[ChunkRecord, float]]:
    if not pool:
        return []
    if np is not None and embed_matrix is not None and pool_indices is not None:
        q = np.asarray(query_vec, dtype=np.float32)
        scores = embed_matrix[pool_indices] @ q
        order = np.argsort(-scores)[:top_k]
        return [(pool[i], float(scores[i])) for i in order]
    scores = _cosine_batch(query_vec, [c.embedding for c in pool])
    ranked = sorted(zip(pool, scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def compute_metrics(
    hits: list[tuple[ChunkRecord, float]],
    *,
    top_k: int,
) -> dict[str, float | int]:
    scores = [s for _, s in hits]
    iaea_ranks = [
        i + 1 for i, (c, _) in enumerate(hits) if c.category == IAEA_CATEGORY
    ]

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "top1_score": scores[0] if scores else 0.0,
        "top3_mean_score": _mean(scores[:3]),
        "top10_mean_score": _mean(scores[: min(10, len(scores))]),
        "max_score": max(scores) if scores else 0.0,
        "iaea_count_topk": sum(1 for c, _ in hits if c.category == IAEA_CATEGORY),
        "iaea_purity_topk": (
            sum(1 for c, _ in hits if c.category == IAEA_CATEGORY) / len(hits)
            if hits
            else 0.0
        ),
        "first_iaea_rank": iaea_ranks[0] if iaea_ranks else 0,
        "retrieved_k": len(hits),
        "top_k": top_k,
    }


def build_pool(
    chunks: list[ChunkRecord],
    doc_to_indices: dict[str, list[int]],
    allowed_doc_ids: set[str],
) -> tuple[list[ChunkRecord], list[int]]:
    pool: list[ChunkRecord] = []
    indices: list[int] = []
    for doc_id in allowed_doc_ids:
        for idx in doc_to_indices.get(doc_id, []):
            pool.append(chunks[idx])
            indices.append(idx)
    return pool, indices


def run_experiment(
    *,
    storage_dir: Path,
    out_dir: Path,
    trials: int,
    top_k: int,
    seed: int,
) -> None:
    _check_ollama()
    chunks, docs, embed_matrix, doc_to_indices = load_index_corpus(storage_dir)
    iaea_doc_ids, other_doc_ids = split_iaea_docs(docs)
    extra_doc_counts = build_extra_doc_counts(len(other_doc_ids))
    print(f"  附加规模  : IAEA×{len(iaea_doc_ids)} + {list(extra_doc_counts)}（非 IAEA 共 {len(other_doc_ids)} 篇）")

    query_texts = [zh for zh, _, _ in QUERIES] + [en for _, en, _ in QUERIES]
    embedder = _load_embedder()
    query_vecs = embed_queries(embedder, query_texts)

    scope_levels: list[tuple[str, int, int | None]] = [("IAEA_only", 0, None)]
    for n in extra_doc_counts:
        scope_levels.append((f"IAEA_plus_{n}", n, n))

    detail_rows: list[dict] = []
    rng_master = random.Random(seed)

    for scope_name, extra_n, sample_n in scope_levels:
        n_trials = 1 if sample_n is None else trials
        for trial in range(n_trials):
            if sample_n is None:
                allowed = set(iaea_doc_ids)
                extra_docs: list[str] = []
            else:
                trial_rng = random.Random(rng_master.randint(0, 2**31 - 1))
                k = min(sample_n, len(other_doc_ids))
                extra_docs = trial_rng.sample(other_doc_ids, k)
                allowed = set(iaea_doc_ids) | set(extra_docs)

            pool, pool_indices = build_pool(chunks, doc_to_indices, allowed)
            pool_doc_count = len(allowed)
            pool_chunk_count = len(pool)

            for zh, en, qtag in QUERIES:
                for lang, qtext in (("zh", zh), ("en", en)):
                    hits = retrieve_scored(
                        query_vecs[qtext],
                        pool,
                        top_k,
                        pool_indices=pool_indices,
                        embed_matrix=embed_matrix,
                    )
                    metrics = compute_metrics(hits, top_k=top_k)
                    detail_rows.append(
                        {
                            "scope": scope_name,
                            "extra_docs": extra_n,
                            "trial": trial,
                            "query_tag": qtag,
                            "lang": lang,
                            "query": qtext,
                            "pool_docs": pool_doc_count,
                            "pool_chunks": pool_chunk_count,
                            "iaea_docs": len(iaea_doc_ids),
                            "extra_sampled": len(extra_docs),
                            **metrics,
                        }
                    )

            print(
                f"  ✓ {scope_name} trial={trial} "
                f"pool={pool_doc_count}docs/{pool_chunk_count}chunks"
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_path = out_dir / f"scope_detail_{ts}.csv"
    summary_path = out_dir / f"scope_summary_{ts}.csv"
    plot_score_path = out_dir / f"scope_plot_score_{ts}.png"
    plot_purity_path = out_dir / f"scope_plot_purity_{ts}.png"
    table_score_path = out_dir / f"scope_table_score_{ts}.csv"
    table_purity_path = out_dir / f"scope_table_purity_{ts}.csv"

    _write_csv(detail_path, detail_rows)
    summary_rows = _aggregate_summary(detail_rows)
    _write_csv(summary_path, summary_rows)

    _write_metric_matrix_csv(
        table_score_path,
        summary_rows,
        metric="top10_mean_score",
        value_fmt=".3f",
    )
    _write_metric_matrix_csv(
        table_purity_path,
        summary_rows,
        metric="iaea_purity_topk",
        value_fmt=".2f",
    )
    _plot_results(
        summary_rows,
        plot_score_path,
        metric="top10_mean_score",
        ylabel="Top-10 Average Vector Similarity",
        fix_ymin_zero=False,
    )
    _plot_results(
        summary_rows,
        plot_purity_path,
        metric="iaea_purity_topk",
        ylabel="Proportion of IAEA in Top-k",
        fix_ymin_zero=True,
        ymax_cap=1.0,
    )

    print("\n" + "=" * 60)
    print("  实验完成")
    print(f"  明细 CSV : {detail_path}")
    print(f"  汇总 CSV : {summary_path}")
    print(f"  相似度图 : {plot_score_path}")
    print(f"  相似度表 : {table_score_path}")
    print(f"  纯度图   : {plot_purity_path}")
    print(f"  纯度表   : {table_purity_path}")
    print("=" * 60)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _aggregate_summary(detail_rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in detail_rows:
        key = (
            row["scope"],
            row["extra_docs"],
            row["query_tag"],
            row["lang"],
            row["query"],
        )
        groups[key].append(row)

    summary: list[dict] = []
    metric_keys = [
        "top1_score",
        "top3_mean_score",
        "top10_mean_score",
        "max_score",
        "iaea_purity_topk",
        "first_iaea_rank",
    ]

    for key, rows in sorted(groups.items()):
        scope, extra, qtag, lang, query = key
        item: dict = {
            "scope": scope,
            "extra_docs": extra,
            "query_tag": qtag,
            "lang": lang,
            "query": query,
            "n_trials": len(rows),
            "pool_docs_mean": sum(r["pool_docs"] for r in rows) / len(rows),
            "pool_chunks_mean": sum(r["pool_chunks"] for r in rows) / len(rows),
        }
        for mk in metric_keys:
            vals = [float(r[mk]) for r in rows]
            item[f"{mk}_mean"] = sum(vals) / len(vals)
            if len(vals) > 1:
                mean = item[f"{mk}_mean"]
                var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
                item[f"{mk}_std"] = math.sqrt(var)
            else:
                item[f"{mk}_std"] = 0.0
        summary.append(item)
    return summary


def _summary_to_series(
    summary_rows: list[dict],
    metric: str,
) -> dict[str, list[tuple[int, float, float]]]:
    mean_key = f"{metric}_mean"
    std_key = f"{metric}_std"
    series: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for row in summary_rows:
        label = plot_legend_label(row["query_tag"], row["lang"])
        series[label].append(
            (
                int(row["extra_docs"]),
                float(row[mean_key]),
                float(row.get(std_key) or 0.0),
            )
        )
    return series


def _write_metric_matrix_csv(
    path: Path,
    summary_rows: list[dict],
    *,
    metric: str,
    value_fmt: str,
) -> None:
    """透视表 CSV：行=query 曲线，列=附加文档数，单元格=指标均值。"""
    series = _summary_to_series(summary_rows, metric)
    if not series:
        return
    x_cols = sorted({int(p[0]) for pts in series.values() for p in pts})
    col_headers = [f"+{x}" if x else "0_IAEA_only" for x in x_cols]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", *col_headers])
        for label in sorted(series.keys()):
            by_x = {int(p[0]): p[1] for p in series[label]}
            w.writerow([label, *[format(by_x[x], value_fmt) for x in x_cols]])


def _plot_results(
    summary_rows: list[dict],
    path: Path,
    *,
    metric: str,
    ylabel: str,
    fix_ymin_zero: bool = False,
    ymax_cap: float | None = None,
) -> None:
    series = _summary_to_series(summary_rows, metric)

    fig, ax = plt.subplots(figsize=(10, 6))
    y_lows: list[float] = []
    y_peaks: list[float] = []
    for label, pts in sorted(series.items()):
        pts.sort(key=lambda x: x[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if fix_ymin_zero:
            # purity：误差棒不穿过 0
            yerr_lo = [min(p[2], p[1]) for p in pts]
        else:
            # score：完整误差棒，Y 轴随数据自动缩放
            yerr_lo = [p[2] for p in pts]
        yerr_hi = [p[2] for p in pts]
        y_lows.extend(y - lo for y, lo in zip(ys, yerr_lo))
        y_peaks.extend(y + hi for y, hi in zip(ys, yerr_hi))
        ax.errorbar(
            xs, ys, yerr=[yerr_lo, yerr_hi], marker="o", capsize=3, label=label
        )

    ax.set_xlabel("Number of additional non-IAEA documents (0 = IAEA-only, 13 documents)")
    ax.set_ylabel(ylabel)
    ax.set_title("MD Corpus Extrapolation: IAEA Baseline + Random Library Expansion (Vector Retrieval)")
    ax.set_xticks(sorted({int(r["extra_docs"]) for r in summary_rows}))

    y_min = min(y_lows) if y_lows else 0.0
    y_max = max(y_peaks) if y_peaks else 0.1
    span = max(y_max - y_min, 1e-6)
    pad = span * 0.08
    y_bottom = 0.0 if fix_ymin_zero else y_min - pad
    y_top = y_max + pad
    if ymax_cap is not None:
        y_top = min(y_top, ymax_cap)
    if fix_ymin_zero:
        y_bottom = 0.0
    ax.set_ylim(y_bottom, y_top)

    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IAEA 基线 + 随机扩库的 MD 向量检索外推实验",
    )
    parser.add_argument(
        "chunk_args",
        nargs="*",
        type=int,
        metavar="N",
        help="简写: chunk_size chunk_overlap（如 800 80）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=f"分块长度；不指定则进入交互（默认 {DEFAULT_CHUNK_SIZE}）",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help=f"块重叠；不指定则进入交互（默认 {DEFAULT_CHUNK_OVERLAP}）",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录（默认 output_mdselfcompare_o{overlap}_c{chunk_size}）",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help=f"每个附加规模的随机试验次数（默认 {DEFAULT_TRIALS}）",
    )
    parser.add_argument("--top-k", type=int, default=TOP_K, help="检索 top-k")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    try:
        chunk_size, chunk_overlap = resolve_chunk_params(
            args.chunk_args,
            args.chunk_size,
            args.chunk_overlap,
        )
    except SystemExit as exc:
        parser.error(str(exc))

    storage_dir = resolve_storage_dir(chunk_size, chunk_overlap)
    out_dir = args.out_dir.resolve() if args.out_dir else out_dir_for(chunk_size, chunk_overlap)

    if np is None:
        print("⚠️  未安装 numpy，将使用纯 Python 计算（较慢）", file=sys.stderr)

    print("=" * 60)
    print("  MD 语料范围外推实验（向量相似度评价）")
    print("=" * 60)
    print(f"  chunk     : {chunk_size} / {chunk_overlap}")
    print(f"  storage   : {storage_dir}")
    print(f"  out_dir   : {out_dir}")
    print(f"  queries   : {[q for q, _, _ in QUERIES]} + EN")
    print(f"  附加步长  : 每 {EXTRA_DOC_STEP} 篇，上限 {EXTRA_DOC_MAX}（或余下非 IAEA 总数）")
    print(f"  trials    : {args.trials}（IAEA_only 仅 1 次）")
    print(f"  top_k     : {args.top_k}")

    run_experiment(
        storage_dir=storage_dir.resolve(),
        out_dir=out_dir,
        trials=args.trials,
        top_k=args.top_k,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

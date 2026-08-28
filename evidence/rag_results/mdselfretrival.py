#!/usr/bin/env python3
"""
MD 自检索评测：与 mdselfcompare 共用 storage_md_c{size}_o{overlap} 与 IAEA 扩库协议。

实验内容:
  1. 扩库下的自检索衰减 — 随机附加非 IAEA 文档，Recall@K / MRR 随库规模变化
  2. 分块重叠歧义 — strict（同 node_id）vs relaxed（同 doc_id）
  3. 查询构造对比 — 首句 / 标题 / 随机窗口 / 术语句（均在 IAEA-only 池上对比）
  4. 术语句自检索 — 含 domain_term 模式，抽取含领域术语的句子作 query

示例:
  python mdselfretrival.py 800 80
  python mdselfretrival.py --chunk-size 1200 --chunk-overlap 120 --samples 60 --trials 50
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from mdselfcompare import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    EXTRA_DOC_MAX,
    EXTRA_DOC_STEP,
    ChunkRecord,
    _check_ollama,
    _load_embedder,
    _normalize,
    build_extra_doc_counts,
    build_pool,
    load_index_corpus,
    prompt_chunk_params,
    resolve_chunk_params,
    resolve_storage_dir,
    retrieve_scored,
    split_iaea_docs,
)

plt.rcParams["axes.unicode_minus"] = False

SCRIPT_DIR = Path(__file__).resolve().parent

# =============================================================================
# 实验参数（可直接改这里；重复次数放最前）
# =============================================================================
DEFAULT_TRIALS = 10  # 每个附加规模的随机重复次数（IAEA_only 固定 1 次）
DEFAULT_SAMPLES = 80  # IAEA 探针 chunk 数量
TOP_K_EVAL = 10  # 检索 top-k（与 mdselfcompare 的 TOP_K 默认一致）
# 误差棒：sem = 标准误（先对探针/trial 求均值，再对 trial 求 SEM，适合画曲线）
ERROR_BAR_STYLE = "sem"

RECALL_KS = (1, 5, 10)
DECAY_QUERY_MODE = "first_sentence"
QUERY_MODES = (
    "first_sentence",
    "title",
    "random_window",
    "domain_term",
)

DOMAIN_TERM_RE = re.compile(
    r"\b("
    r"neutron|reactor|detector|sensor|measurement|instrumentation|"
    r"calibration|dosimetry|flux|fission|bwr|pwr|hfir|"
    r"noise|surveillance|monitoring|irradiation"
    r")\b",
    re.IGNORECASE,
)
RANDOM_WINDOW_WORDS = 25
MIN_QUERY_CHARS = 12


def _rng_seed(*parts: object) -> int:
    """将 seed 分量压成 int（Python 3.12 的 Random 不接受 tuple）。"""
    blob = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.md5(blob).hexdigest()[:8], 16)


@dataclass
class Probe:
    node_id: str
    doc_id: str
    file_name: str
    text: str


def out_dir_for(chunk_size: int, chunk_overlap: int) -> Path:
    return SCRIPT_DIR / f"output_mdselfretrival_o{chunk_overlap}_c{chunk_size}"


def _first_sentence(text: str, *, max_chars: int = 280) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    sent = parts[0].strip() if parts else text
    if len(sent) < MIN_QUERY_CHARS and len(parts) > 1:
        sent = " ".join(parts[:2]).strip()
    return sent[:max_chars]


def _title_from_filename(file_name: str) -> str:
    stem = Path(file_name).stem
    return re.sub(r"[_\-]+", " ", stem).strip()


def _random_window(text: str, rng: random.Random, *, n_words: int = RANDOM_WINDOW_WORDS) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/]*", text)
    if len(words) <= n_words:
        return " ".join(words)
    start = rng.randint(0, len(words) - n_words)
    return " ".join(words[start : start + n_words])


def _domain_term_sentence(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return None
    parts = re.split(r"(?<=[.!?])\s+", text)
    for sent in parts:
        s = sent.strip()
        if len(s) >= MIN_QUERY_CHARS and DOMAIN_TERM_RE.search(s):
            return s[:280]
    if DOMAIN_TERM_RE.search(text):
        return text[:280]
    return None


def build_query_text(probe: Probe, mode: str, rng: random.Random) -> str | None:
    if mode == "first_sentence":
        q = _first_sentence(probe.text)
        return q if len(q) >= MIN_QUERY_CHARS else probe.text[:280]
    if mode == "title":
        q = _title_from_filename(probe.file_name)
        return q if q else None
    if mode == "random_window":
        q = _random_window(probe.text, rng)
        return q if len(q) >= MIN_QUERY_CHARS else None
    if mode == "domain_term":
        return _domain_term_sentence(probe.text)
    raise ValueError(f"unknown query mode: {mode}")


def sample_iaea_probes(
    chunks: list[ChunkRecord],
    doc_to_indices: dict[str, list[int]],
    iaea_doc_ids: list[str],
    n: int,
    rng: random.Random,
) -> list[Probe]:
    iaea_indices: list[int] = []
    for doc_id in iaea_doc_ids:
        iaea_indices.extend(doc_to_indices.get(doc_id, []))
    if not iaea_indices:
        print("❌ IAEA 文档下无 chunk", file=sys.stderr)
        sys.exit(1)
    k = min(n, len(iaea_indices))
    picked = rng.sample(iaea_indices, k)
    probes: list[Probe] = []
    for idx in picked:
        c = chunks[idx]
        probes.append(
            Probe(
                node_id=c.node_id,
                doc_id=c.doc_id,
                file_name=c.file_name,
                text=c.text,
            )
        )
    return probes


def embed_texts(embedder, texts: list[str]) -> list[list[float]]:
    vecs: list[list[float]] = []
    total = len(texts)
    for i, text in enumerate(texts, 1):
        if total >= 20 and (i == 1 or i % 20 == 0 or i == total):
            print(f"    ▶ embedding queries {i}/{total}")
        vecs.append(_normalize(embedder.get_query_embedding(text)))
    return vecs


def build_query_cache(
    embedder,
    probes: list[Probe],
    modes: tuple[str, ...],
    seed: int,
) -> tuple[dict[tuple[str, str], list[float]], dict[tuple[str, str], str], int]:
    """返回 (node_id, mode) -> vec / text；跳过 domain_term 无术语句的 probe。"""
    cache_vec: dict[tuple[str, str], list[float]] = {}
    cache_text: dict[tuple[str, str], str] = {}
    skipped_domain = 0
    items: list[tuple[str, str, str]] = []

    for probe in probes:
        for mode in modes:
            rng = random.Random(_rng_seed(seed, probe.node_id, mode))
            qtext = build_query_text(probe, mode, rng)
            if not qtext:
                if mode == "domain_term":
                    skipped_domain += 1
                continue
            items.append((probe.node_id, mode, qtext))

    texts = [t for _, _, t in items]
    vecs = embed_texts(embedder, texts)
    for (nid, mode, qtext), vec in zip(items, vecs):
        cache_vec[(nid, mode)] = vec
        cache_text[(nid, mode)] = qtext
    return cache_vec, cache_text, skipped_domain


def _is_relevant(hit: ChunkRecord, probe: Probe, relevance: str) -> bool:
    if relevance == "strict":
        return hit.node_id == probe.node_id
    if relevance == "relaxed_doc":
        return hit.doc_id == probe.doc_id
    raise ValueError(relevance)


def metrics_for_hits(
    probe: Probe,
    hits: list[tuple[ChunkRecord, float]],
    relevance: str,
) -> dict[str, float]:
    ranks = [
        i + 1
        for i, (c, _) in enumerate(hits)
        if _is_relevant(c, probe, relevance)
    ]
    first_rank = ranks[0] if ranks else 0
    out: dict[str, float] = {
        "mrr": (1.0 / first_rank) if first_rank else 0.0,
        "first_relevant_rank": float(first_rank),
    }
    for k in RECALL_KS:
        top = hits[:k]
        hit = any(_is_relevant(c, probe, relevance) for c, _ in top)
        out[f"recall_at_{k}"] = 1.0 if hit else 0.0
    return out


def _mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    mean = sum(vals) / len(vals)
    if len(vals) < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return mean, math.sqrt(var)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _aggregate_metric_rows(
    detail_rows: list[dict],
    group_keys: tuple[str, ...],
    metric_keys: tuple[str, ...],
) -> list[dict]:
    """逐条 0/1 明细直接聚合（保留在 summary 里作参考，误差偏大）。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in detail_rows:
        key = tuple(row[k] for k in group_keys)
        groups[key].append(row)

    summary: list[dict] = []
    for key, rows in sorted(groups.items()):
        item = {k: rows[0][k] for k in group_keys}
        item["n_probes"] = len(rows)
        for mk in metric_keys:
            vals = [float(r[mk]) for r in rows]
            mean, std = _mean_std(vals)
            item[f"{mk}_mean"] = mean
            item[f"{mk}_std"] = std
            item[f"{mk}_sem"] = std / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
        summary.append(item)
    return summary


def _aggregate_decay_for_plot(
    detail_rows: list[dict],
    metric_keys: tuple[str, ...],
) -> list[dict]:
    """
    扩库曲线用：trial 内先对探针平均，再对 trial 求 mean / std / sem。
    避免把 80×100 条 0/1 混在一起导致 std≈0.45 的巨型误差棒。
    """
    decay_rows = [r for r in detail_rows if r.get("experiment") == "corpus_decay"]
    trial_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in decay_rows:
        key = (
            int(row["extra_docs"]),
            int(row["trial"]),
            row["query_mode"],
            row["relevance"],
        )
        trial_groups[key].append(row)

    trial_means: list[dict] = []
    for key, rows in trial_groups.items():
        extra, trial, qmode, rel = key
        item: dict = {
            "experiment": "corpus_decay",
            "extra_docs": extra,
            "trial": trial,
            "query_mode": qmode,
            "relevance": rel,
            "n_probes": len(rows),
        }
        for mk in metric_keys:
            vals = [float(r[mk]) for r in rows]
            item[mk] = sum(vals) / len(vals)
        trial_means.append(item)

    curve_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in trial_means:
        key = (int(row["extra_docs"]), row["query_mode"], row["relevance"])
        curve_groups[key].append(row)

    summary: list[dict] = []
    for key, rows in sorted(curve_groups.items()):
        extra, qmode, rel = key
        item: dict = {
            "experiment": "corpus_decay",
            "extra_docs": extra,
            "query_mode": qmode,
            "relevance": rel,
            "n_trials": len(rows),
            "n_probes_per_trial": int(rows[0]["n_probes"]),
        }
        for mk in metric_keys:
            vals = [float(r[mk]) for r in rows]
            mean, std = _mean_std(vals)
            item[f"{mk}_mean"] = mean
            item[f"{mk}_std"] = std
            item[f"{mk}_sem"] = std / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
        summary.append(item)
    return summary


def _aggregate_query_for_plot(
    detail_rows: list[dict],
    metric_keys: tuple[str, ...],
) -> list[dict]:
    """查询构造柱状图：单次 IAEA-only，对探针求 mean，误差用 SEM(探针)。"""
    query_rows = [r for r in detail_rows if r.get("experiment") == "query_construction"]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in query_rows:
        key = (row["query_mode"], row["relevance"])
        groups[key].append(row)

    summary: list[dict] = []
    for key, rows in sorted(groups.items()):
        qmode, rel = key
        item: dict = {
            "experiment": "query_construction",
            "extra_docs": 0,
            "query_mode": qmode,
            "relevance": rel,
            "n_probes": len(rows),
            "n_trials": 1,
        }
        for mk in metric_keys:
            vals = [float(r[mk]) for r in rows]
            mean, std = _mean_std(vals)
            item[f"{mk}_mean"] = mean
            item[f"{mk}_std"] = std
            item[f"{mk}_sem"] = std / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
        summary.append(item)
    return summary


def _error_bar_delta(row: dict, metric: str) -> float:
    if ERROR_BAR_STYLE == "sem":
        return float(row.get(f"{metric}_sem") or 0.0)
    return float(row.get(f"{metric}_std") or 0.0)


def _plot_decay(
    summary_rows: list[dict],
    path: Path,
    *,
    metric: str,
    title: str,
) -> None:
    series: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    mean_key = f"{metric}_mean"
    for row in summary_rows:
        if row.get("experiment") != "corpus_decay":
            continue
        label = row["relevance"]
        series[label].append(
            (
                int(row["extra_docs"]),
                float(row[mean_key]),
                _error_bar_delta(row, metric),
            )
        )

    fig, ax = plt.subplots(figsize=(10, 6))
    for label, pts in sorted(series.items()):
        pts.sort(key=lambda x: x[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        yerr_lo = [min(p[2], y) for y, p in zip(ys, pts)]
        yerr_hi = [min(p[2], 1.0 - y) for y, p in zip(ys, pts)]
        ax.errorbar(
            xs, ys, yerr=[yerr_lo, yerr_hi], marker="o", capsize=3, label=label
        )

    ax.set_xlabel("Additional non-IAEA documents (0 = IAEA-only)")
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title(title)
    ax.set_xticks(sorted({int(r["extra_docs"]) for r in summary_rows if r.get("experiment") == "corpus_decay"}))
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_query_modes(
    summary_rows: list[dict],
    path: Path,
    *,
    metric: str,
) -> None:
    rows = [
        r
        for r in summary_rows
        if r.get("experiment") == "query_construction" and int(r.get("extra_docs", -1)) == 0
    ]
    if not rows:
        return

    modes = [m for m in QUERY_MODES if any(r["query_mode"] == m for r in rows)]
    x = list(range(len(modes)))
    width = 0.36
    strict_means = []
    strict_stds = []
    relaxed_means = []
    relaxed_stds = []
    for mode in modes:
        s_row = next(r for r in rows if r["query_mode"] == mode and r["relevance"] == "strict")
        l_row = next(r for r in rows if r["query_mode"] == mode and r["relevance"] == "relaxed_doc")
        strict_means.append(float(s_row[f"{metric}_mean"]))
        strict_stds.append(_error_bar_delta(s_row, metric))
        relaxed_means.append(float(l_row[f"{metric}_mean"]))
        relaxed_stds.append(_error_bar_delta(l_row, metric))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        [i - width / 2 for i in x],
        strict_means,
        width,
        yerr=strict_stds,
        capsize=3,
        label="strict (same chunk)",
    )
    ax.bar(
        [i + width / 2 for i in x],
        relaxed_means,
        width,
        yerr=relaxed_stds,
        capsize=3,
        label="relaxed (same document)",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(modes, rotation=15, ha="right")
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_title("Query Construction Comparison (IAEA-only pool)")
    ax.set_ylim(0.0, 1.05)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _write_decay_table(path: Path, summary_rows: list[dict], metric: str) -> None:
    rows = [r for r in summary_rows if r.get("experiment") == "corpus_decay"]
    if not rows:
        return
    x_cols = sorted({int(r["extra_docs"]) for r in rows})
    rel_modes = sorted({r["relevance"] for r in rows})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["relevance", *[f"+{x}" if x else "0_IAEA_only" for x in x_cols]])
        for rel in rel_modes:
            by_x = {
                int(r["extra_docs"]): float(r[f"{metric}_mean"])
                for r in rows
                if r["relevance"] == rel
            }
            w.writerow([rel, *[f"{by_x.get(x, float('nan')):.4f}" for x in x_cols]])


def _write_query_table(path: Path, summary_rows: list[dict], metric: str) -> None:
    rows = [
        r
        for r in summary_rows
        if r.get("experiment") == "query_construction" and int(r.get("extra_docs", -1)) == 0
    ]
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_mode", "relevance", f"{metric}_mean", f"{metric}_std"])
        for r in sorted(rows, key=lambda x: (x["query_mode"], x["relevance"])):
            w.writerow(
                [
                    r["query_mode"],
                    r["relevance"],
                    f"{float(r[f'{metric}_mean']):.4f}",
                    f"{float(r.get(f'{metric}_std') or 0):.4f}",
                ]
            )


def run_experiment(
    *,
    storage_dir: Path,
    out_dir: Path,
    trials: int,
    top_k: int,
    seed: int,
    n_samples: int,
) -> None:
    _check_ollama()
    chunks, docs, embed_matrix, doc_to_indices = load_index_corpus(storage_dir)
    iaea_doc_ids, other_doc_ids = split_iaea_docs(docs)
    extra_doc_counts = build_extra_doc_counts(len(other_doc_ids))

    rng_master = random.Random(seed)
    probes = sample_iaea_probes(
        chunks, doc_to_indices, iaea_doc_ids, n_samples, rng_master
    )
    print(f"  自检索探针  : {len(probes)} chunks（来自 IAEA {len(iaea_doc_ids)} 篇）")
    print(f"  附加规模    : {list(extra_doc_counts)}（非 IAEA 共 {len(other_doc_ids)} 篇）")

    embedder = _load_embedder()
    print("  ▶ 预计算各 query 构造方式的 embedding …")
    query_cache, query_text_cache, skipped_domain = build_query_cache(
        embedder, probes, QUERY_MODES, seed
    )
    if skipped_domain:
        print(f"  ⚠️  domain_term 跳过 {skipped_domain} 个无术语句的 probe")

    decay_cache = {
        k: v
        for k, v in query_cache.items()
        if k[1] == DECAY_QUERY_MODE
    }
    if not decay_cache:
        print("❌ 无 first_sentence 查询向量", file=sys.stderr)
        sys.exit(1)

    scope_levels: list[tuple[str, int, int | None]] = [("IAEA_only", 0, None)]
    for n in extra_doc_counts:
        scope_levels.append((f"IAEA_plus_{n}", n, n))

    metric_keys = [f"recall_at_{k}" for k in RECALL_KS] + ["mrr"]
    detail_rows: list[dict] = []

    # --- 1 & 2: 扩库衰减 + strict/relaxed 歧义（query=first_sentence）---
    print("\n▶ 实验 A: 扩库自检索衰减（first_sentence, strict vs relaxed_doc）")
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

            for probe in probes:
                key = (probe.node_id, DECAY_QUERY_MODE)
                qvec = decay_cache.get(key)
                if qvec is None:
                    continue
                hits = retrieve_scored(
                    qvec,
                    pool,
                    top_k,
                    pool_indices=pool_indices,
                    embed_matrix=embed_matrix,
                )
                for relevance in ("strict", "relaxed_doc"):
                    m = metrics_for_hits(probe, hits, relevance)
                    detail_rows.append(
                        {
                            "experiment": "corpus_decay",
                            "scope": scope_name,
                            "extra_docs": extra_n,
                            "trial": trial,
                            "query_mode": DECAY_QUERY_MODE,
                            "relevance": relevance,
                            "probe_node_id": probe.node_id,
                            "probe_doc_id": probe.doc_id,
                            "pool_docs": len(allowed),
                            "pool_chunks": len(pool),
                            "query_preview": query_text_cache.get(key, "")[:120],
                            **m,
                        }
                    )

            print(
                f"  ✓ decay {scope_name} trial={trial} "
                f"pool={len(allowed)}docs/{len(pool)}chunks"
            )

    # --- 3 & 4: 查询构造对比 + 术语句（仅 IAEA-only）---
    print("\n▶ 实验 B: 查询构造对比（IAEA-only，含 domain_term）")
    allowed_iaea = set(iaea_doc_ids)
    pool_iaea, pool_indices_iaea = build_pool(chunks, doc_to_indices, allowed_iaea)

    for probe in probes:
        for mode in QUERY_MODES:
            key = (probe.node_id, mode)
            qvec = query_cache.get(key)
            if qvec is None:
                continue
            hits = retrieve_scored(
                qvec,
                pool_iaea,
                top_k,
                pool_indices=pool_indices_iaea,
                embed_matrix=embed_matrix,
            )
            for relevance in ("strict", "relaxed_doc"):
                m = metrics_for_hits(probe, hits, relevance)
                detail_rows.append(
                    {
                        "experiment": "query_construction",
                        "scope": "IAEA_only",
                        "extra_docs": 0,
                        "trial": 0,
                        "query_mode": mode,
                        "relevance": relevance,
                        "probe_node_id": probe.node_id,
                        "probe_doc_id": probe.doc_id,
                        "pool_docs": len(allowed_iaea),
                        "pool_chunks": len(pool_iaea),
                        "query_preview": query_text_cache.get(key, "")[:120],
                        **m,
                    }
                )
    print(f"  ✓ query_construction pool={len(allowed_iaea)}docs/{len(pool_iaea)}chunks")

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail_path = out_dir / f"selfretrieval_detail_{ts}.csv"
    _write_csv(detail_path, detail_rows)

    paths = export_reports_from_detail(detail_rows, out_dir, ts=ts)

    print("\n" + "=" * 60)
    print("  自检索实验完成")
    print(f"  明细 CSV     : {detail_path}")
    for label, path in paths.items():
        print(f"  {label:<12}: {path}")
    print("=" * 60)


def load_detail_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def export_reports_from_detail(
    detail_rows: list[dict],
    out_dir: Path,
    *,
    ts: str | None = None,
) -> dict[str, Path]:
    """从 detail 明细重算汇总、表、图（无需重跑检索）。供 mdselfretrival_plot.py 调用。"""
    if not detail_rows:
        raise ValueError("detail 为空")
    out_dir.mkdir(parents=True, exist_ok=True)
    if ts is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    metric_keys = tuple(f"recall_at_{k}" for k in RECALL_KS) + ("mrr",)

    decay_raw = _aggregate_metric_rows(
        [r for r in detail_rows if r.get("experiment") == "corpus_decay"],
        ("experiment", "extra_docs", "query_mode", "relevance"),
        metric_keys,
    )
    query_raw = _aggregate_metric_rows(
        [r for r in detail_rows if r.get("experiment") == "query_construction"],
        ("experiment", "extra_docs", "query_mode", "relevance"),
        metric_keys,
    )
    decay_final = _aggregate_decay_for_plot(detail_rows, metric_keys)
    query_final = _aggregate_query_for_plot(detail_rows, metric_keys)

    paths: dict[str, Path] = {
        "汇总 CSV": out_dir / f"selfretrieval_summary_{ts}.csv",
        "绘图汇总 CSV": out_dir / f"selfretrieval_summary_plot_{ts}.csv",
        "衰减 Recall@10": out_dir / f"selfretrieval_decay_recall10_{ts}.png",
        "衰减 MRR": out_dir / f"selfretrieval_decay_mrr_{ts}.png",
        "查询构造图": out_dir / f"selfretrieval_query_recall10_{ts}.png",
        "衰减表": out_dir / f"selfretrieval_table_decay_recall10_{ts}.csv",
        "查询构造表": out_dir / f"selfretrieval_table_query_{ts}.csv",
        "重叠歧义表": out_dir / f"selfretrieval_overlap_gap_{ts}.csv",
    }

    _write_csv(paths["汇总 CSV"], decay_raw + query_raw)
    _write_csv(paths["绘图汇总 CSV"], decay_final + query_final)
    _plot_decay(
        decay_final,
        paths["衰减 Recall@10"],
        metric="recall_at_10",
        title="Self-Retrieval Recall@10 vs Corpus Expansion (first sentence)",
    )
    _plot_decay(
        decay_final,
        paths["衰减 MRR"],
        metric="mrr",
        title="Self-Retrieval MRR vs Corpus Expansion (first sentence)",
    )
    _plot_query_modes(query_final, paths["查询构造图"], metric="recall_at_10")
    _write_decay_table(paths["衰减表"], decay_final, "recall_at_10")
    _write_query_table(paths["查询构造表"], query_final, "recall_at_10")
    _write_overlap_gap(paths["重叠歧义表"], decay_final)
    return paths


def _write_overlap_gap(path: Path, decay_summary: list[dict]) -> None:
    """分块重叠歧义: strict vs relaxed 的 Recall@10 差值（按扩库规模）。"""
    by_extra: dict[int, dict[str, float]] = defaultdict(dict)
    for row in decay_summary:
        if row.get("experiment") != "corpus_decay":
            continue
        extra = int(row["extra_docs"])
        rel = row["relevance"]
        by_extra[extra][rel] = float(row["recall_at_10_mean"])

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "extra_docs",
                "recall10_strict",
                "recall10_relaxed_doc",
                "gap_relaxed_minus_strict",
                "ratio_relaxed_over_strict",
            ]
        )
        for extra in sorted(by_extra.keys()):
            s = by_extra[extra].get("strict", 0.0)
            r = by_extra[extra].get("relaxed_doc", 0.0)
            gap = r - s
            ratio = (r / s) if s > 1e-9 else float("nan")
            w.writerow([extra, f"{s:.4f}", f"{r:.4f}", f"{gap:.4f}", f"{ratio:.4f}"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MD 自检索评测（与 mdselfcompare 共用 storage 与扩库协议）",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help=f"每个附加规模的随机试验次数（默认 {DEFAULT_TRIALS}，IAEA_only 仅 1 次）",
    )
    parser.add_argument(
        "chunk_args",
        nargs="*",
        type=int,
        metavar="N",
        help="简写: chunk_size chunk_overlap（如 800 80）",
    )
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录（默认 output_mdselfretrival_o{overlap}_c{chunk_size}）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K_EVAL,
        help=f"检索 top-k（默认 {TOP_K_EVAL}）",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=DEFAULT_SAMPLES,
        help=f"IAEA 探针 chunk 数量（默认 {DEFAULT_SAMPLES}）",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        if args.chunk_args:
            chunk_size, chunk_overlap = resolve_chunk_params(
                args.chunk_args, args.chunk_size, args.chunk_overlap
            )
        elif args.chunk_size is not None or args.chunk_overlap is not None:
            chunk_size, chunk_overlap = resolve_chunk_params(
                [], args.chunk_size, args.chunk_overlap
            )
        else:
            print("  （交互选 storage，与 mdselfcompare 相同）")
            chunk_size, chunk_overlap = prompt_chunk_params()
    except SystemExit as exc:
        parser.error(str(exc))

    storage_dir = resolve_storage_dir(chunk_size, chunk_overlap)
    out_dir = (
        args.out_dir.resolve()
        if args.out_dir
        else out_dir_for(chunk_size, chunk_overlap)
    )

    print("=" * 60)
    print("  MD 自检索评测")
    print("=" * 60)
    print(f"  trials      : {args.trials}（IAEA_only 仅 1 次）")
    print(f"  chunk       : {chunk_size} / {chunk_overlap}")
    print(f"  storage     : {storage_dir}")
    print(f"  out_dir     : {out_dir}")
    print(f"  samples     : {args.samples}")
    print(f"  top_k       : {args.top_k}")
    print(f"  query_modes : {', '.join(QUERY_MODES)}")

    run_experiment(
        storage_dir=storage_dir.resolve(),
        out_dir=out_dir,
        trials=args.trials,
        top_k=args.top_k,
        seed=args.seed,
        n_samples=args.samples,
    )


if __name__ == "__main__":
    main()

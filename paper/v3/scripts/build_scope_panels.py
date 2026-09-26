#!/usr/bin/env python3
"""Build the two single-panel corpus-expansion figures for V3 Figure 5.1--5.2.

The script aggregates the checked-in retrieval summaries only; it performs no
model inference.  It deliberately writes one metric per PDF so the two results
can be placed and numbered independently in the V3 manuscript.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "paper" / "v3" / "figs"


def config_from_path(path: Path) -> str:
    text = str(path.parent)
    current = re.search(r"c(\d+)_o(\d+)", text)
    if current:
        return f"c{current.group(1)}/o{current.group(2)}"
    legacy = re.search(r"_o(\d+)_c(\d+)", text)
    if legacy:
        return f"c{legacy.group(2)}/o{legacy.group(1)}"
    raise ValueError(f"Cannot extract index configuration from {path}")


def scope_results() -> pd.DataFrame:
    frames = []
    for path in sorted(EVIDENCE.glob("rag_results/**/scope_summary*.csv")):
        try:
            config = config_from_path(path)
        except ValueError:
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        frame["config"] = config
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No scope_summary CSV files found")
    scope = pd.concat(frames, ignore_index=True)
    for column in scope.columns:
        if column not in {"scope", "query_tag", "lang", "query", "config"}:
            scope[column] = pd.to_numeric(scope[column], errors="coerce")
    return scope


def plot_metric(data: pd.DataFrame, metric: str, spread: str, ylabel: str, filename: str) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.8), constrained_layout=True)
    colors = {"en": "#1f77b4", "zh": "#d62728"}
    labels = {"en": "English phrase", "zh": "Chinese phrase"}
    for lang in ("en", "zh"):
        part = data[data["lang"].eq(lang)].sort_values("extra_docs")
        ax.plot(part["extra_docs"], part[metric], marker="o", lw=2,
                color=colors[lang], label=labels[lang])
        ax.fill_between(part["extra_docs"], part[metric] - part[spread],
                        part[metric] + part[spread], color=colors[lang], alpha=0.16)
    ax.set_xlabel("Supplementary documents admitted")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper right" if metric == "priority_mean" else "lower right")
    if metric == "priority_mean":
        ax.set_ylim(-0.03, 1.05)
    fig.savefig(OUT / filename, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    scope = scope_results()
    phrase = scope[scope["query_tag"].eq("phrase") & scope["extra_docs"].between(0, 45)]
    grouped = (
        phrase.groupby(["lang", "extra_docs"], as_index=False)
        .agg(
            priority_mean=("iaea_purity_topk_mean", "mean"),
            priority_std=("iaea_purity_topk_mean", "std"),
            score_mean=("top1_score_mean", "mean"),
            score_std=("top1_score_mean", "std"),
        )
        .fillna(0.0)
    )
    OUT.mkdir(exist_ok=True)
    plot_metric(grouped, "priority_mean", "priority_std", "IAEA priority@10", "fig04a_scope_priority.pdf")
    plot_metric(grouped, "score_mean", "score_std", "Mean top-1 cosine score", "fig04b_top1_cosine.pdf")


if __name__ == "__main__":
    main()

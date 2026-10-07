#!/usr/bin/env python3
"""Build Fig. 8 from three representative self-retrieval configurations."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "evidence" / "rag_results"
OUT = ROOT / "paper" / "v3" / "figs"
CONFIGS = [(800, 50), (1000, 80), (1200, 150)]
COLORS = {"strict": "#2563EB", "relaxed_doc": "#F97316"}
LABELS = {"strict": "Strict chunk", "relaxed_doc": "Same document"}
ROLES = {
    (800, 50): "Original configuration",
    (1000, 80): "Narrow gap",
    (1200, 150): "Wide gap",
}


def load_config(chunk: int, overlap: int) -> pd.DataFrame:
    candidates = sorted(RESULTS.glob(
        f"output_mdselfretrival_o{overlap}_c{chunk}/selfretrieval_summary_*.csv"
    ))
    paths = [path for path in candidates if "_plot_" not in path.name]
    if len(paths) != 1:
        raise ValueError(f"Expected one summary for {chunk}/{overlap}, found {len(paths)}")
    data = pd.read_csv(paths[0], encoding="utf-8-sig")
    return data.groupby(["extra_docs", "relevance"], as_index=False)["mrr_mean"].mean()


def main() -> None:
    fig, axes = plt.subplots(3, 1, figsize=(3.30, 5.05), sharex=True, sharey=True)
    panel_labels = ("(a)", "(b)", "(c)")
    for ax, panel, (chunk, overlap) in zip(axes, panel_labels, CONFIGS):
        data = load_config(chunk, overlap)
        expanded_by_relevance: dict[str, pd.DataFrame] = {}
        for relevance in ("strict", "relaxed_doc"):
            subset = data[data["relevance"].eq(relevance)].sort_values("extra_docs")
            baseline = subset[subset["extra_docs"].eq(0)]
            expanded = subset[subset["extra_docs"].gt(0)]
            expanded_by_relevance[relevance] = expanded
            ax.plot(expanded["extra_docs"], expanded["mrr_mean"], color=COLORS[relevance],
                    marker="o", markersize=3.1, linewidth=1.55, label=LABELS[relevance])
            ax.plot(pd.concat([baseline, expanded.iloc[:1]])["extra_docs"],
                    pd.concat([baseline, expanded.iloc[:1]])["mrr_mean"],
                    color=COLORS[relevance], linewidth=1.0, linestyle="--", alpha=0.75)
            ax.scatter(baseline["extra_docs"], baseline["mrr_mean"], s=25,
                       facecolors="white", edgecolors=COLORS[relevance], linewidths=1.3, zorder=3)
        strict = expanded_by_relevance["strict"]
        document = expanded_by_relevance["relaxed_doc"]
        ax.fill_between(strict["extra_docs"], strict["mrr_mean"], document["mrr_mean"],
                        color="#CBD5E1", alpha=0.44, zorder=0)
        ax.set_title(f"{panel} {chunk}/{overlap}", fontsize=9, pad=5)
        ax.text(0.97, 0.09, ROLES[(chunk, overlap)], transform=ax.transAxes,
                ha="right", va="bottom", fontsize=6.7, color="#475569",
                bbox={"boxstyle": "round,pad=0.25", "facecolor": "#F1F5F9",
                      "edgecolor": "none", "alpha": 0.96})
        ax.set_xlim(0, 51)
        ax.set_ylim(0.35, 0.85)
        ax.set_xticks((0, 10, 25, 40, 50))
        ax.set_yticks((0.4, 0.6, 0.8))
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", color="#CBD5E1", linewidth=0.55)
        ax.set_facecolor("#F8FAFC")
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color("#334155")
    fig.supylabel("Mean reciprocal rank", fontsize=8, x=0.02)
    axes[-1].set_xlabel("Supplementary documents admitted", fontsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=7.4,
               frameon=False, bbox_to_anchor=(0.54, 0.995))
    fig.subplots_adjust(left=0.18, right=0.98, bottom=0.09, top=0.91, hspace=0.42)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig08_self_retrieval_selected.pdf", bbox_inches="tight")


if __name__ == "__main__":
    main()

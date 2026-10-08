#!/usr/bin/env python3
"""Build Fig. 8: self-retrieval trajectories for all chunk configurations."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "evidence" / "rag_results"
OUT = ROOT / "paper" / "v3" / "figs"


def load_results() -> dict[tuple[int, int], pd.DataFrame]:
    results: dict[tuple[int, int], pd.DataFrame] = {}
    for path in sorted(RESULTS.glob("output_mdselfretrival_*/selfretrieval_summary_*.csv")):
        if "_plot_" in path.name:
            continue
        match = re.search(r"_o(\d+)_c(\d+)", path.parent.name)
        if not match:
            continue
        overlap, chunk = map(int, match.groups())
        results[(chunk, overlap)] = pd.read_csv(path, encoding="utf-8-sig")
    if len(results) != 17:
        raise ValueError(f"Expected 17 configurations, found {len(results)}")
    return results


def main() -> None:
    results = load_results()
    configs = [(800, 50)] + [(chunk, overlap) for overlap in (80, 100, 120, 150)
                              for chunk in (800, 1000, 1200, 1500)]
    fig, axes = plt.subplots(5, 4, figsize=(7.25, 8.0), sharex=True, sharey=True)
    colors = {"strict": "#2563EB", "relaxed_doc": "#F97316"}
    labels = {"strict": "Strict chunk", "relaxed_doc": "Same document"}

    for index, (chunk, overlap) in enumerate(configs):
        ax = axes.flat[index]
        data = results[(chunk, overlap)]
        for relevance in ("strict", "relaxed_doc"):
            subset = data[data["relevance"].eq(relevance)].sort_values("extra_docs")
            ax.plot(subset["extra_docs"], subset["mrr_mean"], color=colors[relevance],
                    marker="o", markersize=2.0, linewidth=1.05)
        ax.set_title(f"{chunk}/{overlap}", fontsize=7, pad=2)
        ax.set_xlim(0, 51)
        ax.set_ylim(0.35, 0.85)
        ax.set_xticks((0, 25, 50))
        ax.set_yticks((0.4, 0.6, 0.8))
        ax.tick_params(labelsize=6, length=2, pad=1)
        ax.grid(axis="y", color="#CBD5E1", linewidth=0.45)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    for ax in axes.flat[len(configs):]:
        ax.set_visible(False)
    fig.supxlabel("Supplementary documents admitted", fontsize=8, y=0.035)
    fig.supylabel("Mean reciprocal rank", fontsize=8, x=0.025)
    fig.legend([Line2D([0], [0], color=colors[key], marker="o", markersize=3, linewidth=1.2)
                for key in ("strict", "relaxed_doc")],
               [labels[key] for key in ("strict", "relaxed_doc")],
               loc="upper center", ncol=2, frameon=False, fontsize=8,
               bbox_to_anchor=(0.53, 0.995))
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.075, top=0.94,
                        hspace=0.43, wspace=0.25)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig08_self_retrieval_grid.pdf", bbox_inches="tight")


if __name__ == "__main__":
    main()

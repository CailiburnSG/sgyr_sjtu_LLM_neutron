#!/usr/bin/env python3
"""Render a data-grounded retrieval-reliability atlas from existing CSV results."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "paper" / "v2" / "figs"

INK = "#102B46"
MUTED = "#64798B"
EN = "#2878B5"
ZH = "#D35F5F"


def config_from_path(path: Path) -> str:
    match = re.search(r"_o(\d+)_c(\d+)", str(path.parent))
    if not match:
        raise ValueError(path)
    return f"c{match.group(2)}/o{match.group(1)}"


def historical() -> pd.DataFrame:
    frames = []
    for path in sorted(EVIDENCE.glob("rag_results/**/scope_summary*.csv")):
        if not re.search(r"_o\d+_c\d+", str(path.parent)):
            continue
        data = pd.read_csv(path, encoding="utf-8-sig")
        data["config"] = config_from_path(path)
        frames.append(data)
    data = pd.concat(frames, ignore_index=True)
    for col in ("extra_docs", "top1_score_mean", "iaea_purity_topk_mean"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data[(data["query_tag"] == "phrase") & data["extra_docs"].between(0, 45)].copy()


def sort_config(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"c(\d+)/o(\d+)", value)
    return int(match.group(1)), int(match.group(2))


def draw_heatmap(ax, data: pd.DataFrame, lang: str, cmap):
    subset = data[data["lang"].eq(lang)]
    configs = sorted(subset["config"].unique(), key=sort_config)
    docs = sorted(subset["extra_docs"].unique())
    grid = subset.pivot(index="config", columns="extra_docs", values="iaea_purity_topk_mean").reindex(configs).reindex(columns=docs)
    im = ax.imshow(grid.to_numpy(), aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    ax.set_xticks(range(len(docs)), docs)
    ax.set_yticks([0, len(configs) - 1], [configs[0], configs[-1]])
    ax.tick_params(axis="both", labelsize=7, length=0)
    ax.set_xlabel("supplementary documents", fontsize=8, color=MUTED)
    ax.set_title("English phrase" if lang == "en" else "Chinese phrase", fontsize=10, color=INK, fontweight="bold", pad=5)
    for spine in ax.spines.values(): spine.set_color("#B9CAD5")
    return im


def main() -> None:
    OUT.mkdir(exist_ok=True)
    scope = historical()
    cmap = LinearSegmentedColormap.from_list("priority", ["#F7D9D9", "#F4E6A8", "#77C7B8", "#0B6774"])

    fig = plt.figure(figsize=(12.2, 5.35), facecolor="white")
    grid = fig.add_gridspec(2, 11, height_ratios=[.18, 1], left=.055, right=.98, bottom=.13, top=.92, wspace=.68)
    title_ax = fig.add_subplot(grid[0, :])
    title_ax.axis("off")
    title_ax.text(0, .72, "Retrieval reliability atlas: similarity gain can mask source-priority loss",
                  fontsize=18, fontweight="bold", color=INK, va="center")

    ax_h1 = fig.add_subplot(grid[1, 0:3])
    im = draw_heatmap(ax_h1, scope, "en", cmap)
    cbar = fig.colorbar(im, ax=ax_h1, fraction=.048, pad=.04)
    cbar.ax.tick_params(labelsize=7)
    cbar.set_label("IAEA priority@10", fontsize=8, color=MUTED)
    fig.text(.055, .80, "A  ENGLISH CONFIGURATION GRADIENT", fontsize=9.5, color=INK, fontweight="bold")

    ax_q = fig.add_subplot(grid[1, 4:11])
    ax_q.axhspan(-1, 0, color="#FBE9E9", zorder=0)
    ax_q.axhspan(0, 1, color="#EDF7F2", zorder=0)
    ax_q.axvline(0, color="#8DA1AF", lw=.9)
    ax_q.axhline(0, color="#8DA1AF", lw=.9)
    baseline = scope[scope["extra_docs"].eq(0)][["config", "lang", "top1_score_mean", "iaea_purity_topk_mean"]].rename(
        columns={"top1_score_mean": "score0", "iaea_purity_topk_mean": "priority0"})
    points = scope[scope["extra_docs"].gt(0)].merge(baseline, on=["config", "lang"], how="left")
    points["delta_score"] = points["top1_score_mean"] - points["score0"]
    points["delta_priority"] = points["iaea_purity_topk_mean"] - points["priority0"]
    for lang, color, label in (("en", EN, "English phrase"), ("zh", ZH, "Chinese phrase")):
        part = points[points["lang"].eq(lang)]
        ax_q.scatter(part["delta_score"], part["delta_priority"], s=12 + 1.1*part["extra_docs"],
                     color=color, edgecolor="white", linewidth=.35, alpha=.78, label=label)
    ax_q.text(.013, .85, "priority retained", transform=ax_q.transAxes, fontsize=8, color="#438060", fontweight="bold")
    ax_q.text(.58, .08, "deployment-risk region\n(similarity rises; priority falls)", transform=ax_q.transAxes,
              fontsize=8, color="#B75A5A", fontweight="bold", ha="center")
    ax_q.set_xlabel("Change in top-1 cosine from IAEA-only", fontsize=8.6, color=MUTED)
    ax_q.set_ylabel("Change in IAEA priority@10 from IAEA-only", fontsize=8.6, color=MUTED)
    ax_q.tick_params(labelsize=7.5)
    ax_q.grid(alpha=.16)
    ax_q.legend(frameon=False, loc="lower left", fontsize=8)
    ax_q.set_title("B  BILINGUAL CONFIGURATION-SCOPE QUADRANT", fontsize=10.5, color=INK, fontweight="bold", pad=6)

    plt.close(fig)

    heat_fig, heat_ax = plt.subplots(figsize=(4.8, 3.5), constrained_layout=True)
    im = draw_heatmap(heat_ax, scope, "en", cmap)
    cbar = heat_fig.colorbar(im, ax=heat_ax, fraction=.048, pad=.04)
    cbar.ax.tick_params(labelsize=7)
    cbar.set_label("IAEA priority@10", fontsize=8, color=MUTED)
    heat_fig.savefig(OUT / "fig09_retrieval_gradient.pdf", bbox_inches="tight")
    plt.close(heat_fig)

    quadrant_fig, quadrant_ax = plt.subplots(figsize=(4.8, 3.5), constrained_layout=True)
    quadrant_ax.axhspan(-1, 0, color="#FBE9E9", zorder=0)
    quadrant_ax.axhspan(0, 1, color="#EDF7F2", zorder=0)
    quadrant_ax.axvline(0, color="#8DA1AF", lw=.9)
    quadrant_ax.axhline(0, color="#8DA1AF", lw=.9)
    for lang, color, label in (("en", EN, "English phrase"), ("zh", ZH, "Chinese phrase")):
        part = points[points["lang"].eq(lang)]
        quadrant_ax.scatter(part["delta_score"], part["delta_priority"],
                            s=12 + 1.1 * part["extra_docs"], color=color,
                            edgecolor="white", linewidth=.35, alpha=.78, label=label)
    quadrant_ax.text(.03, .91, "priority retained", transform=quadrant_ax.transAxes,
                     fontsize=8, color="#438060", fontweight="bold")
    quadrant_ax.text(.60, .08, "deployment-risk region\n(similarity rises; priority falls)",
                     transform=quadrant_ax.transAxes, fontsize=8, color="#B75A5A",
                     fontweight="bold", ha="center")
    quadrant_ax.set_xlabel("Change in top-1 cosine from IAEA-only", fontsize=8.6, color=MUTED)
    quadrant_ax.set_ylabel("Change in IAEA priority@10 from IAEA-only", fontsize=8.6, color=MUTED)
    quadrant_ax.tick_params(labelsize=7.5)
    quadrant_ax.grid(alpha=.16)
    quadrant_ax.legend(frameon=False, loc="lower left", fontsize=8)
    quadrant_fig.savefig(OUT / "fig10_retrieval_quadrant.pdf", bbox_inches="tight")
    plt.close(quadrant_fig)


if __name__ == "__main__":
    main()

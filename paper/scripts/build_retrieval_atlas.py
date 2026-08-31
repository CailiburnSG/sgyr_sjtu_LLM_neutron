#!/usr/bin/env python3
"""Render a data-grounded retrieval-reliability atlas from existing CSV results."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "paper" / "figs"

INK = "#102B46"
MUTED = "#64798B"
EN = "#2878B5"
ZH = "#D35F5F"
MULTI = "#169A94"
ENGLISH = "#7B67B7"


def config_from_path(path: Path) -> str:
    match = re.search(r"_o(\d+)_c(\d+)", str(path.parent))
    if not match:
        raise ValueError(path)
    return f"c{match.group(2)}/o{match.group(1)}"


def historical() -> pd.DataFrame:
    frames = []
    for path in sorted(EVIDENCE.glob("rag_results/**/scope_summary*.csv")):
        data = pd.read_csv(path, encoding="utf-8-sig")
        data["config"] = config_from_path(path)
        frames.append(data)
    data = pd.concat(frames, ignore_index=True)
    for col in ("extra_docs", "top1_score_mean", "iaea_purity_topk_mean"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data[(data["query_tag"] == "phrase") & data["extra_docs"].between(0, 45)].copy()


def embedding_comparison() -> pd.DataFrame:
    frames = []
    for path in sorted(EVIDENCE.glob("embedding_benchmark/**/scope_summary.csv")):
        frames.append(pd.read_csv(path, encoding="utf-8-sig"))
    data = pd.concat(frames, ignore_index=True)
    for col in ("extra_docs", "top1_score_mean", "top10_mean_score_mean", "iaea_priority_top10_mean"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data[(data["query_tag"] == "phrase") & data["extra_docs"].eq(10)].copy()


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


def draw_radar(ax, data: pd.DataFrame, lang: str):
    subset = data[data["lang"].eq(lang)].copy()
    axes = ["Top-1\ncosine", "Top-10 mean\ncosine", "IAEA\npriority@10"]
    angles = np.linspace(0, 2 * np.pi, len(axes), endpoint=False).tolist()
    angles += angles[:1]
    styles = [("multilingual", MULTI, "Multilingual MiniLM-L12"), ("English", ENGLISH, "English MiniLM-L6")]
    for key, color, label in styles:
        row = subset[subset["model"].str.contains("multilingual", case=False) if key == "multilingual" else subset["model"].str.contains("all-MiniLM", case=False)].iloc[0]
        values = [row["top1_score_mean"], row["top10_mean_score_mean"], row["iaea_priority_top10_mean"]]
        values += values[:1]
        ax.plot(angles, values, color=color, linewidth=1.9, label=label)
        ax.fill(angles, values, color=color, alpha=.12)
    ax.set_xticks(angles[:-1], axes, fontsize=7, color=INK)
    ax.set_yticks([.25, .5, .75, 1.0], ["", ".5", "", "1.0"], fontsize=6, color=MUTED)
    ax.set_ylim(0, 1)
    ax.grid(color="#D6E0E7", linewidth=.7)
    ax.spines["polar"].set_color("#B9CAD5")
    ax.set_title("English" if lang == "en" else "Chinese", fontsize=9, color=INK, fontweight="bold", pad=10)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    scope = historical()
    embedding_data = embedding_comparison()
    cmap = LinearSegmentedColormap.from_list("priority", ["#F7D9D9", "#F4E6A8", "#77C7B8", "#0B6774"])

    fig = plt.figure(figsize=(15.0, 6.15), facecolor="white")
    grid = fig.add_gridspec(2, 14, height_ratios=[.18, 1], left=.045, right=.985, bottom=.11, top=.93, wspace=.92)
    title_ax = fig.add_subplot(grid[0, :])
    title_ax.axis("off")
    title_ax.text(0, .72, "Retrieval reliability atlas: similarity gain can mask source-priority loss",
                  fontsize=18, fontweight="bold", color=INK, va="center")
    title_ax.text(0, .14,
                  "All marks derive from existing phrase-query experiments; no new model runs or relevance labels are introduced.",
                  fontsize=9.5, color=MUTED, va="center")

    ax_h1 = fig.add_subplot(grid[1, 0:2])
    ax_h2 = fig.add_subplot(grid[1, 2:4])
    im = draw_heatmap(ax_h1, scope, "en", cmap)
    draw_heatmap(ax_h2, scope, "zh", cmap)
    cbar = fig.colorbar(im, ax=[ax_h1, ax_h2], fraction=.045, pad=.04)
    cbar.ax.tick_params(labelsize=7)
    cbar.set_label("IAEA priority@10", fontsize=8, color=MUTED)
    fig.text(.045, .80, "A  GRADIENT MAPS", fontsize=9.5, color=INK, fontweight="bold")

    ax_q = fig.add_subplot(grid[1, 4:10])
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
    ax_q.set_title("B  CONFIGURATION-SCOPE QUADRANT", fontsize=10.5, color=INK, fontweight="bold", pad=6)

    ax_r1 = fig.add_subplot(grid[1, 10:12], polar=True)
    ax_r2 = fig.add_subplot(grid[1, 12:14], polar=True)
    draw_radar(ax_r1, embedding_data, "en")
    draw_radar(ax_r2, embedding_data, "zh")
    ax_r1.text(-.25, 1.25, "C  EMBEDDING RETRIEVAL PROFILES", transform=ax_r1.transAxes, fontsize=9.5, color=INK, fontweight="bold")
    handles = [Line2D([0], [0], color=MULTI, lw=2, label="multilingual MiniLM-L12"),
               Line2D([0], [0], color=ENGLISH, lw=2, label="English MiniLM-L6")]
    fig.legend(handles=handles, loc="lower right", bbox_to_anchor=(.986, .03), frameon=False, fontsize=7.1)
    fig.text(.787, .11, "Phrase query, 10 supplementary documents,\n240-word chunks. Radar axes are raw 0–1 metrics, not a composite score.",
             fontsize=6.9, color=MUTED)

    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig8_retrieval_atlas.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=.03)


if __name__ == "__main__":
    main()

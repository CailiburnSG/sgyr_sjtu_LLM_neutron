#!/usr/bin/env python3
"""Build Figure 5: nomic semantic-match landscapes from saved scope results.

The figure overlays the two language-level query means in one coordinate
system. Each colored surface is the observed mean cosine score of the top ten
retrieved chunks after forty-five supplementary documents are admitted.
The 4 x 4 surface joins the regular tested grid nodes only.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import cm
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d import proj3d


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "evidence" / "rag_results"
OUT = ROOT / "paper" / "v3" / "figs"

CHUNKS = [800, 1000, 1200, 1500]
OVERLAPS = [80, 100, 120, 150]
QUERIES = [
    ("neutron", "English core term"),
    ("neutron measurement current", "English measurement phrase"),
    ("中子", "Chinese core term"),
    ("中子测量电流", "Chinese measurement phrase"),
]
LANGUAGE_GROUPS = [
    ("English", ["neutron", "neutron measurement current"], "#2563EB", "#1E3A8A", cm.Blues),
    ("Chinese", ["中子", "中子测量电流"], "#F97316", "#9A3412", cm.Oranges),
]


def load_scores() -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for path in sorted(RESULTS.glob("output_mdselfcompare_*/scope_summary*.csv")):
        match = re.search(r"_o(\d+)_c(\d+)", path.parent.name)
        if not match:
            continue
        overlap, chunk = map(int, match.groups())
        data = pd.read_csv(path, encoding="utf-8-sig")
        at_0 = data[data["extra_docs"].eq(0)].set_index("query")
        at_45 = data[data["extra_docs"].eq(45)].set_index("query")
        for query, _ in QUERIES:
            if query not in at_0.index or query not in at_45.index:
                raise ValueError(f"Missing {query!r} at m=0 or m=45 in {path}")
            rows.append(
                {
                    "query": query,
                    "chunk": chunk,
                    "overlap": overlap,
                    "score_m0": float(at_0.loc[query, "top10_mean_score_mean"]),
                    "score_m45": float(at_45.loc[query, "top10_mean_score_mean"]),
                }
            )
    scores = pd.DataFrame(rows)
    expected = len(QUERIES) * 17
    if len(scores) != expected:
        raise ValueError(f"Expected {expected} query/configuration scores, got {len(scores)}")
    return scores


def main() -> None:
    scores = load_scores()
    x_grid, y_grid = np.meshgrid(CHUNKS, OVERLAPS)
    fig = plt.figure(figsize=(7.1, 5.0), constrained_layout=True)
    ax = fig.add_subplot(1, 1, 1, projection="3d")
    surfaces = []
    peaks = []
    for language, queries, color, label_color, cmap in LANGUAGE_GROUPS:
        panel = (
            scores[scores["query"].isin(queries)]
            .groupby(["chunk", "overlap"], as_index=False)[["score_m0", "score_m45"]]
            .mean()
        )
        grid_m0 = (
            panel[panel["overlap"].isin(OVERLAPS)]
            .pivot(index="overlap", columns="chunk", values="score_m0")
            .reindex(index=OVERLAPS, columns=CHUNKS)
        )
        grid_m45 = (
            panel[panel["overlap"].isin(OVERLAPS)]
            .pivot(index="overlap", columns="chunk", values="score_m45")
            .reindex(index=OVERLAPS, columns=CHUNKS)
        )
        if grid_m0.isna().any().any() or grid_m45.isna().any().any():
            raise ValueError(f"Incomplete 4 x 4 grid for {language}")
        z_m45 = grid_m45.to_numpy()
        local_norm = Normalize(vmin=z_m45.min(), vmax=z_m45.max())
        ax.plot_surface(
            x_grid, y_grid, z_m45,
            facecolors=cmap(0.42 + 0.52 * local_norm(z_m45)),
            rstride=1, cstride=1,
            edgecolor="#1F2937",
            linewidth=0.45,
            antialiased=True,
            shade=True,
            alpha=0.72,
        )
        ax.scatter(x_grid.ravel(), y_grid.ravel(), z_m45.ravel(), color=color,
                   edgecolor="#1F2937", linewidth=0.35, s=18, depthshade=False)
        peak_row, peak_col = np.unravel_index(np.argmax(z_m45), z_m45.shape)
        peak_x, peak_y, peak_z = x_grid[peak_row, peak_col], y_grid[peak_row, peak_col], z_m45[peak_row, peak_col]
        peaks.append((language, color, label_color, peak_x, peak_y, peak_z))
        surfaces.append(z_m45)

    z_values = np.concatenate([surface.ravel() for surface in surfaces])
    z_low, z_high = z_values.min() - 0.004, z_values.max() + 0.004
    ax.set_title("Full-database mean semantic matching", fontsize=10.5, fontweight="bold", pad=8)
    ax.set_xlabel("chunk size", labelpad=5, fontsize=8.5)
    ax.set_ylabel("overlap", labelpad=5, fontsize=8.5)
    ax.set_zlabel("mean cosine score (top 10)", labelpad=5, fontsize=8.5)
    ax.set_xticks(CHUNKS)
    ax.set_yticks(OVERLAPS)
    ax.set_xlim(735, 1540)
    ax.set_ylim(75, 155)
    ax.set_zticks(np.linspace(z_low, z_high, 5))
    ax.set_zlim(z_low, z_high)
    ax.set_box_aspect((1.25, 1.0, 0.85))
    ax.tick_params(labelsize=7)
    ax.view_init(elev=25, azim=-58)
    ax.grid(True, color="#94A3B8", alpha=0.42, linewidth=0.6)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor("#F8FAFC")
        axis.pane.set_alpha(0.58)
    ax.legend(handles=[Patch(facecolor=color, edgecolor="#1F2937", alpha=0.78,
                             label=f"{language} query mean")
                       for language, _, color, _, _ in LANGUAGE_GROUPS],
              loc="upper left", bbox_to_anchor=(0.02, 0.98), fontsize=7.5, frameon=True)
    fig.canvas.draw()
    label_positions = {"English": (0.07, 0.69), "Chinese": (0.07, 0.49)}
    for language, color, label_color, peak_x, peak_y, peak_z in peaks:
        x_2d, y_2d, _ = proj3d.proj_transform(peak_x, peak_y, peak_z, ax.get_proj())
        peak_axes = ax.transAxes.inverted().transform(ax.transData.transform((x_2d, y_2d)))
        ax.annotate(
            f"{language}\nmax {peak_z:.3f}", xy=peak_axes, xytext=label_positions[language],
            xycoords=ax.transAxes, textcoords=ax.transAxes, color=label_color,
            fontsize=6.2, fontweight="bold", ha="right", va="center",
            arrowprops={"arrowstyle": "->", "color": color, "lw": 1.5, "shrinkA": 1, "shrinkB": 2},
        )
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig05_nomic_loss_landscapes.pdf", bbox_inches="tight")


if __name__ == "__main__":
    main()

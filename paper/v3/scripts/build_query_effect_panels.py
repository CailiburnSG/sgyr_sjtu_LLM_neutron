"""Build the Fig. 5 query-family mean-difference panels from recorded P0 results."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm"
OUT = ROOT / "paper/v3/figs"
CHUNKS = [(800, 80), (1200, 120), (1500, 150)]
MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
]


def load_scope() -> pd.DataFrame:
    frames = []
    for chunk, overlap in CHUNKS:
        for model in MODELS:
            path = RESULTS / f"c{chunk}_o{overlap}" / model.replace("/", "__") / "scope_summary.csv"
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    data = load_scope()
    at_m10 = data[data.extra_docs.eq(10)].copy()
    family_means = (
        at_m10.groupby(["model", "chunk_size", "chunk_overlap", "language", "family"], as_index=False)
        .iaea_priority_top10_mean.mean()
    )
    effects = family_means.pivot(
        index=["model", "chunk_size", "chunk_overlap", "language"],
        columns="family",
        values="iaea_priority_top10_mean",
    ).reset_index()
    effects["delta"] = effects["observation_derived"] - effects["baseline"]
    effects["setting"] = effects.apply(
        lambda row: f"{'Multi' if row.model == MODELS[0] else 'English'}\n"
        f"{int(row.chunk_size)}/{int(row.chunk_overlap)}",
        axis=1,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    for language, title, filename in (
        ("en", "English queries", "fig05a_query_effect_en.pdf"),
        ("zh", "Chinese queries", "fig05b_query_effect_zh.pdf"),
    ):
        panel = effects[effects.language.eq(language)].copy()
        panel["model_order"] = panel.model.map({MODELS[0]: 0, MODELS[1]: 1})
        panel = panel.sort_values(["model_order", "chunk_size"]).reset_index(drop=True)
        y = np.arange(len(panel))
        colours = np.where(panel.delta >= 0, "#159A8A", "#D05A5A")

        # These panels are displayed side by side inside one manuscript column.
        # Keep each source panel narrow and tall so its typography remains legible
        # after placement at roughly half a column width.
        fig, ax = plt.subplots(figsize=(2.15, 4.45), constrained_layout=True)
        ax.axvline(0, color="#64748B", lw=1.1, zorder=0)
        ax.hlines(y, 0, panel.delta, color=colours, lw=2.0, alpha=0.8)
        ax.scatter(panel.delta, y, s=78, color=colours, edgecolor="white", linewidth=0.8, zorder=3)
        for yi, value in zip(y, panel.delta):
            side = 0.008 if value >= 0 else -0.008
            ax.text(value + side, yi, f"{value:+.2f}", ha="left" if value >= 0 else "right",
                    va="center", fontsize=7.7, color="#334155", fontweight="bold")
        ax.set_title(title, loc="left", fontsize=9, fontweight="bold")
        ax.set_yticks(y, panel.setting, fontsize=7.2)
        ax.set_xlim(-0.27, 0.18)
        ax.set_xlabel(r"$\Delta$ CorePriority@10", fontsize=8)
        ax.grid(axis="x", color="#D1D5DB", lw=0.7)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        fig.savefig(OUT / filename, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    main()

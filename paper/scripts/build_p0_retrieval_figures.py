"""Build manuscript figures from the completed P0 MiniLM chunking-grid results.

The script only reads recorded result summaries.  It uses display labels that
describe the manually authored technical-detail queries without rewriting the
underlying result artefacts, which retain their original provenance fields.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm"
OUT = ROOT / "paper/v2/figs"

CHUNKS = [(800, 80), (1200, 120), (1500, 150)]
MODEL_ORDER = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
]
MODEL_SHORT = {
    MODEL_ORDER[0]: "Multilingual MiniLM",
    MODEL_ORDER[1]: "English-oriented MiniLM",
}
CHUNK_COLOURS = {(800, 80): "#2A6FBB", (1200, 120): "#E68A2E", (1500, 150): "#2F9D75"}
FAMILY_MARKERS = {"baseline": "o", "observation_derived": "D"}


def display_query(row):
    language = "EN" if row.language == "en" else "ZH"
    mapping = {
        "baseline_en_core": "Core term · EN",
        "baseline_en_phrase": "Measurement phrase · EN",
        "baseline_zh_core": "Core term · ZH",
        "baseline_zh_phrase": "Measurement phrase · ZH",
        "obs_spike_en": "Repeated spikes · EN",
        "obs_zero_en": "Synchronized zeros · EN",
        "obs_sync_en": "High synchrony · EN",
        "obs_spike_zh": "Repeated spikes · ZH",
        "obs_zero_zh": "Synchronized zeros · ZH",
        "obs_sync_zh": "High synchrony · ZH",
    }
    return mapping.get(row.query_id, f"{row.family} · {language}")


def load_scope():
    frames = []
    for chunk, overlap in CHUNKS:
        for model in MODEL_ORDER:
            path = RESULTS / f"c{chunk}_o{overlap}" / model.replace("/", "__") / "scope_summary.csv"
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def build_landscape(scope):
    m10 = scope[scope.extra_docs == 10].copy()
    m51 = scope[scope.extra_docs == 51].copy()
    keys = ["model", "chunk_size", "chunk_overlap", "query_id"]
    merged = m10.merge(
        m51[keys + ["iaea_priority_top10_mean"]],
        on=keys,
        suffixes=("_m10", "_m51"),
    )
    merged["query_label"] = merged.apply(display_query, axis=1)
    query_order = [
        "Core term · EN", "Measurement phrase · EN", "Repeated spikes · EN",
        "Synchronized zeros · EN", "High synchrony · EN",
        "Core term · ZH", "Measurement phrase · ZH", "Repeated spikes · ZH",
        "Synchronized zeros · ZH", "High synchrony · ZH",
    ]
    settings = [(model, c, o) for model in MODEL_ORDER for c, o in CHUNKS]
    values = np.empty((len(query_order), len(settings)))
    for i, label in enumerate(query_order):
        for j, (model, chunk, overlap) in enumerate(settings):
            values[i, j] = merged.loc[
                (merged.query_label == label)
                & (merged.model == model)
                & (merged.chunk_size == chunk)
                & (merged.chunk_overlap == overlap),
                "iaea_priority_top10_mean_m10",
            ].iloc[0]

    fig = plt.figure(figsize=(12.5, 6.5), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.08, 1], wspace=0.13)
    axh = fig.add_subplot(gs[0])
    im = axh.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    axh.set_title("P0 source priority at $m=10$", loc="left", fontsize=12, fontweight="bold")
    axh.set_xlabel("encoder × character chunking")
    axh.set_ylabel("manual query formulation")
    axh.set_xticks(np.arange(6), ["800/80", "1200/120", "1500/150"] * 2, rotation=0)
    axh.set_yticks(np.arange(10), query_order, fontsize=8.5)
    axh.axvline(2.5, color="#1f2937", lw=1.25)
    axh.text(1, -1.25, "Multilingual MiniLM", ha="center", va="center", fontsize=9, fontweight="bold")
    axh.text(4, -1.25, "English-oriented MiniLM", ha="center", va="center", fontsize=9, fontweight="bold")
    axh.axhline(4.5, color="white", lw=2.4)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            colour = "white" if values[i, j] > 0.56 else "#172033"
            axh.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", fontsize=7.2, color=colour)
    cb = fig.colorbar(im, ax=axh, shrink=0.85, pad=0.02)
    cb.set_label("mean IAEA priority@10")

    axs = fig.add_subplot(gs[1])
    for (model, chunk, overlap), group in merged.groupby(["model", "chunk_size", "chunk_overlap"], sort=False):
        colour = CHUNK_COLOURS[(chunk, overlap)]
        for family, family_group in group.groupby("family"):
            axs.scatter(
                family_group.iaea_priority_top10_mean_m10,
                family_group.iaea_priority_top10_mean_m51,
                s=48,
                marker=FAMILY_MARKERS[family],
                facecolor=colour,
                edgecolor="white",
                linewidth=0.7,
                alpha=0.92,
            )
    axs.plot([0, 1], [0, 1], ls="--", lw=1, color="#6b7280", zorder=0)
    axs.set_xlim(0, 1.02)
    axs.set_ylim(0, 1.02)
    axs.set_aspect("equal", adjustable="box")
    axs.grid(color="#d1d5db", lw=0.7, alpha=0.7)
    axs.set_title("Priority retention after full expansion", loc="left", fontsize=12, fontweight="bold")
    axs.set_xlabel("mean IAEA priority@10 at $m=10$")
    axs.set_ylabel("mean IAEA priority@10 at $m=51$")
    axs.text(0.04, 0.93, "below diagonal = priority decay", transform=axs.transAxes, fontsize=8.5, color="#4b5563")
    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#64748b", markersize=7, label="baseline query"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#64748b", markersize=6, label="technical-detail query"),
        *[Line2D([0], [0], marker="o", color="w", markerfacecolor=CHUNK_COLOURS[c], markersize=7, label=f"{c[0]}/{c[1]}") for c in CHUNKS],
    ]
    axs.legend(handles=legend, title="marker / colour", loc="lower right", fontsize=7.5, title_fontsize=8, frameon=True)
    plt.close(fig)

    heat_fig, heat_ax = plt.subplots(figsize=(4.8, 5.1), constrained_layout=True)
    im = heat_ax.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    heat_ax.set_title("P0 source priority at $m=10$", loc="left", fontsize=11, fontweight="bold")
    heat_ax.set_xlabel("encoder × character chunking")
    heat_ax.set_ylabel("manual query formulation")
    heat_ax.set_xticks(np.arange(6), ["800/80", "1200/120", "1500/150"] * 2, fontsize=7)
    heat_ax.set_yticks(np.arange(10), query_order, fontsize=7.2)
    heat_ax.axvline(2.5, color="#1f2937", lw=1.25)
    heat_ax.axhline(4.5, color="white", lw=2.4)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            colour = "white" if values[i, j] > 0.56 else "#172033"
            heat_ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center",
                         fontsize=6.3, color=colour)
    cb = heat_fig.colorbar(im, ax=heat_ax, shrink=0.85, pad=0.02)
    cb.set_label("mean IAEA priority@10")
    save(heat_fig, "fig13_p0_priority_heatmap")

    retention_fig, retention_ax = plt.subplots(figsize=(4.8, 4.2), constrained_layout=True)
    for (model, chunk, overlap), group in merged.groupby(["model", "chunk_size", "chunk_overlap"], sort=False):
        colour = CHUNK_COLOURS[(chunk, overlap)]
        for family, family_group in group.groupby("family"):
            retention_ax.scatter(
                family_group.iaea_priority_top10_mean_m10,
                family_group.iaea_priority_top10_mean_m51,
                s=48, marker=FAMILY_MARKERS[family], facecolor=colour,
                edgecolor="white", linewidth=0.7, alpha=0.92,
            )
    retention_ax.plot([0, 1], [0, 1], ls="--", lw=1, color="#6b7280", zorder=0)
    retention_ax.set_xlim(0, 1.02)
    retention_ax.set_ylim(0, 1.02)
    retention_ax.set_aspect("equal", adjustable="box")
    retention_ax.grid(color="#d1d5db", lw=0.7, alpha=0.7)
    retention_ax.set_title("Priority retention after full expansion", loc="left", fontsize=11, fontweight="bold")
    retention_ax.set_xlabel("mean IAEA priority@10 at $m=10$")
    retention_ax.set_ylabel("mean IAEA priority@10 at $m=51$")
    retention_ax.text(0.04, 0.93, "below diagonal = priority decay",
                      transform=retention_ax.transAxes, fontsize=8, color="#4b5563")
    retention_ax.legend(handles=legend, title="marker / colour", loc="lower right",
                        fontsize=7, title_fontsize=7.5, frameon=True)
    save(retention_fig, "fig14_p0_priority_retention")


def build_trajectory(scope):
    data = (
        scope.groupby(["model", "language", "family", "chunk_size", "chunk_overlap", "extra_docs"], as_index=False)
        .iaea_priority_top10_mean.mean()
    )
    fig, axes = plt.subplots(2, 2, figsize=(11.6, 6.8), sharex=True, sharey=True, constrained_layout=True)
    for row, model in enumerate(MODEL_ORDER):
        for col, language in enumerate(["en", "zh"]):
            ax = axes[row, col]
            panel = data[(data.model == model) & (data.language == language)]
            for (family, chunk, overlap), group in panel.groupby(["family", "chunk_size", "chunk_overlap"]):
                group = group.sort_values("extra_docs")
                ax.plot(
                    group.extra_docs,
                    group.iaea_priority_top10_mean,
                    color=CHUNK_COLOURS[(chunk, overlap)],
                    lw=2.0,
                    ls="-" if family == "baseline" else "--",
                    alpha=0.92,
                )
            ax.set_title(f"{MODEL_SHORT[model]} · {'English' if language == 'en' else 'Chinese'}", fontsize=10, loc="left", fontweight="bold")
            ax.set_xlim(0, 51)
            ax.set_ylim(0, 1.03)
            ax.grid(color="#d1d5db", lw=0.7, alpha=0.8)
            ax.axvspan(0, 10, color="#e0f2fe", alpha=0.55, zorder=0)
            ax.text(0.98, 0.05, "lines average queries within family", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.2, color="#4b5563")
    fig.supxlabel("supplementary documents admitted ($m$)")
    fig.supylabel("mean IAEA priority@10")
    handles = [
        Line2D([0], [0], color="#475569", lw=2, ls="-", label="baseline family"),
        Line2D([0], [0], color="#475569", lw=2, ls="--", label="technical-detail family"),
        *[Line2D([0], [0], color=CHUNK_COLOURS[c], lw=2, label=f"character chunks {c[0]}/{c[1]}") for c in CHUNKS],
    ]
    fig.legend(handles=handles, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.055), frameon=False, fontsize=8)
    plt.close(fig)

    for language in ("en", "zh"):
        panel_fig, panel_axes = plt.subplots(2, 1, figsize=(4.8, 5.7), sharex=True,
                                             sharey=True)
        for ax, model in zip(panel_axes, MODEL_ORDER):
            panel = data[(data.model == model) & (data.language == language)]
            for (family, chunk, overlap), group in panel.groupby(["family", "chunk_size", "chunk_overlap"]):
                group = group.sort_values("extra_docs")
                ax.plot(group.extra_docs, group.iaea_priority_top10_mean,
                        color=CHUNK_COLOURS[(chunk, overlap)], lw=1.8,
                        ls="-" if family == "baseline" else "--", alpha=0.92)
            ax.set_title(MODEL_SHORT[model], fontsize=9, loc="left", fontweight="bold")
            ax.set_xlim(0, 51)
            ax.set_ylim(0, 1.03)
            ax.grid(color="#d1d5db", lw=0.7, alpha=0.8)
            ax.axvspan(0, 10, color="#e0f2fe", alpha=0.55, zorder=0)
        panel_axes[1].set_xlabel("supplementary documents admitted ($m$)", labelpad=3)
        panel_fig.supylabel("mean IAEA priority@10", x=0.02)
        panel_fig.suptitle(f"{'English' if language == 'en' else 'Chinese'} query trajectories",
                           y=0.97, fontsize=11, fontweight="bold")
        panel_fig.legend(handles=handles, ncol=2, loc="lower center",
                         bbox_to_anchor=(0.5, 0.01), frameon=False, fontsize=6.5)
        panel_fig.subplots_adjust(left=0.16, right=0.98, top=0.91, bottom=0.19, hspace=0.18)
        number = {"en": 15, "zh": 16}[language]
        save(panel_fig, f"fig{number:02d}_p0_priority_trajectory_{language}")


def build_query_effect(scope):
    """Show whether technical-detail wording raises or lowers priority in P0."""
    at_m10 = scope[scope.extra_docs.eq(10)].copy()
    means = (
        at_m10.groupby(["model", "chunk_size", "chunk_overlap", "language", "family"], as_index=False)
        .iaea_priority_top10_mean.mean()
    )
    pivot = means.pivot(
        index=["model", "chunk_size", "chunk_overlap", "language"],
        columns="family",
        values="iaea_priority_top10_mean",
    ).reset_index()
    pivot["delta"] = pivot["observation_derived"] - pivot["baseline"]
    pivot["setting"] = pivot.apply(
        lambda row: f"{'Multi' if row.model == MODEL_ORDER[0] else 'English'}\n{int(row.chunk_size)}/{int(row.chunk_overlap)}",
        axis=1,
    )

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.25), sharey=True, constrained_layout=True)
    for ax, language, title in zip(axes, ["en", "zh"], ["English queries", "Chinese queries"]):
        panel = pivot[pivot.language.eq(language)].copy()
        panel["model_order"] = panel.model.map({MODEL_ORDER[0]: 0, MODEL_ORDER[1]: 1})
        panel = panel.sort_values(["model_order", "chunk_size"]).reset_index(drop=True)
        y = np.arange(len(panel))
        colours = np.where(panel.delta >= 0, "#159A8A", "#D05A5A")
        ax.axvline(0, color="#64748B", lw=1.1, zorder=0)
        ax.hlines(y, 0, panel.delta, color=colours, lw=2.0, alpha=0.8)
        ax.scatter(panel.delta, y, s=78, color=colours, edgecolor="white", linewidth=0.8, zorder=3)
        for yi, value in zip(y, panel.delta):
            side = 0.008 if value >= 0 else -0.008
            ax.text(value + side, yi, f"{value:+.2f}", ha="left" if value >= 0 else "right",
                    va="center", fontsize=7.7, color="#334155", fontweight="bold")
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_yticks(y, panel.setting, fontsize=7.5)
        ax.set_xlim(-0.27, 0.18)
        ax.grid(axis="x", color="#D1D5DB", lw=0.7)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.text(0.02, 0.04, "positive = technical-detail family higher", transform=ax.transAxes,
                fontsize=7.2, color="#64748B")
    fig.supxlabel(r"$\Delta$ mean IAEA priority@10 at $m=10$  (technical-detail $-$ baseline)")
    fig.supylabel("encoder / character chunks")
    fig.suptitle("P0 query-formulation effect is configuration dependent", x=0.5, y=1.02,
                 fontsize=13, fontweight="bold")
    plt.close(fig)

    for language, title in (("en", "English queries"), ("zh", "Chinese queries")):
        panel_data = pivot[pivot.language.eq(language)].copy()
        panel_data["model_order"] = panel_data.model.map({MODEL_ORDER[0]: 0, MODEL_ORDER[1]: 1})
        panel_data = panel_data.sort_values(["model_order", "chunk_size"]).reset_index(drop=True)
        panel_fig, panel_ax = plt.subplots(figsize=(4.8, 3.6), constrained_layout=True)
        y = np.arange(len(panel_data))
        colours = np.where(panel_data.delta >= 0, "#159A8A", "#D05A5A")
        panel_ax.axvline(0, color="#64748B", lw=1.1, zorder=0)
        panel_ax.hlines(y, 0, panel_data.delta, color=colours, lw=2.0, alpha=0.8)
        panel_ax.scatter(panel_data.delta, y, s=78, color=colours,
                         edgecolor="white", linewidth=0.8, zorder=3)
        for yi, value in zip(y, panel_data.delta):
            side = 0.008 if value >= 0 else -0.008
            panel_ax.text(value + side, yi, f"{value:+.2f}",
                          ha="left" if value >= 0 else "right", va="center",
                          fontsize=7.7, color="#334155", fontweight="bold")
        panel_ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        panel_ax.set_yticks(y, panel_data.setting, fontsize=7.5)
        panel_ax.set_xlim(-0.27, 0.18)
        panel_ax.set_xlabel(r"$\Delta$ mean IAEA priority@10 at $m=10$")
        panel_ax.grid(axis="x", color="#D1D5DB", lw=0.7)
        panel_ax.spines[["top", "right", "left"]].set_visible(False)
        panel_ax.tick_params(axis="y", length=0)
        panel_ax.text(0.02, 0.04, "positive = technical-detail family higher",
                      transform=panel_ax.transAxes, fontsize=7.2, color="#64748B")
        number = {"en": 11, "zh": 12}[language]
        save(panel_fig, f"fig{number:02d}_p0_query_effect_{language}")


if __name__ == "__main__":
    scope = load_scope()
    build_landscape(scope)
    build_trajectory(scope)
    build_query_effect(scope)

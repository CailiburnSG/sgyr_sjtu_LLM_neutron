#!/usr/bin/env python3
"""Build the compact MiniLM configuration-interaction heatmap for V3 Figure 5.3.

The figure reads only checked-in experiment summaries.  It reports mean
CorePriority@10 at ten admitted supplementary documents; it does not rerun
embedding or retrieval experiments.
"""

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


def display_query(query_id: str) -> str:
    labels = {
        "baseline_en_core": "Core term · EN",
        "baseline_en_phrase": "Measurement phrase · EN",
        "obs_spike_en": "Repeated spikes · EN",
        "obs_zero_en": "Synchronized zeros · EN",
        "obs_sync_en": "High synchrony · EN",
        "baseline_zh_core": "Core term · ZH",
        "baseline_zh_phrase": "Measurement phrase · ZH",
        "obs_spike_zh": "Repeated spikes · ZH",
        "obs_zero_zh": "Synchronized zeros · ZH",
        "obs_sync_zh": "High synchrony · ZH",
    }
    return labels[query_id]


def load_scope() -> pd.DataFrame:
    frames = []
    for chunk, overlap in CHUNKS:
        for model in MODELS:
            path = RESULTS / f"c{chunk}_o{overlap}" / model.replace("/", "__") / "scope_summary.csv"
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    scope = load_scope()
    m10 = scope[scope["extra_docs"].eq(10)].copy()
    m10["query_label"] = m10["query_id"].map(display_query)
    query_order = [
        "Core term · EN", "Measurement phrase · EN", "Repeated spikes · EN",
        "Synchronized zeros · EN", "High synchrony · EN",
        "Core term · ZH", "Measurement phrase · ZH", "Repeated spikes · ZH",
        "Synchronized zeros · ZH", "High synchrony · ZH",
    ]
    settings = [(model, chunk, overlap) for model in MODELS for chunk, overlap in CHUNKS]
    values = np.empty((len(query_order), len(settings)))
    for row, label in enumerate(query_order):
        for column, (model, chunk, overlap) in enumerate(settings):
            result = m10.loc[
                (m10["query_label"].eq(label))
                & (m10["model"].eq(model))
                & (m10["chunk_size"].eq(chunk))
                & (m10["chunk_overlap"].eq(overlap)),
                "iaea_priority_top10_mean",
            ]
            if len(result) != 1:
                raise ValueError(f"Expected one result for {label}, {model}, {chunk}/{overlap}")
            values[row, column] = result.iloc[0]

    fig, ax = plt.subplots(figsize=(5.0, 5.3), constrained_layout=True)
    image = ax.imshow(values, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_xlabel("encoder × character chunking")
    ax.set_ylabel("manual query formulation")
    ax.set_xticks(np.arange(6), ["800/80", "1200/120", "1500/150"] * 2, fontsize=7.5)
    ax.set_yticks(np.arange(10), query_order, fontsize=7.5)
    ax.axvline(2.5, color="#1f2937", lw=1.25)
    ax.axhline(4.5, color="white", lw=2.4)
    ax.text(1, -1.18, "Multilingual", ha="center", va="center", fontsize=8.5, fontweight="bold")
    ax.text(4, -1.18, "English-oriented", ha="center", va="center", fontsize=8.5, fontweight="bold")
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            color = "white" if values[row, column] > 0.56 else "#172033"
            ax.text(column, row, f"{values[row, column]:.2f}", ha="center", va="center", fontsize=6.8, color=color)
    colorbar = fig.colorbar(image, ax=ax, shrink=0.85, pad=0.02)
    colorbar.set_label("mean IAEA priority@10")

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig06_configuration_heatmap.pdf", bbox_inches="tight")


if __name__ == "__main__":
    main()

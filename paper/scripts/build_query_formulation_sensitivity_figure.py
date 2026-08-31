#!/usr/bin/env python3
"""Plot the technical-detail query formulation pilot without altering the paper."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "evidence" / "rag_results" / "query_formulation_sensitivity" / "technical_detail_query_pilot"
RESULTS = PILOT / "results"
OUT = PILOT / "technical_detail_query_priority_pilot"

MODELS = [
    ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "Multilingual MiniLM-L12"),
    ("sentence-transformers/all-MiniLM-L6-v2", "English MiniLM-L6"),
]
QUERIES = {
    "en": [
        ("baseline_en_phrase", "baseline phrase", "#4D4D4D", "--"),
        ("obs_spike_en", "spike-derived", "#D55E00", "-"),
        ("obs_zero_en", "zero-dropout-derived", "#0072B2", "-"),
        ("obs_sync_en", "synchrony-derived", "#009E73", "-"),
    ],
    "zh": [
        ("baseline_zh_phrase", "baseline phrase", "#4D4D4D", "--"),
        ("obs_spike_zh", "spike-derived", "#D55E00", "-"),
        ("obs_zero_zh", "zero-dropout-derived", "#0072B2", "-"),
        ("obs_sync_zh", "synchrony-derived", "#009E73", "-"),
    ],
}


def main() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.8, 6.6), sharex=True, sharey=True, constrained_layout=True)
    for row, (model, model_label) in enumerate(MODELS):
        slug = model.replace("/", "__")
        data = pd.read_csv(RESULTS / slug / "scope_summary.csv")
        for col, lang in enumerate(("en", "zh")):
            ax = axes[row, col]
            for query_id, label, color, style in QUERIES[lang]:
                subset = data[data["query_id"].eq(query_id)].sort_values("extra_docs")
                mean = subset["iaea_priority_top10_mean"]
                std = subset["iaea_priority_top10_std"].fillna(0)
                ax.plot(subset["extra_docs"], mean, label=label, color=color, linestyle=style,
                        marker="o", markersize=3.8, linewidth=2.0)
                ax.fill_between(subset["extra_docs"], mean - std, mean + std, color=color, alpha=0.10)
            ax.set_title(f"{model_label} — {'English' if lang == 'en' else 'Chinese'}")
            ax.grid(alpha=0.22)
            ax.set_ylim(-0.04, 1.04)
            if col == 0:
                ax.set_ylabel("IAEA priority@10")
            if row == 1:
                ax.set_xlabel("Supplementary documents admitted")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=300, bbox_inches="tight")
    print(f"Wrote {OUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()

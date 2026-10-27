"""Build a 2D grouped-bar view of the B2 stage-ablation grid (pool 01)."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIGURE_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIGURE_DIR.parents[1]
B2_ROOT = REPO_ROOT / "neutron anlyse" / "goldencard" / "experiments" / "B2"

KS = [3, 5, 8]
NS = [4, 8, 12]
CONFIGURATIONS = {
    "selector": ("with_training_selector", "#1F77B4"),
    "action": ("with_training_action", "#FF7F0E"),
    "both": ("with_training_both", "#2CA02C"),
}


def load_mf1(directory: str) -> list[float]:
    frame = pd.read_csv(B2_ROOT / directory / "summary_metrics.csv")
    frame = frame.loc[frame["pool_id"].astype(str).str.zfill(2) == "01"]
    indexed = frame.set_index(["retrieval_top_k", "fixed_example_count"])
    expected = {(k, n) for k in KS for n in NS}
    if set(indexed.index) != expected:
        raise ValueError(f"Unexpected B2 grid for {directory}")
    return [float(indexed.loc[(k, n), "action_macro_f1"]) for k in KS for n in NS]


def main() -> None:
    values = {name: load_mf1(directory) for name, (directory, _) in CONFIGURATIONS.items()}
    groups = np.arange(len(KS) * len(NS))
    width = 0.24
    offsets = [-width, 0.0, width]

    fig, ax = plt.subplots(figsize=(6.8, 4.8), constrained_layout=True)
    for offset, (name, (_, color)) in zip(offsets, CONFIGURATIONS.items()):
        bars = ax.bar(
            groups + offset,
            values[name],
            width=width,
            label=name,
            color=color,
            edgecolor="#333333",
            linewidth=0.35,
        )
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.012,
                f"{height:.3f}",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=6.3,
                color="#222222",
            )

    for boundary in (2.5, 5.5):
        ax.axvline(boundary, color="#B8B8B8", linewidth=0.9, linestyle="--", zorder=0)

    ax.set_ylim(0.0, 1.03)
    ax.set_yticks(np.arange(0.0, 1.01, 0.2))
    ax.set_ylabel("MF1")
    ax.set_xticks(groups, labels=[str(n) for _ in KS for n in NS])
    ax.set_xlabel("Number of fixed examples, n")
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        title="Example configuration",
        ncol=3,
        loc="upper left",
        frameon=True,
        fontsize=8,
        title_fontsize=8,
        handlelength=1.4,
        handletextpad=0.5,
        columnspacing=0.9,
        labelspacing=0.25,
        borderpad=0.35,
    )
    ax.set_title("B2 stage-ablation performance across K and n")

    for center, k in zip((1, 4, 7), KS):
        ax.text(center, -0.16, f"K={k}", ha="center", va="top", transform=ax.get_xaxis_transform())
    ax.text(4, -0.29, "Candidate evidence count", ha="center", va="top", transform=ax.get_xaxis_transform())

    for extension in ("png", "pdf"):
        fig.savefig(FIGURE_DIR / f"b2_kn_mf1_grouped_bars.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Plot B0 and B1 action metrics across candidate evidence counts K.

Each figure contains the B0 tag-voting baseline and six B1 conditions:
zero-shot plus fixed-example counts n={4,8,12,16,20}.  B0 is deliberately
shown in a contrasting warm colour; all B1 conditions use a single blue
colour family so that the figure reads as a progression of fixed-example
contexts rather than as unrelated methods.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIGURE_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIGURE_DIR.parents[1]
SUMMARY_ROOT = (
    REPO_ROOT
    / "neutron anlyse"
    / "goldencard"
    / "experiments"
    / "B1"
    / "with_training_examples"
    / "qwen3.8-flash"
)

KS = [3, 5, 8, 10]
NS = [4, 8, 12, 16, 20]

# Official frozen-60 values.  The historical B0 run-metric files contain
# earlier 120-case fields, so the plot uses the verified evaluation-60 values
# reported in the formal comparison table.
B0 = {
    "Acc": [0.2500, 0.2500, 0.2667, 0.2500],
    "MF1": [0.1667, 0.1744, 0.2079, 0.1974],
}
B1_ZERO_SHOT = {
    "Acc": [0.2333, 0.3167, 0.4333, 0.4833],
    "MF1": [0.2258, 0.2551, 0.3401, 0.3686],
}


def load_fixed_example_means(metric: str) -> dict[int, list[float]]:
    column = {
        "Acc": "action_accuracy_mean",
        "MF1": "action_macro_f1_mean",
    }[metric]
    values: dict[int, list[float]] = {}
    for n in NS:
        per_k = []
        for k in KS:
            path = SUMMARY_ROOT / f"top_k_{k:02d}" / "summary_by_example_count.csv"
            frame = pd.read_csv(path)
            row = frame.loc[frame["example_count"] == n]
            if len(row) != 1:
                raise ValueError(f"Expected one summary row for K={k}, n={n}")
            per_k.append(float(row.iloc[0][column]))
        values[n] = per_k
    return values


def draw(metric: str, filename: str) -> None:
    fixed = load_fixed_example_means(metric)
    fig, ax = plt.subplots(figsize=(7.0, 4.5), constrained_layout=True)

    ax.plot(
        KS,
        B0[metric],
        label="B0 tag voting",
        color="#C44E52",
        marker="s",
        linewidth=2.5,
        markersize=6,
        zorder=4,
    )

    b1_colors = plt.cm.Blues(np.linspace(0.48, 0.96, len(NS) + 1))
    ax.plot(
        KS,
        B1_ZERO_SHOT[metric],
        label="B1, $n=0$",
        color=b1_colors[0],
        marker="o",
        linewidth=2.0,
        markersize=5,
    )
    for color, n in zip(b1_colors[1:], NS):
        ax.plot(
            KS,
            fixed[n],
            label=fr"B1, $n={n}$",
            color=color,
            marker="o",
            linewidth=2.0,
            markersize=5,
        )

    ax.set_xticks(KS)
    ax.set_xlabel("Candidate evidence count, $K$")
    ax.set_ylabel(metric)
    ax.set_ylim(0.0, 1.05)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=2, loc="lower right", frameon=True, fontsize=9)
    ax.set_title(f"B0 and B1 performance across candidate evidence counts ({metric})")

    for extension in ("png", "pdf"):
        fig.savefig(FIGURE_DIR / f"{filename}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    draw("Acc", "b0_b1_k_acc_lines")
    draw("MF1", "b0_b1_k_mf1_lines")


if __name__ == "__main__":
    main()

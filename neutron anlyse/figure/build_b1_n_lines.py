"""Plot B1 fixed-example learning curves against the number of examples n."""

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
NS = [0, 4, 8, 12, 16, 20]

# Official frozen-60 B1 zero-shot results. Fixed-example values below are
# read from the corresponding three-pool summary CSV files.
ZERO_SHOT = {
    "Acc": {3: 0.2333, 5: 0.3167, 8: 0.4333, 10: 0.4833},
    "MF1": {3: 0.2258, 5: 0.2551, 8: 0.3401, 10: 0.3686},
}
B0 = {
    "Acc": [0.2500, 0.2500, 0.2667, 0.2500],
    "MF1": [0.1667, 0.1744, 0.2079, 0.1974],
}


def load(metric: str) -> tuple[dict[int, list[float]], dict[int, list[float]]]:
    mean_column, std_column = {
        "Acc": ("action_accuracy_mean", "action_accuracy_std"),
        "MF1": ("action_macro_f1_mean", "action_macro_f1_std"),
    }[metric]
    means: dict[int, list[float]] = {}
    stds: dict[int, list[float]] = {}
    for k in KS:
        frame = pd.read_csv(SUMMARY_ROOT / f"top_k_{k:02d}" / "summary_by_example_count.csv")
        fixed = frame.set_index("example_count")
        means[k] = [ZERO_SHOT[metric][k]] + [float(fixed.loc[n, mean_column]) for n in NS[1:]]
        stds[k] = [0.0] + [float(fixed.loc[n, std_column]) for n in NS[1:]]
    return means, stds


def draw(metric: str, filename: str) -> None:
    means, stds = load(metric)
    fig, ax = plt.subplots(figsize=(4.8, 4.8), constrained_layout=True)
    colors = plt.cm.viridis(np.linspace(0.12, 0.86, len(KS)))

    # B0 is a K-dependent non-LLM baseline, not an n=0 condition.  Show its
    # mean and across-K range as a horizontal reference rather than connecting
    # it to the B1 learning curves.
    b0_min, b0_max, b0_mean = min(B0[metric]), max(B0[metric]), float(np.mean(B0[metric]))
    ax.axhspan(
        b0_min,
        b0_max,
        color="#C44E52",
        alpha=0.16,
        label="B0 range across $K$",
        zorder=0,
    )
    ax.axhline(
        b0_mean,
        color="#C44E52",
        linestyle="--",
        linewidth=1.8,
        label="B0 mean",
        zorder=1,
    )

    for color, k in zip(colors, KS):
        # The zero-shot run has no cross-pool estimate, so its standard
        # deviation is encoded as zero.  Including it lets the band taper
        # continuously from n=0 to the first three-pool setting at n=4.
        fixed_ns = np.array(NS)
        fixed_means = np.array(means[k])
        fixed_stds = np.array(stds[k])
        ax.fill_between(
            fixed_ns,
            fixed_means - fixed_stds,
            fixed_means + fixed_stds,
            color=color,
            alpha=0.16,
            linewidth=0,
            zorder=2,
        )
        ax.plot(
            NS,
            means[k],
            label=fr"$K={k}$",
            color=color,
            marker="o",
            linewidth=2.2,
            markersize=5.5,
            zorder=3,
        )

    ax.axvline(0, color="#999999", linewidth=0.8, linestyle="--", zorder=0)
    ax.text(0.45, 0.055, "zero-shot", color="#666666", fontsize=8)
    ax.set_xticks(NS)
    ax.set_xlabel("Number of fixed examples, $n$")
    ax.set_ylabel(metric)
    ax.set_ylim(0.0, 1.05)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        title="Configuration",
        loc="lower right",
        frameon=True,
        framealpha=0.9,
        fontsize=8,
        title_fontsize=8,
    )
    ax.set_title(f"B1 fixed-example learning curves ({metric})", fontsize=11)

    for extension in ("png", "pdf"):
        fig.savefig(FIGURE_DIR / f"{filename}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    draw("Acc", "b1_n_acc_lines")
    draw("MF1", "b1_n_mf1_lines")


if __name__ == "__main__":
    main()

"""Build a 3D grouped-bar view of the B2 stage ablation grid (pool 01)."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


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


def load_mf1(directory: str) -> np.ndarray:
    path = B2_ROOT / directory / "summary_metrics.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[frame["pool_id"].astype(str).str.zfill(2) == "01"]
    indexed = frame.set_index(["retrieval_top_k", "fixed_example_count"])
    expected = {(k, n) for k in KS for n in NS}
    observed = set(indexed.index)
    if observed != expected:
        raise ValueError(f"Unexpected B2 grid in {path}: missing={expected - observed}, extra={observed - expected}")
    return np.array(
        [[float(indexed.loc[(k, n), "action_macro_f1"]) for n in NS] for k in KS]
    )


def main() -> None:
    values = {name: load_mf1(directory) for name, (directory, _) in CONFIGURATIONS.items()}

    fig = plt.figure(figsize=(7.0, 5.8), constrained_layout=True)
    ax = fig.add_subplot(111, projection="3d")

    # Each (K, n) cell contains three narrow bars offset along the K direction.
    dx, dy = 0.20, 0.56
    x_offsets = [0.05, 0.30, 0.55]
    for config_index, (name, (_, color)) in enumerate(CONFIGURATIONS.items()):
        for k_index, _ in enumerate(KS):
            for n_index, _ in enumerate(NS):
                ax.bar3d(
                    k_index + x_offsets[config_index],
                    n_index + 0.20,
                    0,
                    dx,
                    dy,
                    values[name][k_index, n_index],
                    color=color,
                    alpha=0.92,
                    shade=True,
                    edgecolor="#333333",
                    linewidth=0.25,
                )

    ax.set_xlim(0, len(KS))
    ax.set_ylim(0, len(NS))
    ax.set_zlim(0, 1.02)
    ax.set_xticks(np.arange(len(KS)) + 0.40, labels=KS)
    ax.set_yticks(np.arange(len(NS)) + 0.48, labels=NS)
    ax.set_zticks(np.arange(0.0, 1.01, 0.2))
    ax.set_xlabel("Candidate evidence count, K", labelpad=9)
    ax.set_ylabel("Number of fixed examples, n", labelpad=9)
    ax.set_zlabel("MF1", labelpad=9)
    ax.set_title("B2 stage-ablation performance (pool 01)", pad=16)
    ax.view_init(elev=25, azim=-58)

    legend_handles = [
        Patch(facecolor=color, edgecolor="#333333", label=name)
        for name, (_, color) in CONFIGURATIONS.items()
    ]
    ax.legend(handles=legend_handles, title="Example injection", loc="upper left", bbox_to_anchor=(0.02, 0.98))

    for extension in ("png", "pdf"):
        fig.savefig(FIGURE_DIR / f"b2_kn_mf1_3d_bars.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Build B1 fixed-example K--n heatmaps from frozen 60-case summaries."""

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


def read_summaries() -> pd.DataFrame:
    frames = []
    for k in KS:
        path = SUMMARY_ROOT / f"top_k_{k:02d}" / "summary_by_example_count.csv"
        frames.append(pd.read_csv(path))
    data = pd.concat(frames, ignore_index=True)
    expected = {(k, n) for k in KS for n in NS}
    observed = set(zip(data["retrieval_top_k"], data["example_count"]))
    if observed != expected:
        missing = expected - observed
        extra = observed - expected
        raise ValueError(f"Unexpected B1 summary grid; missing={missing}, extra={extra}")
    pair_f1_means = {}
    for k, n in expected:
        metric_paths = sorted(
            (SUMMARY_ROOT / f"top_k_{k:02d}" / f"n_{n:02d}").glob(
                "pool_*/b1_semantic_metrics.csv"
            )
        )
        if len(metric_paths) != 3:
            raise ValueError(f"Expected three pools for K={k}, n={n}; found {len(metric_paths)}")
        pair_f1_means[(k, n)] = float(
            np.mean(
                [
                    pd.read_csv(path).loc[0, "semantic_candidate_action_pair_f1_at_k"]
                    for path in metric_paths
                ]
            )
        )
    data["semantic_candidate_action_pair_f1_mean"] = [
        pair_f1_means[(k, n)]
        for k, n in zip(data["retrieval_top_k"], data["example_count"])
    ]
    return data


def grid(data: pd.DataFrame, column: str, scale: float = 1.0) -> np.ndarray:
    indexed = data.set_index(["retrieval_top_k", "example_count"])[column]
    return np.array([[indexed.loc[(k, n)] / scale for n in NS] for k in KS])


def draw_heatmap(
    values: np.ndarray,
    title: str,
    colorbar_label: str,
    filename: str,
    cmap: str,
    formatter,
) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.2), constrained_layout=True)
    image = ax.imshow(values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(NS)), labels=NS)
    ax.set_yticks(range(len(KS)), labels=KS)
    ax.set_xlabel("Number of fixed examples, $n$")
    ax.set_ylabel("Candidate evidence count, $K$")
    ax.set_title(title, pad=10)

    midpoint = (float(values.min()) + float(values.max())) / 2
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            color = "white" if value > midpoint else "black"
            ax.text(column, row, formatter(value), ha="center", va="center", color=color, fontsize=9)

    colorbar = fig.colorbar(image, ax=ax, shrink=0.92)
    colorbar.set_label(colorbar_label)
    for extension in ("png", "pdf"):
        fig.savefig(FIGURE_DIR / f"{filename}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data = read_summaries()
    draw_heatmap(
        grid(data, "action_accuracy_mean"),
        "B1 fixed-example action accuracy",
        "Acc",
        "b1_kn_acc_heatmap",
        "YlGnBu",
        lambda value: f"{value:.3f}",
    )
    draw_heatmap(
        grid(data, "semantic_candidate_action_pair_f1_mean"),
        "B1 fixed-example evidence-action pair quality",
        "SCA-F1@K",
        "b1_kn_sca_f1_heatmap",
        "YlGnBu",
        lambda value: f"{value:.3f}",
    )
    draw_heatmap(
        grid(data, "action_macro_f1_mean"),
        "B1 fixed-example macro F1",
        "MF1",
        "b1_kn_mf1_heatmap",
        "YlGnBu",
        lambda value: f"{value:.3f}",
    )
    draw_heatmap(
        grid(data, "total_tokens_mean", scale=1_000_000),
        "B1 fixed-example token cost",
        "Average total tokens per pool (M)",
        "b1_kn_token_cost_heatmap",
        "Oranges",
        lambda value: f"{value:.2f}",
    )


if __name__ == "__main__":
    main()

"""Create B0/B1/B2 radar comparisons for the shared K--n pool-01 grid.

The charts use only metrics that are defined for every configuration and whose
larger values are better.  B0 is read exclusively from the frozen-60 formal
evaluation directory; B1 and B2 use pool 01 so the fixed-example context is
held constant within each K--n panel.
"""

from __future__ import annotations

import csv
from math import pi
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
B0_ROOT = ROOT / "goldencard/experiments/B0/results/formal_evaluation_60"
B1_ROOT = ROOT / "goldencard/experiments/B1/with_training_examples/qwen3.8-flash"
B2_ROOT = ROOT / "goldencard/experiments/B2"
OUT = Path(__file__).resolve().parent

KS = (3, 5, 8)
NS = (4, 8, 12)
METRICS = (
    ("semantic_candidate_precision_at_k", "SP@K"),
    ("semantic_candidate_recall_at_k", "SR@K"),
    ("semantic_candidate_f1_at_k", "SF1@K"),
    ("semantic_candidate_action_pair_f1_at_k", "SCA-F1@K"),
    ("action_accuracy", "Acc"),
    ("action_macro_f1", "MF1"),
)

SERIES = (
    ("B0", "#111111", (0, (5, 2)), 2.60),
    ("B1", "#D62728", "solid", 2.45),
    ("B2-selector", "#7B2CBF", "solid", 2.45),
    ("B2-action", "#FF7F0E", "solid", 2.45),
    ("B2-both", "#00A65A", "solid", 3.00),
)


def read_one(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle))


def merged_metrics(semantic_path: Path, run_path: Path) -> dict[str, float]:
    semantic = read_one(semantic_path)
    run = read_one(run_path)
    merged = {**semantic, **run}
    values: dict[str, float] = {}
    for key, _ in METRICS:
        source_key = "macro_f1" if key == "action_macro_f1" and key not in merged else key
        values[key] = float(merged[source_key])
    return values


def read_b0(k: int) -> dict[str, float]:
    folder = B0_ROOT / f"top_k_{k:02d}"
    return merged_metrics(folder / "b0_semantic_metrics.csv", folder / "b0_run_metrics.csv")


def read_b1(k: int, n: int) -> dict[str, float]:
    folder = B1_ROOT / f"top_k_{k:02d}" / f"n_{n:02d}" / "pool_01"
    return merged_metrics(folder / "b1_semantic_metrics.csv", folder / "b1_run_metrics.csv")


def read_b2(stage: str, k: int, n: int) -> dict[str, float]:
    folder = B2_ROOT / f"with_training_{stage}" / "qwen3.8-flash" / f"top_k_{k:02d}" / f"n_{n:02d}" / "pool_01"
    return merged_metrics(folder / "b2_semantic_metrics.csv", folder / "b2_run_metrics.csv")


def panel_data(k: int, n: int) -> dict[str, dict[str, float]]:
    return {
        "B0": read_b0(k),
        "B1": read_b1(k, n),
        "B2-selector": read_b2("selector", k, n),
        "B2-action": read_b2("action", k, n),
        "B2-both": read_b2("both", k, n),
    }


ANGLES = np.linspace(pi / 2, pi / 2 - 2 * pi, len(METRICS), endpoint=False)
LABELS = [label for _, label in METRICS]
RINGS = (0.25, 0.50, 0.75, 1.00)


def points(radii: np.ndarray | list[float]) -> np.ndarray:
    radii = np.asarray(radii, dtype=float)
    return np.column_stack((radii * np.cos(ANGLES), radii * np.sin(ANGLES)))


def draw_radar(axis, values_by_series: dict[str, dict[str, float]], title: str) -> None:
    """Draw a six-sided spider chart with a globally fixed 0--1 scale."""
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_title(title, fontsize=15, fontweight="bold", pad=13)

    # Hexagonal reference rings: the scale is deliberately identical in all panels.
    for ring in RINGS:
        ring_points = points(np.full(len(METRICS), ring))
        ring_points = np.vstack((ring_points, ring_points[0]))
        axis.plot(ring_points[:, 0], ring_points[:, 1], color="#CBD5E1", linewidth=0.7, zorder=0)
    for angle in ANGLES:
        axis.plot((0, np.cos(angle)), (0, np.sin(angle)), color="#CBD5E1", linewidth=0.7, zorder=0)

    for angle, label in zip(ANGLES, LABELS):
        label_radius = 1.06 if np.sin(angle) < -0.65 else 1.14
        x, y = label_radius * np.cos(angle), label_radius * np.sin(angle)
        horizontal = "center" if abs(x) < 0.2 else ("left" if x > 0 else "right")
        vertical = "bottom" if y > 0.65 else ("top" if y < -0.65 else "center")
        axis.text(x, y, label, ha=horizontal, va=vertical, fontsize=12.5)

    # One unobtrusive radial reference makes the common normalization explicit.
    axis.text(0.02, 0.51, "0.50", fontsize=10, color="#6B7280")
    axis.text(0.02, 1.01, "1.00", fontsize=10, color="#6B7280")

    for index, (label, color, linestyle, linewidth) in enumerate(SERIES):
        radii = [values_by_series[label][key] for key, _ in METRICS]
        curve = points(radii)
        curve = np.vstack((curve, curve[0]))
        axis.plot(
            curve[:, 0],
            curve[:, 1],
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            zorder=4 if label == "B0" else 2 + index,
        )
        axis.fill(curve[:, 0], curve[:, 1], color=color, alpha=0.045, zorder=1)

    axis.set_xlim(-1.18, 1.18)
    axis.set_ylim(-1.15, 1.20)


def save_individual_charts() -> None:
    for k in KS:
        for n in NS:
            figure, axis = plt.subplots(figsize=(6.4, 6.7))
            draw_radar(axis, panel_data(k, n), rf"$K={k},\ n={n}$")
            handles = [
                Line2D((0,), (0,), color=color, linewidth=linewidth, linestyle=linestyle, label=label)
                for label, color, linestyle, linewidth in SERIES
            ]
            figure.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9)
            figure.subplots_adjust(bottom=0.14, top=0.88)
            stem = OUT / f"b0_b1_b2_radar_k{k:02d}_n{n:02d}"
            figure.savefig(stem.with_suffix(".png"), dpi=260, bbox_inches="tight")
            figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
            plt.close(figure)


def save_contact_sheet() -> None:
    figure, axes = plt.subplots(3, 3, figsize=(12.8, 13.3))
    for row, k in enumerate(KS):
        for col, n in enumerate(NS):
            draw_radar(axes[row, col], panel_data(k, n), rf"$K={k},\ n={n}$")

    handles = [
        Line2D((0,), (0,), color=color, linewidth=linewidth, linestyle=linestyle, label=label)
        for label, color, linestyle, linewidth in SERIES
    ]
    figure.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=12)
    figure.suptitle("B0, B1, and B2 multi-metric radar comparison", fontsize=20, fontweight="bold", y=0.985)
    figure.subplots_adjust(left=0.02, right=0.98, top=0.910, bottom=0.06, wspace=0.03, hspace=0.20)
    stem = OUT / "b0_b1_b2_radar_grid_pool_01"
    figure.savefig(stem.with_suffix(".png"), dpi=260, bbox_inches="tight")
    figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    save_individual_charts()
    save_contact_sheet()

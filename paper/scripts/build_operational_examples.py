#!/usr/bin/env python3
"""Build a data-grounded companion figure for the operational definitions.

The figure intentionally uses only the checked-in representative 5,000-row
raw-record excerpt. It is therefore an explanation of what the deterministic
rules calculate, not an estimate for the complete operational archive and not
a fault-label figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator
from matplotlib.transforms import Bbox


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "evidence" / "data_samples" / "A1_1_head5000.csv"
OUT = ROOT / "paper" / "figs"

INK = "#17324D"
MUTED = "#657B8D"
BLUE = "#2878B5"
TEAL = "#148F86"
ORANGE = "#E59A2E"
RED = "#CC5B5B"


def short_channel(name: str) -> str:
    return name.split("RIC")[-1].replace("MA_VER", "")


def rolling_probe(series: pd.Series, window: int = 31) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return the local median, rolling median absolute deviation, and mask."""
    median = series.rolling(window, center=True, min_periods=window).median()
    deviation = (series - median).abs().rolling(window, center=True, min_periods=window).median()
    value_range = series.max() - series.min()
    mask = ((series - median).abs() > 5 * deviation) & ((series - median).abs() > 0.05 * value_range)
    return median, deviation, mask.fillna(False)


def best_lag(x: np.ndarray, y: np.ndarray, max_lag: int = 30) -> tuple[np.ndarray, np.ndarray]:
    lags = np.arange(-max_lag, max_lag + 1)
    values = []
    for lag in lags:
        if lag < 0:
            a, b = x[:lag], y[-lag:]
        elif lag > 0:
            a, b = x[lag:], y[:-lag]
        else:
            a, b = x, y
        values.append(np.corrcoef(a, b)[0, 1])
    return lags, np.asarray(values)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    raw = pd.read_csv(SAMPLE).iloc[::-1].reset_index(drop=True)
    data = raw.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")

    # Select the most pronounced rule-positive departure mechanically, rather
    # than hand-picking a visually appealing segment. This guarantees that the
    # orange reference line and red marker mean the same thing in the figure.
    probe_col = data.columns[2]
    probe = data[probe_col]
    median, deviation, candidates = rolling_probe(probe)
    residual = ((probe - median).abs() / (probe.max() - probe.min())).fillna(0.0)
    center = int(residual[candidates].idxmax()) if candidates.any() else int(residual.idxmax())
    start, stop = max(0, center - 60), min(len(data), center + 61)
    local = pd.DataFrame({"x": probe, "median": median, "mad": deviation, "candidate": candidates}).iloc[start:stop]

    # Strong (but not near-redundant) co-movement in this same raw excerpt.
    x_col, y_col = data.columns[1], data.columns[2]
    x, y = data[x_col].to_numpy(), data[y_col].to_numpy()
    corr = float(np.corrcoef(x, y)[0, 1])
    lags, lag_corr = best_lag(x, y)
    peak = int(np.argmax(np.abs(lag_corr)))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5})
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.65), constrained_layout=True)
    fig.patch.set_facecolor("white")

    # (a) True local record and the quantities in the spike rule.
    ax = axes[0]
    t = np.arange(start, stop)
    ax.plot(t, local["x"], color=INK, lw=1.35, label="raw current")
    ax.plot(t, local["median"], color=TEAL, lw=1.35, label="31-sample median")
    ax.fill_between(t, (local["median"] - 5 * local["mad"]).to_numpy(),
                    (local["median"] + 5 * local["mad"]).to_numpy(),
                    color=TEAL, alpha=0.15, label=r"adaptive $\pm5d_{t,c}$")
    flagged = local["candidate"].to_numpy()
    if flagged.any():
        ax.scatter(t[flagged], local.loc[flagged, "x"], s=24, color=RED, zorder=4,
                   label="rule-positive sample")
    ax.axvline(center, color=ORANGE, lw=1.0, ls=(0, (3, 2)), label="selected rule-positive sample")
    ax.scatter([center], [probe.iloc[center]], s=44, color=RED, edgecolor="white", linewidth=.8, zorder=5)
    ax.set_title("Local robust-deviation probe", loc="left", color=INK, fontweight="bold")
    ax.set_xlabel("sample index in representative excerpt")
    ax.set_ylabel(f"current ({short_channel(probe_col)})")
    ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.grid(axis="y", alpha=.20)
    ax.legend(frameon=False, fontsize=6.8, loc="lower left", ncol=2)

    # (b) Actual 5,000-point pair relationship.
    ax = axes[1]
    bins = ax.hexbin(x, y, gridsize=42, mincnt=1, cmap="YlGnBu", linewidths=0)
    slope, intercept = np.polyfit(x, y, 1)
    xx = np.linspace(x.min(), x.max(), 100)
    ax.plot(xx, slope * xx + intercept, color=ORANGE, lw=1.4)
    ax.text(.04, .95, rf"$r_{{ij}}={corr:.3f}$", transform=ax.transAxes, va="top",
            color=INK, fontweight="bold", fontsize=10)
    ax.text(.04, .86, "all 5,000 sample pairs", transform=ax.transAxes, va="top", color=MUTED, fontsize=7.2)
    ax.set_title("Pearson co-movement", loc="left", color=INK, fontweight="bold")
    ax.set_xlabel(f"current ({short_channel(x_col)})")
    ax.set_ylabel(f"current ({short_channel(y_col)})")
    ax.xaxis.set_major_locator(MaxNLocator(4)); ax.yaxis.set_major_locator(MaxNLocator(4))
    cbar = fig.colorbar(bins, ax=ax, pad=.01, fraction=.046)
    cbar.ax.tick_params(labelsize=6.5)
    cbar.set_label("local density", fontsize=6.8, color=MUTED)

    # (c) Lag scan for the same pair: timing association, not causality.
    ax = axes[2]
    ax.plot(lags, lag_corr, color=BLUE, lw=1.8)
    ax.fill_between(lags, lag_corr, np.min(lag_corr) - .005, color=BLUE, alpha=.12)
    ax.axvline(0, color=MUTED, lw=.8, ls="--")
    ax.scatter(lags[peak], lag_corr[peak], color=ORANGE, s=30, zorder=3)
    ax.annotate(f"peak at {lags[peak]:+d} samples\n$r={lag_corr[peak]:.3f}$",
                xy=(lags[peak], lag_corr[peak]), xytext=(.61, .22), textcoords="axes fraction",
                color=INK, fontsize=7.8,
                arrowprops=dict(arrowstyle="-", color=ORANGE, lw=.9))
    ax.set_title("Lead--lag scan", loc="left", color=INK, fontweight="bold")
    ax.set_xlabel("relative lag (samples)")
    ax.set_ylabel("Pearson correlation")
    ax.set_xticks([-30, -15, 0, 15, 30])
    ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.grid(alpha=.20)
    ax.text(.02, .04, "Timing association only; not causal direction.", transform=ax.transAxes,
            fontsize=6.8, color=MUTED)

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.2, colors=MUTED)

    # Keep a composite preview for working purposes, but export each panel as a
    # separate one-column figure. In the manuscript each image then sits next
    # to the definition it explains instead of forming a page-wide interruption.
    fig.savefig(OUT / "fig3_operational_examples.pdf", bbox_inches="tight")
    fig.savefig(OUT / "fig3_operational_examples.png", dpi=320, bbox_inches="tight")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    panel_specs = [
        ("fig3_spike_rule_example", axes[0].get_tightbbox(renderer), [axes[0]]),
        ("fig4_pearson_example", Bbox.union([axes[1].get_tightbbox(renderer), cbar.ax.get_tightbbox(renderer)]), [axes[1], cbar.ax]),
        ("fig5_lag_example", axes[2].get_tightbbox(renderer), [axes[2]]),
    ]
    all_axes = [*axes, cbar.ax]
    for name, box, visible_axes in panel_specs:
        # Prevent adjacent panels from leaking into a cropped export.
        for panel in all_axes:
            panel.set_visible(panel in visible_axes)
        # bbox coordinates are display pixels; savefig expects inches.
        box_inches = box.transformed(fig.dpi_scale_trans.inverted()).expanded(1.01, 1.12)
        fig.savefig(OUT / f"{name}.pdf", bbox_inches=box_inches, pad_inches=.02)
        fig.savefig(OUT / f"{name}.png", dpi=320, bbox_inches=box_inches, pad_inches=.02)
    for panel in all_axes:
        panel.set_visible(True)
    print("Wrote one-column panels:", ", ".join(name for name, _, _ in panel_specs))


if __name__ == "__main__":
    main()

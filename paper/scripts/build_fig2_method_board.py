#!/usr/bin/env python3
"""Render Fig. 2: a compact, data-grounded observation-method board.

The layout deliberately favours four large probe cards over a dense catalogue
of tools. Each card includes a miniature artifact computed from a representative
archived record or its derived workflow state, so the visual remains a method
figure rather than an illustrative mock-up.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
OUT = PAPER / "figs"
SAMPLE = ROOT / "evidence" / "data_samples" / "A1_1_head5000.csv"
STATE = ROOT / "evidence" / "case_A1_1" / "state.json"
REPORT = ROOT / "evidence" / "case_A1_1" / "A1_1_sorted_进阶全局工况报告_数据快照.json"

INK = "#102B46"
MUTED = "#667C8F"
PANEL = "#F8FAFC"
EDGE = "#C7D5DF"
MORPH = "#129D88"
EVENT = "#E9A23B"
EXTREME = "#D45E5E"
SYNC = "#3487C6"
VIOLET = "#7C68B7"


def card(ax, x, y, w, h, face="white", edge=EDGE, lw=1.1, z=1):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.055",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=z,
    ))


def arrow(ax, start, end, color=INK, width=1.35, rad=0.0, dashed=False, z=2):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=13, linewidth=width,
        color=color, linestyle=(0, (3, 2)) if dashed else "solid",
        connectionstyle=f"arc3,rad={rad}", shrinkA=3, shrinkB=6, zorder=z,
    ))


def title(ax, x, y, label, color):
    ax.add_patch(Circle((x, y - .02), .075, facecolor=color, edgecolor="none", zorder=6))
    ax.text(x + .16, y, label, va="center", fontsize=10.2, color=INK,
            fontweight="bold", zorder=6)


def inset(fig, rect):
    ax = fig.add_axes(rect)
    ax.set_facecolor("none")
    return ax


def normalized(series):
    lo, hi = np.nanpercentile(series, [2, 98])
    return np.clip((series - lo) / (hi - lo + 1e-12), 0, 1)


def main():
    OUT.mkdir(exist_ok=True)
    raw = pd.read_csv(SAMPLE)
    values = raw.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    with STATE.open(encoding="utf-8") as f:
        state = json.load(f)
    with REPORT.open(encoding="utf-8") as f:
        report = json.load(f)

    profile = state["knowledge_graph"]["initial_data_stats"]
    corr = values.corr().to_numpy()
    zero_counts = [len(item["alerts"].get("isolated_zeros", [])) for item in report]
    spike_counts = [item["alerts"].get("spikes_summary", {}).get("total_count", 0) for item in report]
    snapshot = values.iloc[min(1600, len(values) - 1)].to_numpy(dtype=float)
    snapshot = normalized(snapshot)

    fig = plt.figure(figsize=(14.5, 6.8), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 14.5); ax.set_ylim(0, 6.8); ax.axis("off")

    # Title rail.
    ax.text(.42, 6.43, "From multichannel record to auditable observation packet",
            fontsize=19, fontweight="bold", color=INK, va="bottom")
    ax.text(.42, 6.14,
            "Four registered probes turn one active record into traceable signal evidence before retrieval or interpretation.",
            fontsize=10.3, color=MUTED, va="bottom")
    ax.plot([.42, 14.08], [6.00, 6.00], color="#BBCBD6", linewidth=.9)

    # Zone boundaries.
    card(ax, .42, .72, 3.14, 4.92, face="#F8FBFD", edge="#BFD0DC", lw=1.15)
    card(ax, 3.84, .72, 6.76, 4.92, face="#FCFDFE", edge="#BFD0DC", lw=1.15)
    card(ax, 10.88, .72, 3.20, 4.92, face="#F8FBFD", edge="#BFD0DC", lw=1.15)
    ax.text(.66, 5.37, "A  RAW MULTICHANNEL RECORD", fontsize=10.4, color=SYNC, fontweight="bold")
    ax.text(4.08, 5.37, "B  REGISTERED OBSERVATION PROBES", fontsize=10.4, color=MORPH, fontweight="bold")
    ax.text(11.12, 5.37, "C  AUDITABLE ARTIFACTS", fontsize=10.4, color=VIOLET, fontweight="bold")

    # A: profile strip and real seven-channel trace block.
    card(ax, .68, 4.38, 2.62, .62, face="#EAF3F9", edge="#AFC9DA", lw=.9)
    ax.text(.88, 4.78, "PROFILE / WORKSPACE INITIALIZATION", fontsize=8.3, color=SYNC, fontweight="bold")
    ax.text(.88, 4.55, f"{profile['rows']:,} rows  ·  7 channels  ·  1 s", fontsize=9.6, color=INK, fontweight="bold")
    trace = inset(fig, [.063, .205, .17, .39])
    take = np.linspace(0, min(1800, len(values) - 1), 430).astype(int)
    for i, col in enumerate(values.columns):
        y = (6 - i) + .66 * normalized(values[col].to_numpy(dtype=float)[take])
        trace.plot(np.arange(len(take)), y, color=EVENT if i in (0, 4) else SYNC, linewidth=.75)
        trace.text(-18, 6 - i + .30, f"C{i+1}", fontsize=6.5, color=MUTED, ha="right", va="center")
    trace.set_xlim(-28, len(take)); trace.set_ylim(-.15, 7.0); trace.axis("off")
    ax.text(.82, 1.12, "representative 7-channel window", fontsize=8.5, color=INK, fontweight="bold")
    ax.text(.82, .93, "display-normalized; source values preserved in the workspace", fontsize=7.1, color=MUTED)

    # B: central engine.
    cx, cy, r = 7.20, 3.19, .88
    angles = np.linspace(0, 2*np.pi, 7)[:-1] + np.pi/6
    points = np.column_stack((cx + r*np.cos(angles), cy + r*np.sin(angles)))
    ax.add_patch(Polygon(points, closed=True, facecolor=INK, edgecolor="#092035", linewidth=1.4, zorder=5))
    ax.text(cx, cy+.23, "OBSERVATION", color="white", fontsize=11.1, ha="center", fontweight="bold", zorder=7)
    ax.text(cx, cy-.02, "ENGINE", color="white", fontsize=11.1, ha="center", fontweight="bold", zorder=7)
    ax.plot([cx-.47, cx+.47], [cy-.18, cy-.18], color="#68A9BB", linewidth=.8, zorder=7)
    ax.text(cx, cy-.43, "state.json", color="#B8DCE3", fontsize=8.1, ha="center", fontweight="bold", zorder=7)
    ax.text(cx, cy-.60, "active record + probe log", color="#D8E8EE", fontsize=6.8, ha="center", zorder=7)

    # Four satellite cards as suggested by the reference layout.
    cards = {
        "morph": (4.18, 3.98, 2.15, 1.08, "MORPHOLOGY", "variability + roles", MORPH),
        "event": (8.08, 3.98, 2.15, 1.08, "EVENTS", f"{sum(spike_counts)} spike episodes", EVENT),
        "extreme": (4.18, 1.25, 2.15, 1.08, "EXTREMES", "time-localized bounds", EXTREME),
        "sync": (8.08, 1.25, 2.15, 1.08, "SYNCHRONY", "co-movement + lag", SYNC),
    }
    for key, (x, y, w, h, name, subtitle, color) in cards.items():
        card(ax, x, y, w, h, edge=color, lw=1.35, z=4)
        title(ax, x+.23, y+h-.23, name, color)
        ax.text(x+.19, y+.16, subtitle, fontsize=7.8, color=MUTED, zorder=6)
        arrow(ax, (cx, cy), (x+w/2, y+h/2), color=color, width=1.1, z=3)

    # Real miniature artifacts, rendered at a larger scale than v1.
    morph_ax = inset(fig, [.316, .600, .108, .074])
    for idx, col in enumerate(values.columns[:3]):
        series = normalized(values[col].to_numpy(dtype=float)[take])
        morph_ax.plot(np.arange(len(take)), idx + .58*series, color=MORPH, alpha=.5+.15*idx, linewidth=.72)
    morph_ax.set_xlim(0, len(take)); morph_ax.set_ylim(-.1, 3); morph_ax.axis("off")

    event_ax = inset(fig, [.586, .604, .105, .068])
    for i, n in enumerate(zero_counts):
        loc = np.linspace(.05, .95, min(n, 15))
        event_ax.vlines(loc, i-.25, i+.25, color=EVENT, linewidth=.75)
    event_ax.set_xlim(0, 1); event_ax.set_ylim(-.4, 6.4); event_ax.axis("off")

    extreme_ax = inset(fig, [.316, .201, .108, .064])
    extreme_ax.bar(np.arange(7), spike_counts, color=EXTREME, alpha=.85, width=.6)
    extreme_ax.set_xticks([]); extreme_ax.set_yticks([])
    for spine in extreme_ax.spines.values(): spine.set_visible(False)

    sync_ax = inset(fig, [.584, .198, .111, .081])
    sync_ax.imshow(corr, cmap="PuBuGn", vmin=.85, vmax=1.0, interpolation="nearest")
    sync_ax.set_xticks([]); sync_ax.set_yticks([])
    for spine in sync_ax.spines.values(): spine.set_visible(False)

    # Main data-flow labels.
    arrow(ax, (3.58, 3.19), (6.25, 3.19), color=INK, width=1.55)
    ax.text(4.38, 3.42, "one active record", fontsize=7.9, color=MUTED, fontweight="bold")
    arrow(ax, (8.14, 3.19), (11.24, 4.17), color=INK, width=1.55)
    ax.text(9.02, 4.03, "registered outputs", fontsize=7.9, color=MUTED, fontweight="bold")

    # C: audit packet and compressed retrieval interface.
    card(ax, 11.28, 3.46, 2.40, 1.30, face="#F4F1FB", edge="#B7AED2", lw=1.2, z=4)
    ax.text(11.52, 4.49, "OBSERVATION PACKET", fontsize=10.1, color=VIOLET, fontweight="bold", zorder=6)
    for i, text in enumerate(("scope + active record", "probe log + parameters", "events + relations", "data-health + uncertainty")):
        ax.text(11.57, 4.20 - .21*i, f"•  {text}", fontsize=7.9, color=INK, zorder=6)
    card(ax, 11.52, 1.38, 2.15, 1.16, face="#EBF6F2", edge="#9CCDC1", lw=1.2, z=4)
    ax.text(11.76, 2.28, "ALERT SUMMARY", fontsize=10.0, color=MORPH, fontweight="bold", zorder=6)
    for i, text in enumerate(("health · morphology", "spikes · zeros · lag", "co-movement · snapshot")):
        ax.text(11.76, 2.02 - .22*i, text, fontsize=7.7, color=INK, zorder=6)
    arrow(ax, (12.48, 3.46), (12.58, 2.54), color=MORPH, width=1.35)
    ax.text(12.75, 3.02, "controlled\ncompression", fontsize=7.1, color=MORPH, va="center")
    arrow(ax, (12.63, 1.38), (13.82, .91), color=MORPH, width=1.0, dashed=True)
    ax.text(13.12, .80, "retrieval-facing", fontsize=6.8, color=MUTED, fontweight="bold")

    # Short guardrail strip: enough to preserve the core methodological claim.
    card(ax, 3.98, .80, 6.38, .34, face="#EDF3F7", edge="#C4D3DD", lw=.8, z=2)
    rails = (("STATE OWNERSHIP", "active record", SYNC),
             ("ACTION BOUNDARY", "registered probes", MORPH),
             ("OUTPUT BOUNDARY", "not a fault label", EXTREME))
    x = 4.28
    for head, detail, color in rails:
        ax.add_patch(Circle((x, .97), .05, facecolor=color, edgecolor="none", zorder=5))
        ax.text(x+.11, 1.00, head, fontsize=6.5, color=INK, fontweight="bold", va="center", zorder=5)
        ax.text(x+.11, .87, detail, fontsize=6.2, color=MUTED, va="center", zorder=5)
        x += 2.07

    ax.text(.44, .34,
            "Microvisuals are derived from a representative archived record and its workflow artifacts; they illustrate probe outputs, not confirmed fault labels.",
            fontsize=7.0, color=MUTED)

    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig2_method_board.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=.03)


if __name__ == "__main__":
    main()

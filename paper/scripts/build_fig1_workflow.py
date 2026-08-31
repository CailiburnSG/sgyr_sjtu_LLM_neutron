#!/usr/bin/env python3
"""Render Fig. 1: an evidence-constrained diagnostic-assistance architecture."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figs"

INK = "#18324A"
MUTED = "#59738A"
TEAL = "#147D91"
DATA = "#EAF1F6"
OBSERVE = "#E5F2F0"
EVIDENCE = "#EAF0FA"
GOVERN = "#F9F0DE"
EVAL = "#F3F5F7"
BOUNDARY = "#F7FAFC"


def panel(ax, x, y, w, h, title, body, color, dashed=False, title_size=10.5, body_size=8.7):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.018,rounding_size=0.06",
        linewidth=1.45,
        edgecolor=INK,
        facecolor=color,
        linestyle=(0, (4, 3)) if dashed else "solid",
        zorder=3,
    ))
    ax.text(x + 0.17, y + h - 0.22, title, ha="left", va="top", color=INK,
            fontsize=title_size, fontweight="bold", zorder=4)
    ax.text(x + 0.17, y + h - 0.55, body, ha="left", va="top", color=MUTED,
            fontsize=body_size, linespacing=1.35, zorder=4)


def arrow(ax, start, end, *, dashed=False, rad=0.0, color=INK, width=1.5):
    ax.add_patch(FancyArrowPatch(
        start, end,
        arrowstyle="-|>", mutation_scale=12, linewidth=width, color=color,
        linestyle=(0, (4, 3)) if dashed else "solid",
        connectionstyle=f"arc3,rad={rad}", shrinkA=6, shrinkB=7, zorder=2,
    ))


def label(ax, x, y, text, *, color=TEAL):
    ax.text(x, y, text, ha="left", va="center", fontsize=8.1,
            fontweight="bold", color=color, zorder=5)


def main():
    OUT.mkdir(exist_ok=True)
    # A compact canvas keeps labels readable after placement in a single-column manuscript.
    fig, ax = plt.subplots(figsize=(10.0, 6.0))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    ax.text(0.42, 6.80, "Evidence-constrained diagnostic assistance",
            fontsize=16.5, fontweight="bold", color=INK, va="bottom")
    ax.text(0.42, 6.46,
            "A report-centered architecture that separates observed signal events, documentary evidence, and engineering judgment.",
            fontsize=9.5, color=MUTED, va="bottom")
    ax.plot([0.42, 12.58], [6.27, 6.27], color="#C8D4DD", linewidth=0.9)

    panel(ax, 3.85, 5.23, 5.30, 0.72,
          "Engineering review and decision authority (outside automation)",
          "Checks data context, evidence support, and any physical interpretation before use.",
          GOVERN, dashed=True, title_size=10.2, body_size=8.1)

    ax.add_patch(FancyBboxPatch(
        (0.40, 0.48), 12.18, 4.43,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.0, edgecolor="#B8C7D2", facecolor=BOUNDARY,
        linestyle=(0, (5, 4)), zorder=0,
    ))
    label(ax, 0.63, 4.67, "AUTOMATED, EVIDENCE-CONSTRAINED WORKSPACE")

    panel(ax, 0.72, 2.88, 2.20, 1.23,
          "Raw measurement input", "Unlabeled neutron-current CSV\ntime series + channel identifiers", DATA)
    panel(ax, 1.15, 0.94, 2.88, 1.45,
          "Controlled observation layer", "Deterministic probes\nhealth · morphology · anomalies · lag", OBSERVE)
    panel(ax, 4.18, 2.48, 4.35, 1.86,
          "Auditable condition report", "Observed signal events and structured alert summary\n\nInterface between measurement analysis and manual retrieval\nNot a confirmed fault diagnosis", OBSERVE,
          title_size=12.0, body_size=9.0)
    panel(ax, 9.98, 3.58, 2.02, 1.12,
          "Evidence sources", "IAEA core + same-domain\nsupplementary manuals", EVIDENCE,
          title_size=10.1, body_size=7.9)
    panel(ax, 9.07, 1.32, 3.12, 1.58,
          "Evidence retrieval layer", "Terminology-rich query · source policy\nretrieved passages · traceable citations", EVIDENCE)
    panel(ax, 4.48, 0.82, 3.98, 0.93,
          "Retrieval robustness evaluation", "Corpus expansion · bilingual queries · chunking · strict/document relevance", EVAL,
          title_size=10.2, body_size=8.0)

    arrow(ax, (1.82, 2.88), (2.40, 2.39), rad=-0.18)
    arrow(ax, (4.03, 1.74), (4.18, 2.78), rad=-0.15)
    arrow(ax, (8.53, 3.20), (9.07, 2.28), rad=-0.15)
    arrow(ax, (10.99, 3.58), (10.77, 2.90), rad=0.08)
    arrow(ax, (6.42, 2.48), (6.65, 1.75), dashed=True, color=MUTED)
    arrow(ax, (9.07, 1.86), (8.46, 1.32), dashed=True, rad=0.10, color=MUTED)
    arrow(ax, (6.36, 4.34), (6.50, 5.23), dashed=True, color=INK)
    arrow(ax, (10.52, 2.90), (8.90, 5.23), dashed=True, rad=-0.18, color=INK)

    label(ax, 2.08, 2.68, "parse + profile", color=MUTED)
    label(ax, 3.78, 2.16, "auditable observations", color=MUTED)
    label(ax, 8.12, 2.76, "retrieval intent", color=MUTED)
    label(ax, 10.95, 3.18, "manual evidence", color=MUTED)
    label(ax, 6.67, 4.80, "review boundary", color=MUTED)

    ax.plot([0.72, 1.16], [0.70, 0.70], color=INK, linewidth=1.45)
    ax.text(1.27, 0.70, "automated artifact flow", va="center", fontsize=7.8, color=MUTED)
    ax.plot([3.16, 3.60], [0.70, 0.70], color=INK, linewidth=1.45, linestyle=(0, (4, 3)))
    ax.text(3.71, 0.70, "evaluation / human-governance link", va="center", fontsize=7.8, color=MUTED)

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig1_overview.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.03)


if __name__ == "__main__":
    main()

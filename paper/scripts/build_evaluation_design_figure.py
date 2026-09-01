"""Create the Chapter 3 evaluation-design map from the recorded protocols."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper" / "figs"

INK = "#18324B"
MUTED = "#5B6B7A"
CORE = "#2B6CB0"
SUPP = "#94A3B8"
P0 = "#0F8B7E"
HIST = "#7056A6"
WORD = "#D97706"
PANEL = "#F7FAFC"
LINE = "#CBD5E1"


def card(ax, x, y, w, h, title, subtitle, bullets, colour):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=LINE, fc="white", lw=1.0))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.12), w, 0.12,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=colour, fc=colour, lw=0))
    ax.text(x + 0.025, y + h - 0.06, title, va="center", ha="left",
            fontsize=9.5, fontweight="bold", color="white")
    ax.text(x + 0.025, y + h - 0.16, subtitle, va="top", ha="left",
            fontsize=7.2, color=MUTED, fontweight="bold")
    for i, bullet in enumerate(bullets):
        ax.text(x + 0.034, y + h - 0.245 - i * 0.060, "•", color=colour,
                va="center", ha="left", fontsize=9)
        ax.text(x + 0.06, y + h - 0.245 - i * 0.060, bullet, color=INK,
                va="center", ha="left", fontsize=7.25)


def arrow(ax, x1, y1, x2, y2, text):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=12, lw=1.2, color="#64748B"))
    ax.text((x1 + x2) / 2, max(y1, y2) + 0.035, text, ha="center", va="bottom",
            fontsize=7, color=MUTED)


def main():
    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
    fig, ax = plt.subplots(figsize=(12.8, 5.3))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.02, 0.965, "Retrieval evaluation design", fontsize=15, fontweight="bold",
            color=INK, ha="left", va="top")
    ax.text(0.02, 0.925,
            "A shared corpus-expansion policy is evaluated through three non-pooled protocol families.",
            fontsize=8.1, color=MUTED, ha="left", va="top")

    # Shared inputs.
    ax.add_patch(FancyBboxPatch((0.02, 0.53), 0.20, 0.31,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=LINE, fc=PANEL, lw=1.0))
    ax.text(0.04, 0.80, "SHARED EVIDENCE CORPUS", fontsize=8.4, fontweight="bold", color=INK)
    for i in range(13):
        ax.add_patch(Circle((0.055 + (i % 7) * 0.020, 0.724 - (i // 7) * 0.036), 0.008,
                            color=CORE))
    ax.text(0.055, 0.646, "13 IAEA core documents", fontsize=7.3, color=CORE, fontweight="bold")
    for i in range(20):
        ax.add_patch(Circle((0.055 + (i % 10) * 0.014, 0.604 - (i // 10) * 0.025), 0.0055,
                            color=SUPP))
    ax.text(0.055, 0.548, "+ 51 same-domain supplements", fontsize=7.3, color=MUTED)

    ax.add_patch(FancyBboxPatch((0.02, 0.18), 0.20, 0.25,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=LINE, fc=PANEL, lw=1.0))
    ax.text(0.04, 0.39, "CONTROLLED EXPANSION", fontsize=8.4, fontweight="bold", color=INK)
    ax.plot([0.05, 0.19], [0.31, 0.31], lw=4.0, color="#DCE7F2", solid_capstyle="round")
    for j, label in enumerate(["0", "5", "10", "…", "51"]):
        x = 0.052 + j * 0.034
        ax.scatter(x, 0.31, s=24 if label in {"0", "10", "51"} else 12, color=CORE, zorder=3)
        ax.text(x, 0.27, label, ha="center", va="top", fontsize=6.7, color=MUTED)
    ax.text(0.05, 0.215, r"$\mathcal{D}_{m,t}=\mathcal{D}_{core}\cup\mathcal{D}_{sup}^{(m,t)}$",
            fontsize=7.3, color=INK)

    # Query cards.
    ax.add_patch(FancyBboxPatch((0.27, 0.18), 0.20, 0.66,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=LINE, fc=PANEL, lw=1.0))
    ax.text(0.29, 0.80, "MANUALLY FIXED QUERIES", fontsize=8.4, fontweight="bold", color=INK)
    ax.text(0.29, 0.748, "Baseline suite", fontsize=7.8, color=CORE, fontweight="bold")
    for y, text in [(0.704, "4 bilingual core / phrase queries"),
                    (0.582, "P0 extension"),
                    (0.538, "6 bilingual technical-detail queries"),
                    (0.494, "spikes · zeros · synchrony")]:
        ax.text(0.30, y, text, fontsize=7.15, color=INK if y != 0.582 else P0,
                fontweight="bold" if y in {0.748, 0.582} else "normal")
    ax.plot([0.30, 0.44], [0.635, 0.635], color=LINE, lw=0.8)
    ax.text(0.30, 0.398, "No LLM-generated queries", fontsize=7.1, color=MUTED)
    ax.text(0.30, 0.365, "No pooled cosine scale", fontsize=7.1, color=MUTED)
    ax.text(0.30, 0.245, "top-$k$ retrieval", fontsize=8.0, color=INK, fontweight="bold")
    ax.text(0.30, 0.210, r"$k=10$", fontsize=9.0, color=CORE, fontweight="bold")

    arrow(ax, 0.22, 0.685, 0.27, 0.685, "same collection")
    arrow(ax, 0.47, 0.54, 0.52, 0.54, "evaluate separately")

    # Protocol cards.
    card(ax, 0.52, 0.47, 0.145, 0.37, "HISTORICAL", "legacy robustness", [
        "nomic-embed-text",
        "17 index configurations",
        "100 non-zero draws",
    ], HIST)
    card(ax, 0.685, 0.47, 0.145, 0.37, "P0 GRID", "primary new comparison", [
        "2 MiniLM encoders",
        "800/80 · 1200/120 · 1500/150",
        "10 non-zero draws",
    ], P0)
    card(ax, 0.85, 0.47, 0.13, 0.37, "FIXED WORD", "cross-check", [
        "2 MiniLM encoders",
        "240 words / 24 overlap",
        "10 non-zero draws",
    ], WORD)

    # Metrics.
    ax.add_patch(FancyBboxPatch((0.52, 0.08), 0.46, 0.30,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                ec=LINE, fc=PANEL, lw=1.0))
    ax.text(0.54, 0.345, "RECORDED OUTCOMES AND INTERPRETATION BOUNDARY",
            fontsize=8.3, color=INK, fontweight="bold")
    metrics = [
        ("cosine similarity", "ranked within a protocol"),
        ("IAEA Priority@10", "source-policy adherence"),
        ("first-IAEA rank", "authority visibility"),
        ("strict / document recall", "historical self-retrieval only"),
    ]
    for i, (name, meaning) in enumerate(metrics):
        x = 0.55 + (i % 2) * 0.215
        y = 0.275 - (i // 2) * 0.10
        ax.scatter(x, y, s=32, color=CORE if i < 2 else P0)
        ax.text(x + 0.014, y + 0.015, name, fontsize=7.4, color=INK, fontweight="bold")
        ax.text(x + 0.014, y - 0.015, meaning, fontsize=6.75, color=MUTED)
    ax.text(0.54, 0.105, "Do not infer fault accuracy, universal model rankings, or generation quality.",
            fontsize=7.0, color="#9A3412")

    fig.savefig(OUT / "fig6_evaluation_design.pdf", bbox_inches="tight")
    fig.savefig(OUT / "fig6_evaluation_design.png", dpi=280, bbox_inches="tight")


if __name__ == "__main__":
    main()

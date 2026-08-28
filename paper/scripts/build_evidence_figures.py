#!/usr/bin/env python3
"""Build paper figures and LaTeX tables from checked-in evidence CSV/JSON files.

No model inference is performed. This script only aggregates the repository's
existing retrieval summaries and A2_1 condition-report snapshot.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
FIGS = ROOT / "paper" / "figs"
TABLES = ROOT / "paper" / "tables"
FIGS.mkdir(exist_ok=True)
TABLES.mkdir(exist_ok=True)


def config_from_path(path: Path) -> str:
    match = re.search(r"_o(\d+)_c(\d+)", str(path.parent))
    if not match:
        raise ValueError(f"Cannot extract index configuration from {path}")
    return f"c{match.group(2)}/o{match.group(1)}"


def read_many(pattern: str) -> pd.DataFrame:
    frames = []
    for path in sorted(EVIDENCE.glob(pattern)):
        frame = pd.read_csv(path, encoding="utf-8-sig")
        frame["config"] = config_from_path(path)
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(pattern)
    return pd.concat(frames, ignore_index=True)


def fmt(mean: float, std: float) -> str:
    return f"{mean:.2f} $\\pm$ {std:.2f}"


def scope_results() -> pd.DataFrame:
    scope = read_many("rag_results/**/scope_summary*.csv")
    for column in scope.columns:
        if column not in {"scope", "query_tag", "lang", "query", "config"}:
            scope[column] = pd.to_numeric(scope[column], errors="coerce")
    return scope


def plot_scope(scope: pd.DataFrame) -> pd.DataFrame:
    phrase = scope[scope["query_tag"].eq("phrase")].copy()
    # All configurations share the 0--45 supplementary-document range.
    phrase = phrase[phrase["extra_docs"].between(0, 45)]
    grouped = (
        phrase.groupby(["lang", "extra_docs"], as_index=False)
        .agg(
            priority_mean=("iaea_purity_topk_mean", "mean"),
            priority_std=("iaea_purity_topk_mean", "std"),
            score_mean=("top1_score_mean", "mean"),
            score_std=("top1_score_mean", "std"),
        )
        .fillna(0.0)
    )

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.9), constrained_layout=True)
    colors = {"en": "#1f77b4", "zh": "#d62728"}
    labels = {"en": "English phrase", "zh": "Chinese phrase"}
    for lang in ("en", "zh"):
        data = grouped[grouped["lang"].eq(lang)].sort_values("extra_docs")
        for ax, metric, spread, ylabel in [
            (axes[0], "priority_mean", "priority_std", "IAEA priority@10"),
            (axes[1], "score_mean", "score_std", "Mean top-1 cosine score"),
        ]:
            ax.plot(data["extra_docs"], data[metric], marker="o", lw=2,
                    color=colors[lang], label=labels[lang])
            ax.fill_between(data["extra_docs"], data[metric] - data[spread],
                            data[metric] + data[spread], color=colors[lang], alpha=0.16)
            ax.set_xlabel("Supplementary documents admitted")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.25)
    axes[0].set_ylim(-0.03, 1.05)
    axes[0].legend(frameon=False, loc="upper right")
    axes[1].legend(frameon=False, loc="lower right")
    fig.savefig(FIGS / "fig4_scope_priority.pdf", bbox_inches="tight")
    fig.savefig(FIGS / "fig4_scope_priority.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return grouped


def self_retrieval_results() -> pd.DataFrame:
    summary = read_many("rag_results/**/selfretrieval_summary*.csv")
    for column in summary.columns:
        if column not in {"experiment", "query_mode", "relevance", "config"}:
            summary[column] = pd.to_numeric(summary[column], errors="coerce")
    return summary


def plot_self_retrieval(summary: pd.DataFrame) -> pd.DataFrame:
    data = summary[
        summary["experiment"].eq("corpus_decay")
        & summary["query_mode"].eq("first_sentence")
        & summary["extra_docs"].between(0, 45)
    ].copy()
    grouped = (
        data.groupby(["relevance", "extra_docs"], as_index=False)
        .agg(recall_mean=("recall_at_10_mean", "mean"),
             recall_std=("recall_at_10_mean", "std"),
             mrr_mean=("mrr_mean", "mean"),
             mrr_std=("mrr_mean", "std"))
        .fillna(0.0)
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.9), constrained_layout=True)
    colors = {"strict": "#9467bd", "relaxed_doc": "#2ca02c"}
    labels = {"strict": "Strict node", "relaxed_doc": "Document-level"}
    for relevance in ("strict", "relaxed_doc"):
        part = grouped[grouped["relevance"].eq(relevance)].sort_values("extra_docs")
        for ax, metric, spread, ylabel in [
            (axes[0], "recall_mean", "recall_std", "Recall@10"),
            (axes[1], "mrr_mean", "mrr_std", "MRR"),
        ]:
            ax.plot(part["extra_docs"], part[metric], marker="o", lw=2,
                    color=colors[relevance], label=labels[relevance])
            ax.fill_between(part["extra_docs"], part[metric] - part[spread],
                            part[metric] + part[spread], color=colors[relevance], alpha=0.16)
            ax.set_xlabel("Supplementary documents admitted")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.25)
    axes[0].set_ylim(0, 1.03)
    axes[1].set_ylim(0, 1.03)
    axes[0].legend(frameon=False, loc="lower left")
    axes[1].legend(frameon=False, loc="lower left")
    fig.savefig(FIGS / "fig5_self_retrieval.pdf", bbox_inches="tight")
    fig.savefig(FIGS / "fig5_self_retrieval.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return grouped


def case_events() -> pd.DataFrame:
    path = EVIDENCE / "case_A2_1" / "A2_1_sorted_进阶全局工况报告_数据快照.json"
    with path.open(encoding="utf-8") as handle:
        records = json.load(handle)
    rows = []
    for record in records:
        alerts = record.get("alerts", {})
        spikes = alerts.get("spikes_summary", {}).get("total_count", 0)
        zeros = len(alerts.get("isolated_zeros", []))
        rows.append({"channel": record["var_name"].split("RIC")[-1].replace("MA_VER", ""),
                     "spike_events": spikes, "isolated_zeros": zeros})
    return pd.DataFrame(rows)


def plot_case(events: pd.DataFrame) -> None:
    x = np.arange(len(events))
    fig, ax = plt.subplots(figsize=(8.2, 3.8), constrained_layout=True)
    ax.bar(x - 0.19, events["spike_events"], width=0.38, label="Spike episodes", color="#ff7f0e")
    ax.bar(x + 0.19, events["isolated_zeros"], width=0.38, label="Isolated zero events", color="#17becf")
    ax.set_xticks(x, events["channel"])
    ax.set_xlabel("A2_1 detector channel suffix")
    ax.set_ylabel("Detected event count")
    ax.set_ylim(0, max(events["spike_events"].max(), events["isolated_zeros"].max()) + 6)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=2, loc="upper center")
    fig.savefig(FIGS / "fig6_a2_event_summary.pdf", bbox_inches="tight")
    fig.savefig(FIGS / "fig6_a2_event_summary.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_tables(scope_grouped: pd.DataFrame, self_grouped: pd.DataFrame, events: pd.DataFrame) -> None:
    key_points = []
    for lang in ("en", "zh"):
        part = scope_grouped[scope_grouped["lang"].eq(lang)]
        for extra in (0, 5, 10, 45):
            row = part[part["extra_docs"].eq(extra)].iloc[0]
            key_points.append((lang, extra, row["priority_mean"], row["priority_std"], row["score_mean"], row["score_std"]))
    lines = [
        "% Generated by scripts/build_evidence_figures.py from evidence/rag_results.",
        "\\begin{table}[t]",
        "  \\centering",
        "  \\caption{Corpus-scope results for phrase queries, averaged across the 17 available index configurations. IAEA priority@10 is a source-priority measure, not a general relevance judgment.}",
        "  \\label{tab:scope-aggregate}",
        "  \\small",
        "  \\resizebox{\\linewidth}{!}{%",
        "  \\begin{tabular}{llcc}",
        "    \\toprule",
        "    Query language & Supplementary documents & IAEA priority@10 & Mean top-1 cosine \\\\",
        "    \\midrule",
    ]
    for lang, extra, priority, priority_std, score, score_std in key_points:
        language = "English" if lang == "en" else "Chinese"
        lines.append(f"    {language} & {extra} & {fmt(priority, priority_std)} & {fmt(score, score_std)} \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}", "  }", "\\end{table}", ""]
    (TABLES / "table_scope_aggregate.tex").write_text("\n".join(lines), encoding="utf-8")

    recall_0 = self_grouped[self_grouped["extra_docs"].eq(0)]
    strict = recall_0[recall_0["relevance"].eq("strict")].iloc[0]
    relaxed = recall_0[recall_0["relevance"].eq("relaxed_doc")].iloc[0]
    lines = [
        "% Generated by scripts/build_evidence_figures.py from evidence/rag_results.",
        "\\begin{table}[t]",
        "  \\centering",
        "  \\caption{A2\\_1 event summary generated from the checked-in condition-report snapshot. Counts describe detected signal events, not confirmed equipment faults.}",
        "  \\label{tab:a2-events}",
        "  \\small",
        "  \\begin{tabular}{lcc}",
        "    \\toprule",
        "    Channel suffix & Spike episodes & Isolated zero events \\\\",
        "    \\midrule",
    ]
    for row in events.itertuples(index=False):
        lines.append(f"    {row.channel} & {row.spike_events} & {row.isolated_zeros} \\\\")
    lines += [
        "    \\midrule",
        f"    Mean & {events['spike_events'].mean():.1f} & {events['isolated_zeros'].mean():.1f} \\\\",
        "    \\bottomrule", "  \\end{tabular}", "\\end{table}", "",
    ]
    (TABLES / "table_a2_events.tex").write_text("\n".join(lines), encoding="utf-8")

    summary_lines = [
        "# Evidence aggregation snapshot",
        "",
        "- Scope summaries aggregated: 17 index configurations.",
        "- Self-retrieval summaries aggregated: 33 available result directories.",
        f"- A2_1 channels summarized: {len(events)}.",
        f"- At zero supplement, averaged strict/document Recall@10: {strict['recall_mean']:.3f} / {relaxed['recall_mean']:.3f}.",
        "",
    ]
    (TABLES / "EVIDENCE_AGGREGATION.md").write_text("\n".join(summary_lines), encoding="utf-8")


def main() -> None:
    scope = scope_results()
    scope_grouped = plot_scope(scope)
    self_summary = self_retrieval_results()
    self_grouped = plot_self_retrieval(self_summary)
    events = case_events()
    plot_case(events)
    write_tables(scope_grouped, self_grouped, events)
    print("Generated figures in", FIGS)
    print("Generated tables in", TABLES)


if __name__ == "__main__":
    main()

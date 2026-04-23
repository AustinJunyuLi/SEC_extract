"""Generate the compact figure set for the supervisor report.

This script intentionally separates:
1. Live current-state visuals, sourced from `state/progress.json` plus the
   latest `output/extractions/{deal}.json` files.
2. Historical comparison visuals, sourced from the frozen three-way audit slice
   under `quality_reports/comparisons/2026-04-21_three-way/inputs/`.

Outputs
-------
- `report/figures/live_reference_status.png`
- `report/figures/live_flag_codes.png`
- `report/figures/dated_three_way_comparison.png`

The older six-PNG bundle is removed when this script runs so the report folder
only contains assets used by the rebuilt memo.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator


REPO = Path(__file__).resolve().parents[2]
FIGURES = REPO / "report" / "figures"
PROGRESS = REPO / "state" / "progress.json"
OUTPUTS = REPO / "output" / "extractions"
COMPARISON_INPUTS = (
    REPO / "quality_reports" / "comparisons" / "2026-04-21_three-way" / "inputs"
)

REFERENCE_DEALS = [
    "medivation",
    "imprivata",
    "zep",
    "providence-worcester",
    "penford",
    "mac-gray",
    "petsmart-inc",
    "stec",
    "saks",
]

PIPELINE_ORDER = ["alex", "bids_try", "bids_pipeline"]
PIPELINE_LABELS = {
    "alex": "Alex reference",
    "bids_try": "bids_try",
    "bids_pipeline": "bids_pipeline",
}
THEME = {
    "paper": "#f7f4ee",
    "panel": "#fffdfa",
    "ink": "#17212b",
    "muted": "#5e6874",
    "line": "#d8d1c5",
    "grid": "#e7dfd2",
    "track": "#efe7d8",
    "accent": "#234d63",
}
PIPELINE_COLORS = {
    "alex": "#8a8f98",
    "bids_try": "#234d63",
    "bids_pipeline": "#cf8d1b",
}
SEVERITY_COLORS = {
    "hard": "#8f392d",
    "soft": "#cf8d1b",
    "info": "#6f95aa",
}
STATUS_COLORS = {
    "validated": "#8f392d",
    "failed": "#8f392d",
    "passed": "#2f6f52",
    "passed_clean": "#2f6f52",
    "verified": "#234d63",
    "pending": "#b7b2a9",
}
FLAG_LABELS = {
    "date_inferred_from_context": "Inferred date from context",
    "date_range_collapsed": "Collapsed narrated date range",
    "date_inferred_from_rough": "Inferred precise date from rough date",
    "nda_without_bid_or_drop": "NDA with no later bid/drop",
    "unnamed_count_placeholder": "Unnamed bidder placeholders",
    "bid_range": "Bid encoded as range",
    "bidder_type_ambiguous": "Bidder type ambiguous",
    "resolved_name_not_observed": "Resolved name not observed in filing",
    "final_round_inferred": "Final round inferred from process",
    "unnamed_nda_member_of_group": "Unnamed bidder within group count",
    "bid_type_unsupported": "Unsupported bid typing",
    "bid_value_unspecified": "Bid value not specified",
}
EXPECTED_OUTPUTS = {
    "live_reference_status.png",
    "live_flag_codes.png",
    "dated_three_way_comparison.png",
}
STALE_OUTPUTS = {
    "status_by_deal.png",
    "flag_severity.png",
    "event_counts.png",
    "bidder_counts.png",
    "nda_counts.png",
    "drop_counts.png",
}
COMPARISON_RE = re.compile(
    r"^(?P<slug>.+)_(?P<source>alex|bids_try|bids_pipeline)\.csv$"
)


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": THEME["paper"],
            "savefig.facecolor": THEME["paper"],
            "axes.facecolor": THEME["panel"],
            "axes.edgecolor": THEME["line"],
            "axes.labelcolor": THEME["ink"],
            "axes.titleweight": "bold",
            "axes.titlesize": 18,
            "axes.labelsize": 12,
            "xtick.color": "#33414d",
            "ytick.color": "#33414d",
            "text.color": THEME["ink"],
            "font.size": 11,
            "font.family": "DejaVu Sans",
            "grid.color": THEME["grid"],
            "grid.linestyle": (0, (1.2, 2.6)),
            "grid.alpha": 1.0,
        }
    )


def style_axis(ax: plt.Axes, *, grid_axis: str) -> None:
    ax.set_facecolor(THEME["panel"])
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(THEME["line"])
        ax.spines[side].set_linewidth(1.1)


def add_eyebrow(fig: plt.Figure, text: str) -> None:
    fig.text(
        0.5,
        0.985,
        text.upper(),
        ha="center",
        va="top",
        fontsize=9,
        fontweight="bold",
        color=THEME["muted"],
    )


def add_source_note(fig: plt.Figure, text: str) -> None:
    fig.text(0.012, 0.02, text, fontsize=9, color=THEME["muted"])


def add_left_header(
    fig: plt.Figure,
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
) -> None:
    add_eyebrow(fig, eyebrow)
    fig.text(
        0.012,
        0.93,
        title,
        ha="left",
        va="top",
        fontsize=23,
        fontweight="bold",
        color=THEME["ink"],
    )
    fig.text(
        0.012,
        0.892,
        subtitle,
        ha="left",
        va="top",
        fontsize=10.5,
        color=THEME["muted"],
    )


def _count_flags(payload: dict) -> Counter:
    counts: Counter = Counter()
    for event in payload.get("events", []):
        for flag in event.get("flags", []):
            counts[flag["severity"]] += 1
    for flag in payload.get("deal", {}).get("deal_flags", []):
        counts[flag["severity"]] += 1
    return counts


def load_live_reference_state() -> tuple[list[dict], str]:
    progress = json.loads(PROGRESS.read_text())
    updated = progress["updated"]
    rows: list[dict] = []
    for slug in REFERENCE_DEALS:
        payload = json.loads((OUTPUTS / f"{slug}.json").read_text())
        flags = _count_flags(payload)
        rows.append(
            {
                "slug": slug,
                "status": progress["deals"][slug]["status"],
                "row_count": len(payload.get("events", [])),
                "hard": flags["hard"],
                "soft": flags["soft"],
                "info": flags["info"],
                "total_flags": sum(flags.values()),
            }
        )
    status_rank = {
        "validated": 0,
        "failed": 1,
        "passed": 2,
        "passed_clean": 3,
        "verified": 4,
        "pending": 5,
    }
    rows.sort(
        key=lambda row: (
            status_rank.get(row["status"], 99),
            -row["hard"],
            -row["total_flags"],
            row["slug"],
        )
    )
    return rows, updated


def build_live_reference_status() -> None:
    rows, updated = load_live_reference_state()
    slugs = [row["slug"] for row in rows]
    hard = np.array([row["hard"] for row in rows], dtype=float)
    soft = np.array([row["soft"] for row in rows], dtype=float)
    info = np.array([row["info"] for row in rows], dtype=float)
    totals = hard + soft + info

    fig, ax = plt.subplots(figsize=(13.0, 7.1))
    y = np.arange(len(rows))
    max_total = max(int(totals.max()), 1)

    ax.barh(
        y,
        np.full(len(rows), max_total),
        color=THEME["track"],
        height=0.74,
        edgecolor="none",
        zorder=0,
    )

    ax.barh(
        y,
        hard,
        color=SEVERITY_COLORS["hard"],
        label="hard",
        height=0.58,
        edgecolor=THEME["panel"],
        linewidth=0.6,
        zorder=3,
    )
    ax.barh(
        y,
        soft,
        left=hard,
        color=SEVERITY_COLORS["soft"],
        label="soft",
        height=0.58,
        edgecolor=THEME["panel"],
        linewidth=0.6,
        zorder=3,
    )
    ax.barh(
        y,
        info,
        left=hard + soft,
        color=SEVERITY_COLORS["info"],
        label="info",
        height=0.58,
        edgecolor=THEME["panel"],
        linewidth=0.6,
        zorder=3,
    )

    label_x = max_total + 6
    x_max = max_total + 37
    for idx, row in enumerate(rows):
        total = int(totals[idx])
        status = row["status"]
        status_color = STATUS_COLORS.get(status, "#b7b2a9")
        ax.text(
            total + 1.2,
            idx,
            f"{total}",
            va="center",
            ha="left",
            fontsize=10,
            fontweight="bold",
            color="#4b5563",
        )
        ax.text(
            label_x,
            idx,
            status,
            va="center",
            ha="left",
            fontsize=9,
            color="white",
            bbox={"boxstyle": "round,pad=0.28", "fc": status_color, "ec": "none"},
        )
        ax.text(
            label_x + 14.6,
            idx,
            f"{row['row_count']} rows",
            va="center",
            ha="left",
            fontsize=9,
            color="#4b5563",
        )

    ax.set_yticks(y)
    ax.set_yticklabels(slugs)
    ax.invert_yaxis()
    ax.set_xlim(0, x_max)
    ax.set_xlabel("Current flag count in latest extraction")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    style_axis(ax, grid_axis="x")
    ax.legend(loc="upper right", ncol=3, bbox_to_anchor=(1, 1.02))
    add_left_header(
        fig,
        eyebrow="Current-state snapshot",
        title="Live reference-set status and flag burden",
        subtitle="Stacked bars show current flag counts by severity; the right-side badge shows workflow status.",
    )
    add_source_note(
        fig,
        (
            "Source: state/progress.json + output/extractions/{deal}.json. "
            f"Snapshot updated {updated}."
        ),
    )
    plt.tight_layout(rect=[0, 0.05, 1, 0.87])
    plt.savefig(FIGURES / "live_reference_status.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_live_flag_codes() -> None:
    code_counts: Counter = Counter()
    severity_counts: dict[str, Counter] = defaultdict(Counter)
    for slug in REFERENCE_DEALS:
        payload = json.loads((OUTPUTS / f"{slug}.json").read_text())
        for event in payload.get("events", []):
            for flag in event.get("flags", []):
                code_counts[flag["code"]] += 1
                severity_counts[flag["code"]][flag["severity"]] += 1
        for flag in payload.get("deal", {}).get("deal_flags", []):
            code_counts[flag["code"]] += 1
            severity_counts[flag["code"]][flag["severity"]] += 1

    selected_codes = [code for code, _ in code_counts.most_common(10)]
    hard_led_codes = [
        code
        for code, severities in severity_counts.items()
        if severities.get("hard", 0) > 0 and code not in selected_codes
    ]
    for code in hard_led_codes:
        selected_codes.append(code)
    for code, _ in code_counts.most_common():
        if len(selected_codes) >= 12:
            break
        if code not in selected_codes:
            selected_codes.append(code)

    top_codes = [(code, code_counts[code]) for code in selected_codes]
    labels = [FLAG_LABELS.get(code, code.replace("_", " ")) for code, _ in reversed(top_codes)]
    values = [count for _, count in reversed(top_codes)]
    colors = []
    for code, _ in reversed(top_codes):
        dominant = max(
            severity_counts[code].items(),
            key=lambda item: (item[1], item[0] == "hard", item[0] == "soft"),
        )[0]
        colors.append(SEVERITY_COLORS[dominant])

    fig, ax = plt.subplots(figsize=(13.0, 7.2))
    y = np.arange(len(labels))
    max_value = max(values) if values else 1
    ax.barh(
        y,
        np.full(len(labels), max_value),
        color=THEME["track"],
        height=0.74,
        edgecolor="none",
        zorder=0,
    )
    ax.barh(
        y,
        values,
        color=colors,
        height=0.58,
        edgecolor=THEME["panel"],
        linewidth=0.8,
        zorder=3,
    )
    for idx, value in enumerate(values):
        ax.text(
            value + 0.9,
            idx,
            str(value),
            va="center",
            ha="left",
            fontsize=10,
            fontweight="bold",
            color=THEME["ink"],
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Current occurrences across the 9 reference deals")
    ax.set_xlim(0, max_value + 8)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    style_axis(ax, grid_axis="x")
    legend_handles = [
        plt.Line2D([0], [0], color=SEVERITY_COLORS["hard"], lw=6, label="hard-led"),
        plt.Line2D([0], [0], color=SEVERITY_COLORS["soft"], lw=6, label="soft-led"),
        plt.Line2D([0], [0], color=SEVERITY_COLORS["info"], lw=6, label="info-led"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", ncol=3, bbox_to_anchor=(1, 1.02))
    add_left_header(
        fig,
        eyebrow="Live validator mix",
        title="Current validator issues, by issue family",
        subtitle="Color indicates the dominant severity observed for each issue family in the current live outputs.",
    )
    add_source_note(
        fig,
        (
            "Source: latest output/extractions payloads only. "
            "Append-only state/flags.jsonl is intentionally not used here."
        ),
    )
    plt.tight_layout(rect=[0, 0.05, 1, 0.87])
    plt.savefig(FIGURES / "live_flag_codes.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def load_dated_comparison_metrics() -> dict[tuple[str, str], dict[str, int]]:
    metrics: dict[tuple[str, str], dict[str, int]] = {}
    for path in sorted(COMPARISON_INPUTS.glob("*.csv")):
        match = COMPARISON_RE.match(path.name)
        if not match:
            continue
        slug = match.group("slug")
        source = match.group("source")
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        bid_notes = Counter(row.get("bid_note", "") for row in rows)
        metrics[(slug, source)] = {
            "rows": len(rows),
            "ndas": bid_notes["NDA"],
            "drops": sum(
                value for key, value in bid_notes.items() if key.startswith("Drop")
            ),
        }
    return metrics


def build_dated_three_way_comparison() -> None:
    metrics = load_dated_comparison_metrics()
    x = np.arange(len(REFERENCE_DEALS))
    width = 0.24
    subplot_meta = [
        ("rows", "Event rows"),
        ("ndas", "NDA rows"),
        ("drops", "Drop-family rows"),
    ]

    fig, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(13.2, 10.8),
        sharex=True,
        constrained_layout=False,
    )

    for axis, (metric_key, metric_label) in zip(axes, subplot_meta):
        for idx, source in enumerate(PIPELINE_ORDER):
            values = [metrics[(slug, source)][metric_key] for slug in REFERENCE_DEALS]
            offset = (idx - 1) * width
            axis.bar(
                x + offset,
                values,
                width=width,
                color=PIPELINE_COLORS[source],
                label=PIPELINE_LABELS[source],
                edgecolor=THEME["panel"],
                linewidth=0.7,
                zorder=3,
            )
        axis.set_ylabel("")
        axis.set_title(metric_label, loc="left", fontsize=13, color=THEME["accent"], pad=8)
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        style_axis(axis, grid_axis="y")

    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=3)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(REFERENCE_DEALS, rotation=24, ha="right")
    fig.suptitle(
        "Dated three-way comparison slice (2026-04-21 audit inputs)",
        y=0.967,
        fontsize=22,
        fontweight="bold",
    )
    fig.text(
        0.012,
        0.935,
        "Grouped bars compare the same frozen audit slice across the reference set, bids_try, and bids_pipeline.",
        fontsize=10,
        color=THEME["muted"],
    )
    add_eyebrow(fig, "Historical benchmark")
    add_source_note(
        fig,
        (
            "Source: quality_reports/comparisons/2026-04-21_three-way/inputs/*.csv. "
            "This is historical benchmark evidence, not the live rerun state."
        ),
    )
    plt.tight_layout(rect=[0, 0.05, 1, 0.92])
    plt.savefig(
        FIGURES / "dated_three_way_comparison.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


def cleanup_stale_outputs() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for filename in STALE_OUTPUTS:
        path = FIGURES / filename
        if path.exists():
            path.unlink()
    for path in FIGURES.glob("*.png"):
        if path.name not in EXPECTED_OUTPUTS:
            path.unlink()


def main() -> None:
    configure_matplotlib()
    cleanup_stale_outputs()
    build_live_reference_status()
    build_live_flag_codes()
    build_dated_three_way_comparison()
    for filename in sorted(EXPECTED_OUTPUTS):
        print(f"wrote report/figures/{filename}")


if __name__ == "__main__":
    main()

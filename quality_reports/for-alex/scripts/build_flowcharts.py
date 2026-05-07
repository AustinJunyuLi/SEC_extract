#!/usr/bin/env python3
"""Generate polished SVG flowcharts for the Alex-facing HTML reports.

The reports need exact labels and stable captions, so the diagrams are
authored as deterministic SVG rather than rendered from Mermaid at page load.
"""

from __future__ import annotations

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"

INK = "#172033"
MUTED = "#5f6b7c"
LINE = "#d9e0ea"
CANVAS = "#ffffff"
LABEL_BG = "#ffffff"

TONES = {
    "blue":  ("#f3f7fd", "#4f7fbf", "#1e4677"),
    "green": ("#f1f8f4", "#4f956f", "#22513a"),
    "amber": ("#fff7e8", "#bd7a2b", "#744412"),
    "red":   ("#fff2f0", "#bf6258", "#792d28"),
    "slate": ("#f6f8fb", "#8390a3", "#354255"),
}

FONT = "'Source Sans 3', 'Inter', 'Avenir', system-ui, sans-serif"


def esc(value: str) -> str:
    return escape(value, quote=True)


def defs() -> str:
    return """
  <defs>
    <filter id="softShadow" x="-8%" y="-12%" width="116%" height="130%">
      <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#172033" flood-opacity="0.08"/>
    </filter>
    <marker id="arrowSlate" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#8390a3"/>
    </marker>
    <marker id="arrowGreen" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#4f956f"/>
    </marker>
    <marker id="arrowRed" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#bf6258"/>
    </marker>
    <marker id="arrowAmber" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#bd7a2b"/>
    </marker>
  </defs>
"""


def text_block(
    x: int,
    y: int,
    lines: list[str],
    *,
    size: int = 13,
    weight: str = "400",
    color: str = INK,
    anchor: str = "middle",
    line_height: int | None = None,
    family: str = FONT,
    italic: bool = False,
) -> str:
    if line_height is None:
        line_height = int(size * 1.4)
    spans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else line_height
        spans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    style = ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}"{style}>'
        + "".join(spans)
        + "</text>"
    )


def card(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    lines: list[str] | None = None,
    *,
    tone: str = "blue",
    number: str | None = None,
    title_size: int = 15,
    body_size: int = 13,
    align: str = "center",
) -> str:
    fill, stroke, dark = TONES[tone]
    tx = x + w // 2 if align == "center" else x + 22
    anchor = "middle" if align == "center" else "start"
    title_y = y + 34
    body_y = title_y + int(title_size * 1.85)
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.35" filter="url(#softShadow)"/>',
    ]
    if number is not None:
        badge_x = x + 24 if align == "center" else x + 22
        title_x = x + 50 if align == "center" else x + 50
        title_anchor = "start"
        out.append(
            f'<circle cx="{badge_x}" cy="{title_y - 5}" r="12" fill="#ffffff" '
            f'stroke="{stroke}" stroke-width="1.15"/>'
        )
        out.append(
            text_block(badge_x, title_y, [str(number)], size=title_size - 2, weight="700", color=stroke)
        )
        out.append(
            text_block(title_x, title_y, [title], size=title_size, weight="700", color=dark, anchor=title_anchor)
        )
    else:
        out.append(text_block(tx, title_y, [title], size=title_size, weight="700", color=dark, anchor=anchor))
    if lines:
        body_anchor = "middle" if align == "center" else "start"
        body_x = tx if number is None or align != "center" else x + w // 2
        out.append(
            text_block(
                body_x,
                body_y,
                lines,
                size=body_size,
                color=INK,
                anchor=body_anchor,
                line_height=int(body_size * 1.55),
            )
        )
    return "\n".join(out)


def small_card(x: int, y: int, w: int, h: int, lines: list[str], *, tone: str = "slate") -> str:
    fill, stroke, dark = TONES[tone]
    line_height = 17
    total_height = line_height * len(lines)
    base_y = y + h // 2 - total_height // 2 + 12
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>',
            text_block(x + w // 2, base_y, lines, size=12, weight="500", color=dark, line_height=line_height),
        ]
    )


def decision(x: int, y: int, w: int, h: int, lines: list[str], *, tone: str = "amber") -> str:
    fill, stroke, dark = TONES[tone]
    points = [
        (x + w // 2, y),
        (x + w, y + h // 2),
        (x + w // 2, y + h),
        (x, y + h // 2),
    ]
    point_string = " ".join(f"{px},{py}" for px, py in points)
    line_height = 16
    total = line_height * len(lines)
    base_y = y + h // 2 - total // 2 + 11
    return "\n".join(
        [
            f'<polygon points="{point_string}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>',
            text_block(x + w // 2, base_y, lines, size=12, weight="600", color=dark, line_height=line_height),
        ]
    )


def pill(x: int, y: int, w: int, h: int, label: str, *, tone: str = "slate") -> str:
    fill, stroke, dark = TONES[tone]
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h // 2}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>',
            text_block(x + w // 2, y + h // 2 + 4, [label], size=12, weight="600", color=dark),
        ]
    )


def arrow(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    tone: str = "slate",
    label: str | None = None,
    label_offset: tuple[int, int] = (0, -8),
    curve: tuple[int, int, int, int] | None = None,
) -> str:
    colors = {
        "slate": ("#8390a3", "arrowSlate"),
        "green": ("#4f956f", "arrowGreen"),
        "red": ("#bf6258", "arrowRed"),
        "amber": ("#bd7a2b", "arrowAmber"),
    }
    color, marker = colors[tone]
    if curve:
        c1x, c1y, c2x, c2y = curve
        path = f"M {x1} {y1} C {c1x} {c1y}, {c2x} {c2y}, {x2} {y2}"
    else:
        path = f"M {x1} {y1} L {x2} {y2}"
    out = [
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.65" '
        f'stroke-linecap="round" marker-end="url(#{marker})"/>'
    ]
    if label:
        lx = (x1 + x2) // 2 + label_offset[0]
        ly = (y1 + y2) // 2 + label_offset[1]
        label_width = max(40, int(len(label) * 6.2 + 16))
        out.append(
            f'<rect x="{lx - label_width // 2}" y="{ly - 14}" width="{label_width}" height="20" '
            f'rx="10" fill="{LABEL_BG}" stroke="#edf1f6" stroke-width="1"/>'
        )
        out.append(text_block(lx, ly, [label], size=11, weight="500", color=color))
    return "\n".join(out)


def frame(width: int, height: int, title: str, body: str) -> str:
    """Render the SVG root with an accessibility title only — no inline header text or outer pageGlow rect."""
    title_id = title.lower().replace(" ", "-").replace("/", "-").replace("&", "and")
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id}">\n'
        f'  <title id="{title_id}">{esc(title)}</title>\n'
        f"{defs()}"
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="{CANVAS}"/>\n'
        f"{body}\n"
        f"</svg>\n"
    )


def write(name: str, width: int, height: int, title: str, body: str) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    (ASSET_DIR / name).write_text(frame(width, height, title, body), encoding="utf-8")


# --- Diagrams ----------------------------------------------------------------


def architecture() -> None:
    # SEC filing → 3 layer cards horizontally → authority-order footer
    body = "\n".join(
        [
            small_card(30, 175, 140, 90, ["SEC filing", "Background pages", "pages.json"], tone="slate"),
            arrow(170, 220, 210, 220, tone="slate"),
            card(210, 100, 240, 240, "Layer 1: LLM",
                 ["Proposes source-backed", "claims only", "", "5 claim families", "exact evidence refs", "", "No IDs, offsets,", "or spreadsheet rows"],
                 tone="amber", number="1"),
            arrow(450, 220, 490, 220, tone="slate"),
            card(490, 100, 240, 240, "Layer 2: Python",
                 ["Binds every quote", "byte-for-byte", "", "Builds canonical graph", "validates hard rules", "", "Owns IDs, spans,", "dispositions"],
                 tone="blue", number="2"),
            arrow(730, 220, 770, 220, tone="slate"),
            card(770, 100, 240, 240, "Layer 3: Review",
                 ["Flat CSV for scanning", "JSONL for AI review", "DuckDB for SQL", "", "Human adjudication", "goes back to filing", "", "Workbook is calibration"],
                 tone="green", number="3"),
            text_block(520, 400, ["Authority order: SEC filing > canonical graph > Alex CSV > legacy workbook"],
                       size=13, weight="600", color=INK),
        ]
    )
    write("architecture_layers.svg", 1040, 440, "Three-Layer Extraction Architecture", body)


def e2e_run() -> None:
    # Zigzag 4+3 layout. Top row LTR (1-4), connector right-down, bottom row RTL (5-7),
    # with red/green branch cards hanging below.
    parts: list[str] = []
    cards = [
        ("Filing package", ["pages.json", "manifest.json"], "slate"),
        ("Prompt + rules", ["extract.md", "rules/*.md"], "slate"),
        ("Strict LLM call", ["Responses API", "claim schema"], "amber"),
        ("Raw claims", ["raw_response", "5 families"], "amber"),
        ("Finalize graph", ["bind quotes", "canonicalize"], "blue"),
        ("Review outputs", ["JSONL, CSV", "DuckDB"], "green"),
        ("Alex ledger", ["consolidated", "CSV"], "green"),
    ]
    w, h = 200, 130
    gap = 20
    # Top row: x positions 30, 250, 470, 690 (4 cards), right edge 890
    top_x = [30, 250, 470, 690]
    top_y = 60
    # Bottom row (RTL): x positions 690, 470, 250 (3 cards) — under cols 4,3,2 of top row
    bottom_x = [690, 470, 250]
    bottom_y = 280

    for i in range(4):
        title, lines, tone = cards[i]
        parts.append(card(top_x[i], top_y, w, h, title, lines, tone=tone, number=str(i + 1), title_size=14, body_size=12))
        if i < 3:
            parts.append(arrow(top_x[i] + w + 2, top_y + h // 2, top_x[i + 1] - 4, top_y + h // 2, tone="slate"))

    # Connector from card 4 right edge → curl down → card 5 right edge (top side)
    # Card 4 at (690, 60), right edge x=890, mid y=125. Card 5 at (690, 280), top y=280, top-mid x=790.
    parts.append(
        arrow(
            890, 125, 790, 280,
            tone="slate",
            curve=(940, 125, 940, 280),
        )
    )

    for j in range(3):
        i = j + 4  # cards 5, 6, 7
        title, lines, tone = cards[i]
        parts.append(card(bottom_x[j], bottom_y, w, h, title, lines, tone=tone, number=str(i + 1), title_size=14, body_size=12))
        if j < 2:
            # arrow from card[j] LEFT edge to card[j+1] RIGHT edge — RTL
            x_from = bottom_x[j] - 2
            x_to = bottom_x[j + 1] + w + 4
            parts.append(arrow(x_from, bottom_y + h // 2, x_to, bottom_y + h // 2, tone="slate"))

    # Branches:
    # Below card 5 (Finalize graph at x=690, bottom_y=280): red "quote/validation issue" → review row
    parts.append(arrow(790, 280 + h, 790, 480, tone="red", label="quote or validation issue"))
    parts.append(small_card(700, 480, 180, 70, ["review row", "or failed_system status"], tone="red"))
    # Below card 6 (Review outputs at x=470, bottom_y=280): green "trusted run" → audit folder
    parts.append(arrow(570, 280 + h, 570, 480, tone="green", label="trusted run"))
    parts.append(small_card(450, 480, 220, 70, ["output/audit/{slug}/runs", "preserves the full trail"], tone="green"))

    parts.append(text_block(490, 600, ["The export step reads trusted graph snapshots only; it does not call the model again."],
                            size=13, weight="500", color=INK))
    write("e2e_run_flow.svg", 980, 640, "End-to-End Flow for One Filing", "\n".join(parts))


def llm_roundtrip() -> None:
    # Three actors in a row, two arrows between cards 1 & 2 (forward, return), one to card 3.
    # Width 1000, cards 230×200, x = 115, 385, 655
    parts: list[str] = []
    parts.append(card(115, 60, 230, 200, "run.py / run_pool",
                      ["Builds one prompt", "with filing pages,", "citation units,", "and rule files"],
                      tone="blue", number="1"))
    parts.append(card(385, 60, 230, 200, "Responses API",
                      ["Accepts strict", "JSON schema only", "", "No free text", "No old fields"],
                      tone="amber", number="2"))
    parts.append(card(655, 60, 230, 200, "Audit folder",
                      ["raw_response.json", "prompt.jsonl", "calls.jsonl", "manifest.json"],
                      tone="green", number="3"))
    # Card 1 right (345) → Card 2 left (385) at y=130 (upper half)
    parts.append(arrow(347, 130, 383, 130, tone="slate", label="system + user message"))
    # Card 2 left (385) → Card 1 right (345) at y=190 (lower half) — return arrow
    parts.append(arrow(383, 190, 347, 190, tone="amber", label="5 claim families"))
    # Card 2 right → Card 3 left, label "immutable write"
    parts.append(arrow(617, 160, 653, 160, tone="green", label="immutable write"))
    parts.append(
        text_block(
            500, 320,
            ["Schema gate blocks drift; accepted payload is the five claim families:",
             "actor_claims, event_claims, bid_claims, participation_count_claims, actor_relation_claims."],
            size=12, weight="500", color=INK, italic=True, line_height=18,
        )
    )
    write("llm_roundtrip.svg", 1000, 380, "LLM Round Trip", "\n".join(parts))


def quote_binding() -> None:
    # Clean rail: input → 3 decisions → 2 success cards. Failures drop below each decision.
    parts: list[str] = []
    # Input
    parts.append(card(24, 135, 130, 86, "evidence_ref",
                      ["citation_unit_id", "quote_text"],
                      tone="slate", title_size=13, body_size=11))
    parts.append(arrow(154, 178, 184, 178, tone="slate"))
    # Three decisions on a single rail, center y=178.
    decisions = [
        (184, "citation unit", "known?"),
        (344, "quote is exact", "substring?"),
        (504, "unique", "match?"),
    ]
    for x, l1, l2 in decisions:
        parts.append(decision(x, 126, 130, 104, [l1, l2], tone="amber"))
    # Right-side flow: decision 1 → decision 2 → decision 3 → bound span → success terminus
    parts.append(arrow(314, 178, 344, 178, tone="slate", label="yes", label_offset=(0, -10)))
    parts.append(arrow(474, 178, 504, 178, tone="slate", label="yes", label_offset=(0, -10)))
    parts.append(arrow(634, 178, 660, 178, tone="slate", label="yes", label_offset=(0, -10)))
    # Bound span card
    parts.append(card(660, 135, 150, 86, "Bound span",
                      ["source page", "source offset"],
                      tone="green", title_size=13, body_size=11))
    parts.append(arrow(810, 178, 832, 178, tone="green"))
    # Success terminus
    parts.append(small_card(832, 135, 178, 86, ["Claim can enter graph", "if at least one ref bound"], tone="green"))
    # Failure cards below each decision
    failure_y = 282
    parts.append(arrow(249, 230, 249, failure_y, tone="red", label="no", label_offset=(0, -8)))
    parts.append(small_card(184, failure_y, 130, 72, ["UnknownCitation", "review row"], tone="red"))
    parts.append(arrow(409, 230, 409, failure_y, tone="red", label="no", label_offset=(0, -8)))
    parts.append(small_card(344, failure_y, 130, 72, ["MissingQuote", "review row"], tone="red"))
    parts.append(arrow(569, 230, 569, failure_y, tone="red", label="ambiguous", label_offset=(0, -8)))
    parts.append(small_card(504, failure_y, 130, 72, ["AmbiguousQuote", "review row"], tone="red"))
    # Footnote
    parts.append(text_block(520, 382,
                            ["Failed refs stay visible as review issues; a claim with zero bound refs cannot create canonical rows."],
                            size=12, weight="500", color=INK, italic=True))
    write("quote_binding_flow.svg", 1040, 420, "Quote-Binding Decision Tree", "\n".join(parts))


def claim_lifecycle() -> None:
    # Upper rail: provider claim → bind & match → canonical row (3 cards)
    # Failure forks down at bind & match: → No exact match → Rejected → Review stream
    # Off canonical row to the right: small Alex CSV card
    parts: list[str] = []
    # Upper rail at y=80, h=140
    parts.append(card(60, 80, 200, 140, "Provider claim",
                      ["example: bid claim", "Party C", "$21.00"],
                      tone="amber", number="1", title_size=14, body_size=12))
    parts.append(arrow(260, 150, 296, 150, tone="slate"))
    parts.append(card(300, 80, 220, 140, "Bind & match",
                      ["byte-exact", "paragraph check"],
                      tone="blue", number="2", title_size=14, body_size=12))
    parts.append(arrow(520, 150, 556, 150, tone="slate", label="supported", label_offset=(0, -8)))
    parts.append(card(560, 80, 200, 140, "Canonical row",
                      ["actor / event", "bid / relation"],
                      tone="green", number="3", title_size=14, body_size=12))
    # Off canonical row to the right: Alex CSV (if projected)
    parts.append(arrow(760, 150, 790, 150, tone="green"))
    parts.append(small_card(790, 115, 200, 70, ["Alex CSV", "(if projected)"], tone="green"))
    # Failure fork: down from bind & match
    parts.append(arrow(410, 220, 410, 296, tone="red", label="no exact match", label_offset=(28, -4)))
    # Lower rail at y=300, h=120
    parts.append(card(310, 300, 200, 120, "No exact match",
                      ["unknown unit", "missing quote", "ambiguous quote"],
                      tone="red", title_size=14, body_size=12))
    parts.append(arrow(510, 360, 556, 360, tone="red"))
    parts.append(card(560, 300, 200, 120, "Rejected",
                      ["rejected_unsupported", "no graph entry"],
                      tone="red", title_size=14, body_size=12))
    parts.append(arrow(760, 360, 796, 360, tone="amber"))
    parts.append(card(800, 300, 200, 120, "Review stream",
                      ["JSONL issue row", "candidate units"],
                      tone="amber", title_size=14, body_size=12))
    # Footnote
    parts.append(text_block(530, 470,
                            ["Only the upper path creates canonical graph rows; the lower path remains review-only."],
                            size=12, weight="500", color=INK, italic=True))
    write("claim_flow.svg", 1060, 510, "Lifecycle of a Single Claim", "\n".join(parts))


def disposition_lifecycle() -> None:
    # Start → Emitted → Binding → {Supported, Rejected, partial}, each terminating in Done.
    parts: list[str] = []
    parts.append(pill(40, 195, 110, 36, "Start", tone="slate"))
    parts.append(arrow(150, 213, 196, 213, tone="slate"))
    parts.append(card(200, 150, 170, 130, "Emitted",
                      ["LLM returns claim", "with evidence_refs"],
                      tone="amber", title_size=14, body_size=12))
    parts.append(arrow(370, 213, 406, 213, tone="slate"))
    parts.append(card(410, 150, 180, 130, "Binding",
                      ["Python tests", "every evidence ref"],
                      tone="blue", title_size=14, body_size=12))
    # Up branch: ≥1 bound → Supported
    parts.append(arrow(590, 185, 626, 110, tone="green", label=">=1 bound", label_offset=(-54, -6),
                       curve=(620, 185, 590, 110)))
    parts.append(card(630, 70, 180, 110, "Supported",
                      ["creates canonical", "rows and evidence"],
                      tone="green", title_size=14, body_size=12))
    parts.append(arrow(810, 125, 836, 125, tone="green"))
    parts.append(pill(840, 107, 100, 36, "Done", tone="green"))
    # Down branch: zero bound → Rejected
    parts.append(arrow(590, 240, 626, 320, tone="red", label="zero bound", label_offset=(-54, 4),
                       curve=(620, 240, 590, 320)))
    parts.append(card(630, 305, 200, 110, "Rejected",
                      ["rejected_unsupported", "review JSONL only"],
                      tone="red", title_size=14, body_size=12))
    parts.append(arrow(830, 360, 856, 360, tone="red"))
    parts.append(pill(860, 342, 100, 36, "Done", tone="red"))
    # Side: some refs fail
    parts.append(arrow(500, 280, 500, 380, tone="amber", label="some refs fail", label_offset=(50, -4)))
    parts.append(small_card(400, 380, 220, 60, ["Supported claim", "plus soft review issue"], tone="amber"))
    write("disposition_lifecycle.svg", 1000, 480, "Claim Disposition States", "\n".join(parts))


def claim_family_map() -> None:
    # 5 family rows on left, central canonicalization card, 5 table rows on right.
    # Direct arrows from family to table; the canonicalization card sits between as an annotation.
    parts: list[str] = []
    families = [
        ("actor_claims", "actors table", "blue"),
        ("actor_relation_claims", "actor_relations table", "blue"),
        ("event_claims", "events table", "green"),
        ("bid_claims", "events table (event_type=bid)", "amber"),
        ("participation_count_claims", "participation_counts table", "slate"),
    ]
    left_x, fam_w = 40, 240
    right_x, tab_w = 600, 280
    fam_y = [80, 140, 200, 260, 320]
    for i, (family, table, tone) in enumerate(families):
        y = fam_y[i]
        parts.append(small_card(left_x, y, fam_w, 46, [family], tone=tone))
        parts.append(small_card(right_x, y, tab_w, 46, [table], tone=tone))
        # Two-segment arrow passing through the central card region
        parts.append(arrow(left_x + fam_w + 2, y + 23, 320, y + 23, tone="slate"))
        parts.append(arrow(540, y + 23, right_x - 4, y + 23, tone="slate"))
    # Central canonicalization card
    parts.append(card(320, 80, 220, 286, "Canonicalization",
                      ["deduplicate actors", "preserve groups", "lock bidder_class", "attach evidence", "assign stable IDs"],
                      tone="blue", title_size=14, body_size=12))
    # Bottom note
    parts.append(pill(380, 410, 280, 36, "No provider-owned row IDs", tone="red"))
    parts.append(text_block(560, 480,
                            ["Provider claims propose; Python chooses the canonical row table."],
                            size=12, weight="500", color=INK, italic=True))
    write("claim_family_map.svg", 1120, 510, "Five Claim Families to Canonical Tables", "\n".join(parts))


def reference_gate() -> None:
    # Vertical stack of cards 1, 2, 3 in left column. Card 3 (Verification) decides:
    # yes → Card 4 (Release proof) → success card.
    # no  → Blocked card (positioned bottom-right).
    parts: list[str] = []
    col_x, w = 60, 220
    # Card 1
    parts.append(card(col_x, 60, w, 110, "Reference set",
                      ["9 filing-grounded", "reference deals"],
                      tone="slate", number="1", title_size=14, body_size=12))
    parts.append(arrow(col_x + w // 2, 170, col_x + w // 2, 195, tone="slate"))
    # Card 2
    parts.append(card(col_x, 195, w, 110, "Stable runs",
                      ["3 consecutive runs", "same rulebook hash"],
                      tone="blue", number="2", title_size=14, body_size=12))
    parts.append(arrow(col_x + w // 2, 305, col_x + w // 2, 330, tone="slate"))
    # Card 3 (Verification, the decision point)
    parts.append(card(col_x, 330, w, 130, "Verification",
                      ["report exists", "current run cited", "Conclusion: VERIFIED"],
                      tone="green", number="3", title_size=14, body_size=12))
    # Right side: yes → Card 4 → success
    parts.append(arrow(col_x + w + 2, 395, 376, 395, tone="green", label="yes", label_offset=(0, -8)))
    parts.append(card(380, 330, 220, 130, "Release proof",
                      ["target proof accepted", "--release-targets set"],
                      tone="amber", number="4", title_size=14, body_size=12))
    parts.append(arrow(600, 395, 696, 395, tone="slate"))
    parts.append(small_card(700, 360, 230, 80, ["5 target deals eligible", "for extraction"], tone="green"))
    # Below: no → Blocked
    parts.append(arrow(col_x + w // 2, 460, col_x + w // 2, 510, tone="red", label="no", label_offset=(12, -2)))
    parts.append(small_card(col_x, 510, w, 70, ["Blocked", "reference gate closed"], tone="red"))
    # Footer
    parts.append(text_block(490, 620,
                            ["Verification is metadata, not a run status; it requires filing-grounded review."],
                            size=12, weight="500", color=INK, italic=True))
    write("reference_gate.svg", 980, 660, "Reference Verification Gate", "\n".join(parts))


def artefact_picker() -> None:
    # Question card on left → 3 symmetric branches (CSV, JSONL, DuckDB) →
    # converge to Answer path → Filing text terminus.
    parts: list[str] = []
    # Geometry: question center y=300, 3 answer cards at y=120/290/460 (offset ±170 from center)
    parts.append(card(40, 240, 200, 120, "Your question",
                      ["What do I need", "to inspect?"],
                      tone="slate", title_size=14, body_size=12))
    # 3 branches diverging
    parts.append(arrow(240, 295, 320, 180, tone="slate", label="spot check", label_offset=(0, -8),
                       curve=(280, 295, 280, 180)))
    parts.append(arrow(240, 300, 320, 300, tone="slate", label="cross-row", label_offset=(0, -8)))
    parts.append(arrow(240, 305, 320, 420, tone="slate", label="joins", label_offset=(0, 18),
                       curve=(280, 305, 280, 420)))
    # 3 answer cards
    parts.append(card(320, 120, 240, 120, "CSV",
                      ["single row", "sort/filter", "spreadsheet review"],
                      tone="green", title_size=14, body_size=12))
    parts.append(card(320, 240, 240, 120, "Review JSONL",
                      ["richer row fields", "good for AI chat", "issue metadata"],
                      tone="blue", title_size=14, body_size=12))
    parts.append(card(320, 360, 240, 120, "DuckDB graph",
                      ["actors + events", "relations + evidence", "SQL joins"],
                      tone="slate", title_size=14, body_size=12))
    # 3 branches converging to Answer path
    parts.append(arrow(560, 180, 640, 295, tone="slate",
                       curve=(600, 180, 600, 295)))
    parts.append(arrow(560, 300, 640, 300, tone="slate"))
    parts.append(arrow(560, 420, 640, 305, tone="slate",
                       curve=(600, 420, 600, 305)))
    # Answer path card
    parts.append(card(640, 240, 240, 120, "Answer path",
                      ["apply review heuristics", "trace source_claim_ids", "filing remains authority"],
                      tone="amber", title_size=14, body_size=12))
    parts.append(arrow(880, 300, 916, 300, tone="green"))
    parts.append(card(920, 240, 160, 120, "Filing text",
                      ["pages.json", "quote decides,", "not workbook"],
                      tone="green", title_size=14, body_size=12))
    parts.append(text_block(540, 540,
                            ["For a quote dispute, skip straight to pages.json and compare the bound filing substring."],
                            size=12, weight="500", color=INK, italic=True))
    write("artefact_picker.svg", 1100, 580, "Choosing the Right Review Artefact", "\n".join(parts))


def main() -> None:
    architecture()
    e2e_run()
    llm_roundtrip()
    quote_binding()
    claim_lifecycle()
    disposition_lifecycle()
    claim_family_map()
    reference_gate()
    artefact_picker()
    print(f"Wrote SVG flowcharts to {ASSET_DIR}")


if __name__ == "__main__":
    main()

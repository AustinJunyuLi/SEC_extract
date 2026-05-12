#!/usr/bin/env python3
"""Build the two Alex-facing standalone HTML reports.

Reads:
  prose/{pipeline_overview,csv_user_manual}.md
  data/{glossary,columns,event_codes,figures}.yaml
  assets/*.svg
  fixtures/*.json
  static/{styles.css,overview.js,manual.js}
  templates/{pipeline_overview,csv_user_manual}.html.j2
  ../../output/review_csv/alex_event_ledger_ref9_plus_targets5.csv

Writes:
  pipeline_overview.html  (single-file, ~1.5 MB)
  csv_user_manual.html    (single-file, ~3.5 MB after CSV embed)

Deterministic: same inputs → byte-identical outputs.
No network. No watch mode.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

import mistune
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]            # quality_reports/for-alex
REPO_ROOT = ROOT.parents[1]                           # bids_try
PROSE = ROOT / "prose"
DATA = ROOT / "data"
FIXTURES = ROOT / "fixtures"
ASSETS = ROOT / "assets"
STATIC = ROOT / "static"
TEMPLATES = ROOT / "templates"
CSV_PATH = REPO_ROOT / "output" / "review_csv" / "alex_event_ledger_ref9_plus_targets5.csv"

OUT_OVERVIEW = ROOT / "pipeline_overview.html"
OUT_MANUAL = ROOT / "csv_user_manual.html"

OVERVIEW_TITLE = "M&A Bidding Extraction Pipeline — How It Works"
OVERVIEW_SUBTITLE = "An end-to-end walkthrough for Alex Gorbenko"
MANUAL_TITLE = "Alex Event Ledger CSV — User Manual"
MANUAL_SUBTITLE = "How to read alex_event_ledger_ref9_plus_targets5.csv"

# 14 deals in the current ledger — used to build the deals table inline.
DEALS_TABLE = [
    {"slug": "imprivata", "target": "IMPRIVATA INC", "acquirer": "(per filing)", "announced": "2016", "verified": True},
    {"slug": "mac-gray", "target": "MAC GRAY CORP", "acquirer": "CSC SERVICEWORKS, INC.", "announced": "2013-10-14", "verified": True},
    {"slug": "medivation", "target": "MEDIVATION INC", "acquirer": "(per filing)", "announced": "2016", "verified": True},
    {"slug": "penford", "target": "PENFORD CORP", "acquirer": "(per filing)", "announced": "2014–15", "verified": True},
    {"slug": "petsmart-inc", "target": "PETSMART INC", "acquirer": "BC Partners + Caisse + GIC + StepStone + Longview (Buyer Group)", "announced": "2014-12-14", "verified": True},
    {"slug": "providence-worcester", "target": "PROVIDENCE & WORCESTER RR CO", "acquirer": "GENESEE & WYOMING INC", "announced": "2016-08-15", "verified": True},
    {"slug": "saks", "target": "SAKS INC", "acquirer": "HUDSON'S BAY COMPANY", "announced": "2013-07-29", "verified": True},
    {"slug": "stec", "target": "STEC INC", "acquirer": "(per filing)", "announced": "2013", "verified": True},
    {"slug": "zep", "target": "ZEP INC", "acquirer": "NEW MOUNTAIN CAPITAL", "announced": "2015-04-08", "verified": True},
    {"slug": "art-technology-group-inc", "target": "ART TECHNOLOGY GROUP INC", "acquirer": "(per filing)", "announced": "2010–11", "verified": False},
    {"slug": "gen-probe-inc-new", "target": "GEN PROBE INC NEW", "acquirer": "HOLOGIC INC", "announced": "2012-04-30", "verified": False},
    {"slug": "m-g-c-diagnostics-corp", "target": "M G C DIAGNOSTICS CORP", "acquirer": "(per filing)", "announced": "2013", "verified": False},
    {"slug": "multimedia-games-holding-co-inc", "target": "MULTIMEDIA GAMES HOLDING CO INC", "acquirer": "(per filing)", "announced": "2013–14", "verified": False},
    {"slug": "wafergen-bio-systems-inc", "target": "WAFERGEN BIO SYSTEMS INC", "acquirer": "TAKARA BIO INC", "announced": "2014–15", "verified": False},
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def load_yaml(p: Path):
    return yaml.safe_load(read_text(p))


def load_json(p: Path):
    return json.loads(read_text(p))


def fingerprint(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
    return h.hexdigest()[:12]


# ---------------------------------------------------------------------------
# placeholder substitution (runs on raw markdown before mistune renders)
# ---------------------------------------------------------------------------

def _figure_html(fig_id: str, figures_index: dict, sections_by_id: dict) -> str:
    if fig_id not in figures_index:
        return f"<!-- missing figure: {fig_id} -->"
    meta = figures_index[fig_id]
    svg_path = ROOT / meta["src"]
    if not svg_path.exists():
        return f"<!-- missing svg file: {meta['src']} -->"
    svg = svg_path.read_text(encoding="utf-8")
    # Strip any XML declaration so the SVG embeds cleanly.
    svg = re.sub(r"<\?xml[^?]*\?>\s*", "", svg)
    section_id = meta.get("section", "")
    section_title = sections_by_id.get(section_id, section_id)
    backlink = ""
    if section_id and section_title:
        backlink = (
            f' <a class="fig-link" href="#{html.escape(section_id)}">'
            f"discussed in §{html.escape(section_title)}</a>"
        )
    caption_html = html.escape(meta.get("caption", ""))
    fig_id_html = html.escape(fig_id)
    return (
        f'<figure class="figure-card" id="fig-{fig_id_html}" role="figure" '
        f'aria-label="{html.escape(meta.get("alt", meta.get("caption", "")))}">'
        f"{svg}"
        f'<figcaption>{caption_html}{backlink}</figcaption>'
        f"</figure>"
    )


def _fixture_html(fixture_id: str) -> str:
    p = FIXTURES / f"{fixture_id}.json"
    if not p.exists():
        return f"<!-- missing fixture: {fixture_id} -->"
    text = p.read_text(encoding="utf-8")
    safe = html.escape(text)
    return (
        f'<details class="fixture">'
        f"<summary>{html.escape(fixture_id)}.json — sample</summary>"
        f"<pre><code>{safe}</code></pre>"
        f"</details>"
    )


def _deals_table_html() -> str:
    rows = []
    for d in DEALS_TABLE:
        verified = "✓" if d["verified"] else "—"
        rows.append(
            f"<tr><td><code>{html.escape(d['slug'])}</code></td>"
            f"<td>{html.escape(d['target'])}</td>"
            f"<td>{html.escape(d['acquirer'])}</td>"
            f"<td>{html.escape(d['announced'])}</td>"
            f"<td style='text-align:center;'>{verified}</td></tr>"
        )
    return (
        '<table><thead><tr><th>Slug</th><th>Target</th><th>Acquirer</th>'
        '<th>Announced</th><th>Verified?</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


PLACEHOLDER_RE = re.compile(r"\{\{(?P<kind>figure|fixture|deals_table|column_reference|event_code_reference)(?::(?P<arg>[\w-]+))?\}\}")


def substitute_placeholders(md_src: str, figures_index: dict, sections_by_id: dict) -> str:
    def replace(match: re.Match) -> str:
        kind = match.group("kind")
        arg = match.group("arg") or ""
        if kind == "figure":
            return _figure_html(arg, figures_index, sections_by_id)
        if kind == "fixture":
            return _fixture_html(arg)
        if kind == "deals_table":
            return _deals_table_html()
        if kind == "column_reference":
            return '<div id="column-reference"></div>'
        if kind == "event_code_reference":
            return '<div id="event-code-reference"></div>'
        return match.group(0)
    return PLACEHOLDER_RE.sub(replace, md_src)


# ---------------------------------------------------------------------------
# markdown rendering with heading IDs
# ---------------------------------------------------------------------------

class HeadingIdRenderer(mistune.HTMLRenderer):
    """Add slugified id= to <h1>-<h4>; also collect a heading list."""

    def __init__(self):
        super().__init__(escape=False)
        self.headings: list[tuple[int, str, str]] = []  # (level, id, title_text)

    def heading(self, text: str, level: int, **attrs) -> str:
        # `text` is already-rendered HTML for the heading content; strip tags for slug.
        plain = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        slug = slugify(plain)
        if 1 <= level <= 4:
            self.headings.append((level, slug, plain))
        return f"<h{level} id=\"{slug}\">{text}</h{level}>\n"


def render_markdown(md_src: str) -> tuple[str, list[tuple[int, str, str]]]:
    renderer = HeadingIdRenderer()
    md = mistune.create_markdown(renderer=renderer, plugins=["table", "strikethrough"])
    html_out = md(md_src)
    return html_out, renderer.headings


# ---------------------------------------------------------------------------
# glossary wrapping (post-rendering, tag-aware)
# ---------------------------------------------------------------------------

TAG_OPEN_RE = re.compile(r"<(\w+)", re.IGNORECASE)
TAG_NAME_RE = re.compile(r"</?(\w+)", re.IGNORECASE)
SEGMENT_RE = re.compile(r"(<!--.*?-->|<[^>]+>)", re.DOTALL)
SOURCE_COMMENT_RE = re.compile(r"\A\s*(?:<!--.*?-->\s*)+", re.DOTALL)
BLOCKER_TAGS = {"script", "style", "svg", "pre", "code", "h1", "h2", "h3", "h4", "figcaption"}


def strip_source_comments(md_src: str) -> str:
    """Drop authoring comments from the top of Markdown sources before rendering.

    The prose files use leading HTML comments for maintainer notes. Those notes
    can contain report placeholders, so stripping them before placeholder
    substitution prevents hidden instructions from becoming visible content.
    """
    return SOURCE_COMMENT_RE.sub("", md_src)


def build_glossary_regex(terms: list[str]) -> re.Pattern | None:
    if not terms:
        return None
    # Sort longest first so multi-word terms win.
    terms_sorted = sorted({t.strip() for t in terms if t.strip()}, key=len, reverse=True)
    parts = []
    for t in terms_sorted:
        # Match whole-word boundary on alpha-numeric ends only.
        word = re.escape(t)
        # Require non-word boundary on alpha-character ends; permit punctuation otherwise.
        parts.append(rf"\b{word}\b")
    pattern = "(?:" + "|".join(parts) + ")"
    return re.compile(pattern, re.IGNORECASE)


def wrap_glossary(html_src: str, glossary_terms: list[str], term_keys: dict[str, str]) -> str:
    """Wrap each glossary term occurrence in <span class="term" data-term="key">.
    Skips text inside <pre>, <code>, <script>, <style>, <h1-h4>, <figcaption>.
    Each term is wrapped at most once per text segment."""
    pattern = build_glossary_regex(glossary_terms)
    if pattern is None:
        return html_src

    seen_per_segment_initial = set()  # reset per segment

    def replace_in_text(text: str) -> str:
        seen: set[str] = set()
        def sub(match: re.Match) -> str:
            term = match.group(0)
            key = term_keys.get(term.lower(), term)
            if key.lower() in seen:
                return term
            seen.add(key.lower())
            return (
                f'<span class="term" data-term="{html.escape(key)}">'
                f"{html.escape(term)}</span>"
            )
        return pattern.sub(sub, text)

    parts = SEGMENT_RE.split(html_src)
    blocker_depth = 0
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if p.startswith("<!--"):
            out.append(p)
            continue
        if p.startswith("<"):
            m = TAG_NAME_RE.match(p)
            if m:
                name = m.group(1).lower()
                if name in BLOCKER_TAGS:
                    if p.startswith("</"):
                        blocker_depth = max(0, blocker_depth - 1)
                    elif not p.endswith("/>") and "/" not in p[:2]:
                        blocker_depth += 1
            out.append(p)
        else:
            if blocker_depth > 0:
                out.append(p)
            else:
                out.append(replace_in_text(p))
    return "".join(out)


# ---------------------------------------------------------------------------
# outline generation (overview only)
# ---------------------------------------------------------------------------

def render_outline_html(headings: list[tuple[int, str, str]]) -> str:
    """Return a flat <ul><li><a>… outline including h2 and h3."""
    items = []
    for level, slug, title in headings:
        if level == 1:
            cls = "h1"
        elif level == 2:
            cls = "h2"
        else:
            cls = "h3"
        items.append(
            f'<li><a class="{cls}" href="#{slug}">{html.escape(title)}</a></li>'
        )
    return "<ul>" + "".join(items) + "</ul>"


# ---------------------------------------------------------------------------
# CSV → JSON for embedding
# ---------------------------------------------------------------------------

def load_csv_for_embed(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Consolidated CSV not found at {path}.\n"
            f"Run: python scripts/export_alex_event_ledger.py --scope all "
            f"--output {path.relative_to(REPO_ROOT)}"
        )
    rows: list[list] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for raw in reader:
            row: list = []
            for v in raw:
                # Stable typing: numeric columns parsed only if they're full numbers; else string.
                row.append(v)
            rows.append(row)
    rows.sort(key=lambda r: (r[header.index("deal_slug")], _safe_int(r[header.index("event_order")])))
    return {"columns": header, "rows": rows}


def _safe_int(v: str) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 10**9


# ---------------------------------------------------------------------------
# build a single report
# ---------------------------------------------------------------------------

def build(
    *,
    report_kind: str,
    title: str,
    subtitle: str,
    md_path: Path,
    template_name: str,
    out_path: Path,
    figures_index: dict,
    glossary: list[dict],
    css_inline: str,
    js_inline: str,
    csv_payload: dict | None,
    columns_meta: list,
    coded_values: dict,
    event_codes: dict,
    build_meta: dict,
    env: Environment,
):
    md_src = strip_source_comments(read_text(md_path))
    # Pre-resolve sections for figure backlinks: derive from prose headings.
    pre_html, pre_headings = render_markdown(md_src)
    sections_by_id = {slug: title for _, slug, title in pre_headings}

    # Substitute placeholders with HTML, then re-render so headings still get IDs.
    md_substituted = substitute_placeholders(md_src, figures_index, sections_by_id)
    html_body, headings = render_markdown(md_substituted)

    # Glossary wrap (post-rendering)
    term_keys = {t["term"].lower(): t["term"] for t in glossary}
    html_body = wrap_glossary(html_body, [t["term"] for t in glossary], term_keys)

    outline_html = render_outline_html(headings) if report_kind == "overview" else ""

    template = env.get_template(template_name)
    rendered = template.render(
        title=title,
        subtitle=subtitle,
        prose_html=html_body,
        outline_html=outline_html,
        glossary_json=json.dumps(glossary, ensure_ascii=False, sort_keys=False),
        csv_json=json.dumps(csv_payload, ensure_ascii=False) if csv_payload else "{}",
        columns_json=json.dumps(columns_meta, ensure_ascii=False),
        coded_values_json=json.dumps(coded_values, ensure_ascii=False),
        event_codes_json=json.dumps(event_codes, ensure_ascii=False),
        css_inline=css_inline,
        js_inline=js_inline,
        build_meta=build_meta,
    )
    out_path.write_text(rendered, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"  → {out_path.relative_to(REPO_ROOT)} ({size_kb:,.0f} KB)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Building Alex-facing reports…")

    # Load static assets
    css_inline = read_text(STATIC / "styles.css")
    js_overview = read_text(STATIC / "overview.js")
    js_manual = read_text(STATIC / "manual.js")

    # Load data
    glossary = load_yaml(DATA / "glossary.yaml")
    columns_doc = load_yaml(DATA / "columns.yaml")
    columns_meta = columns_doc.get("columns", [])
    coded_values = columns_doc.get("coded_values", {})
    event_codes = load_yaml(DATA / "event_codes.yaml")
    figures = load_yaml(DATA / "figures.yaml")
    figures_index = {f["id"]: f for f in figures.get("figures", [])}

    # Load CSV
    csv_payload = load_csv_for_embed(CSV_PATH)
    csv_rows = len(csv_payload["rows"])
    csv_cols = len(csv_payload["columns"])

    # Build metadata
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = fingerprint(timestamp, str(csv_rows), str(csv_cols))
    build_meta_overview = {"timestamp": timestamp, "run_id": run_id, "csv_rows": csv_rows, "csv_cols": csv_cols}
    build_meta_manual = dict(build_meta_overview)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape([]),
        keep_trailing_newline=True,
    )

    build(
        report_kind="overview",
        title=OVERVIEW_TITLE,
        subtitle=OVERVIEW_SUBTITLE,
        md_path=PROSE / "pipeline_overview.md",
        template_name="pipeline_overview.html.j2",
        out_path=OUT_OVERVIEW,
        figures_index=figures_index,
        glossary=glossary,
        css_inline=css_inline,
        js_inline=js_overview,
        csv_payload=None,
        columns_meta=columns_meta,
        coded_values=coded_values,
        event_codes=event_codes,
        build_meta=build_meta_overview,
        env=env,
    )

    build(
        report_kind="manual",
        title=MANUAL_TITLE,
        subtitle=MANUAL_SUBTITLE,
        md_path=PROSE / "csv_user_manual.md",
        template_name="csv_user_manual.html.j2",
        out_path=OUT_MANUAL,
        figures_index=figures_index,
        glossary=glossary,
        css_inline=css_inline,
        js_inline=js_manual,
        csv_payload=csv_payload,
        columns_meta=columns_meta,
        coded_values=coded_values,
        event_codes=event_codes,
        build_meta=build_meta_manual,
        env=env,
    )

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""scripts/fetch_filings.py — Download SEC filings + convert to markdown.

Resolves each seeds.csv row to its primary EDGAR document, downloads the raw
HTML, runs sec2md to produce page-aware markdown, and writes everything under
data/filings/{deal_slug}/.

SEC COMPLIANCE
--------------
- User-Agent: "Austin Li <junyu.li.24@ucl.ac.uk>" (EDGAR rejects anonymous requests).
- Rate limit: SEC caps at 10 req/sec. We sleep MIN_DELAY between requests
  (default 0.15s, so ~6 req/sec — comfortably under the cap).
- Exponential back-off on 429/403 with a max of 3 retries.

USAGE
-----
    python scripts/fetch_filings.py --reference-only           # 9 deals
    python scripts/fetch_filings.py --slug medivation          # one deal
    python scripts/fetch_filings.py --all                      # all 401
    python scripts/fetch_filings.py --reference-only --force   # re-download

OUTPUT LAYOUT
-------------
    data/filings/{slug}/
        raw.htm         # primary document HTML, verbatim from EDGAR
        raw.md          # sec2md markdown, all pages concatenated with page markers
        pages.json      # list of {page_number, content, tokens, element_count}
        manifest.json   # fetch provenance (URL, accession, form type, sizes, timestamps)

WHY FETCH AND CONVERT IN ONE PASS
---------------------------------
We save raw.htm so sec2md can be re-run without hitting EDGAR again (useful when
sec2md upgrades). We pass the HTML bytes to sec2md rather than re-fetching via
its URL interface for exactly this reason.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    import sec2md
except ImportError as e:
    sys.exit(
        "sec2md is required. Install with: "
        "pip install sec2md --break-system-packages"
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS_PATH = REPO_ROOT / "seeds.csv"
FILINGS_DIR = REPO_ROOT / "data" / "filings"

USER_AGENT = "Austin Li <junyu.li.24@ucl.ac.uk>"
MIN_DELAY_SEC = 0.15            # ~6.7 req/sec, under SEC's 10 req/sec ceiling
MAX_RETRIES = 3
BACKOFF_BASE_SEC = 2.0

# Form types that carry a merger/tender "Background of the …" narrative.
PRIMARY_FORM_TYPES = {
    "DEFM14A", "PREM14A",
    "SC TO-T", "SC TO-T/A",
    "SC 14D9", "SC 14D9/A",
    "S-4", "S-4/A",
    "425",
}

# Tender-offer covers (SC TO-T) are typically 50-100 KB and incorporate the actual
# "Background of the Offer" narrative by reference from the Offer to Purchase,
# which is filed as an EX-99.(A)(1)(A) exhibit. For these filings we follow the
# reference and grab the Offer to Purchase instead of the cover form.
TENDER_OFFER_FORMS = {"SC TO-T", "SC TO-T/A"}
OFFER_TO_PURCHASE_EXHIBIT_PATTERN = re.compile(
    r"^EX-99\.\(?A\)?\(?1\)?\(?A\)?", re.IGNORECASE
)


# ---------- CSV helpers ----------

@dataclass
class Seed:
    slug: str
    target_name: str
    acquirer: str
    date_announced: str
    primary_url: str
    is_reference: bool


def load_seeds() -> list[Seed]:
    with SEEDS_PATH.open() as f:
        reader = csv.DictReader(f)
        seeds = []
        for row in reader:
            seeds.append(Seed(
                slug=row["deal_slug"],
                target_name=row["target_name"],
                acquirer=row["acquirer"],
                date_announced=row["date_announced"],
                primary_url=row["primary_url"],
                is_reference=row["is_reference"].strip().lower() == "true",
            ))
        return seeds


# ---------- HTTP ----------

_last_request = 0.0


def _rate_limited_get(url: str, accept: str = "text/html,*/*") -> bytes:
    """GET with User-Agent, rate limiting, and exponential back-off on 429/403."""
    global _last_request
    for attempt in range(MAX_RETRIES):
        # Throttle
        elapsed = time.time() - _last_request
        if elapsed < MIN_DELAY_SEC:
            time.sleep(MIN_DELAY_SEC - elapsed)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": accept, "Host": "www.sec.gov"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                _last_request = time.time()
                return r.read()
        except urllib.error.HTTPError as e:
            _last_request = time.time()
            if e.code in (429, 403) and attempt < MAX_RETRIES - 1:
                sleep = BACKOFF_BASE_SEC ** (attempt + 1)
                print(f"  [{e.code}] back-off {sleep:.1f}s", file=sys.stderr)
                time.sleep(sleep)
                continue
            raise


# ---------- EDGAR parsing ----------

@dataclass
class FilingDocument:
    name: str
    form_type: str
    size_bytes: int | None
    url: str


def _parse_index_table(index_url: str) -> list[tuple[str, str, str, str]]:
    """Fetch an EDGAR '…-index.htm' page and return raw (href, name, form_type, size) rows."""
    html = _rate_limited_get(index_url).decode("utf-8", errors="replace")
    rows = re.findall(
        r'<a href="([^"]+\.(?:htm|html))"[^>]*>([^<]+)</a>\s*</td>\s*'
        r'<td[^>]*>([^<]*)</td>\s*'
        r'<td[^>]*>([^<]*)</td>',
        html,
        re.IGNORECASE,
    )
    if not rows:
        raise ValueError(f"No document rows found on {index_url}")
    return rows


def _row_to_doc(row: tuple[str, str, str, str]) -> FilingDocument:
    href, name, form_type, size_cell = row
    try:
        size_bytes = int(size_cell.strip()) if size_cell.strip().isdigit() else None
    except ValueError:
        size_bytes = None
    abs_url = href if href.startswith("http") else f"https://www.sec.gov{href}"
    return FilingDocument(
        name=name.strip(), form_type=form_type.strip(),
        size_bytes=size_bytes, url=abs_url,
    )


def resolve_substantive_document(index_url: str) -> FilingDocument:
    """Return the document containing the 'Background of the …' narrative.

    For most merger filings (DEFM14A, PREM14A, S-4), this is the primary
    document. For tender offers (SC TO-T), the cover form is a ~50 KB shell
    that incorporates the background section by reference from the Offer to
    Purchase exhibit (EX-99.(A)(1)(A)) — in that case we return the exhibit.
    """
    rows = _parse_index_table(index_url)

    # 1. Find the primary (first matching merger form).
    primary: FilingDocument | None = None
    for row in rows:
        doc = _row_to_doc(row)
        if doc.form_type in PRIMARY_FORM_TYPES:
            primary = doc
            break

    # 2. Fall back: first non-exhibit row.
    if primary is None:
        for row in rows:
            doc = _row_to_doc(row)
            if not doc.form_type.upper().startswith("EX-"):
                primary = doc
                break
        if primary is None:
            raise ValueError(f"No primary document identifiable on {index_url}")

    # 3. For tender offers, prefer the Offer to Purchase exhibit.
    if primary.form_type in TENDER_OFFER_FORMS:
        for row in rows:
            doc = _row_to_doc(row)
            if OFFER_TO_PURCHASE_EXHIBIT_PATTERN.match(doc.form_type):
                return doc
        # If no OtP exhibit found, fall through to the cover form — warn on stderr.
        print(
            f"  WARNING: {primary.form_type} filing but no Offer to Purchase "
            f"exhibit found; using cover form (likely missing Background narrative)",
            file=sys.stderr,
        )
    return primary


def parse_accession(index_url: str) -> tuple[str, str]:
    """Extract (cik, accession_no_dashes) from the seeds.csv index URL.

    Input:  https://www.sec.gov/Archives/edgar/data/{cik}/{accession}-index.htm
    Output: (cik, accession_no_dashes)
    """
    m = re.search(r"/data/(\d+)/([0-9\-]+)-index\.htm", index_url)
    if not m:
        raise ValueError(f"cannot parse CIK/accession from {index_url}")
    cik, accession_with_dashes = m.group(1), m.group(2)
    accession_no_dashes = accession_with_dashes.replace("-", "")
    return cik, accession_no_dashes


# ---------- Per-deal orchestration ----------

def process_deal(seed: Seed, force: bool = False) -> dict[str, Any]:
    deal_dir = FILINGS_DIR / seed.slug
    manifest_path = deal_dir / "manifest.json"

    if manifest_path.exists() and not force:
        print(f"[{seed.slug}] already fetched; skip (use --force to overwrite)")
        return json.loads(manifest_path.read_text())

    deal_dir.mkdir(parents=True, exist_ok=True)

    # 1. Parse seeds CIK + accession.
    cik, accession = parse_accession(seed.primary_url)

    # 2. Resolve substantive document (primary, or Offer to Purchase for tender offers).
    print(f"[{seed.slug}] resolving substantive document …")
    doc = resolve_substantive_document(seed.primary_url)
    print(f"[{seed.slug}]   picked: {doc.form_type}  {doc.name}  ({doc.size_bytes} B)")

    # 3. Download the primary document.
    print(f"[{seed.slug}] downloading {doc.url}")
    html_bytes = _rate_limited_get(doc.url)
    raw_htm_path = deal_dir / "raw.htm"
    raw_htm_path.write_bytes(html_bytes)

    # 4. Run sec2md on the HTML we just saved.
    print(f"[{seed.slug}] converting with sec2md …")
    pages = sec2md.parse_filing(
        html_bytes.decode("utf-8", errors="replace"),
        user_agent=USER_AGENT,
        include_elements=True,
    )

    # 5. Serialize pages.
    pages_payload = [
        {
            "number": p.number,
            "tokens": getattr(p, "tokens", None),
            "element_count": len(getattr(p, "elements", []) or []),
            "content": p.content,
        }
        for p in pages
    ]
    (deal_dir / "pages.json").write_text(json.dumps(pages_payload, indent=2))

    # 6. Flat markdown with page markers (for grep-ability).
    md_lines: list[str] = []
    for p in pages:
        md_lines.append(f"\n<!-- PAGE {p.number} -->\n")
        md_lines.append(p.content)
    (deal_dir / "raw.md").write_text("".join(md_lines))

    # 7. Manifest.
    manifest = {
        "slug": seed.slug,
        "target_name": seed.target_name,
        "acquirer": seed.acquirer,
        "date_announced": seed.date_announced,
        "is_reference": seed.is_reference,
        "source": {
            "index_url": seed.primary_url,
            "cik": cik,
            "accession": accession,
            "primary_document_url": doc.url,
            "primary_document_name": doc.name,
            "form_type": doc.form_type,
        },
        "artifacts": {
            "raw_htm_bytes": len(html_bytes),
            "raw_md_bytes": (deal_dir / "raw.md").stat().st_size,
            "pages_count": len(pages),
        },
        "fetch": {
            "user_agent": USER_AGENT,
            "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
            "sec2md_version": getattr(sec2md, "__version__", "unknown"),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[{seed.slug}] done: {len(pages)} pages, "
          f"{manifest['artifacts']['raw_md_bytes']/1024:.1f} KB markdown")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch SEC filings from EDGAR.")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug", help="fetch one deal by slug")
    grp.add_argument("--reference-only", action="store_true",
                     help="fetch the 9 Alex-reference deals")
    grp.add_argument("--all", action="store_true", help="fetch every deal in seeds.csv")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing manifests")
    args = parser.parse_args()

    seeds = load_seeds()
    if args.slug:
        targets = [s for s in seeds if s.slug == args.slug]
        if not targets:
            sys.exit(f"slug {args.slug} not in seeds.csv")
    elif args.reference_only:
        targets = [s for s in seeds if s.is_reference]
    else:
        targets = seeds

    print(f"fetching {len(targets)} deal(s) with User-Agent: {USER_AGENT}")
    ok = 0
    for seed in targets:
        try:
            process_deal(seed, force=args.force)
            ok += 1
        except Exception as e:
            print(f"[{seed.slug}] FAILED: {e}", file=sys.stderr)
    print(f"\n{ok}/{len(targets)} deals fetched successfully")


if __name__ == "__main__":
    main()

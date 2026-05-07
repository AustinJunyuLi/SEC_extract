from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REFERENCE_SLUGS: tuple[str, ...] = (
    "providence-worcester",
    "medivation",
    "imprivata",
    "zep",
    "petsmart-inc",
    "penford",
    "mac-gray",
    "saks",
    "stec",
)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Run Metadata",
    "## Commands",
    "## Extraction And Flag Summary",
    "## Filing-Grounded Calibration Ledger",
    "## Filing Evidence Review",
    "## Contract Updates",
    "## Conclusion",
)


@dataclass(frozen=True)
class VerificationFailure:
    slug: str
    path: Path
    message: str


def report_path(repo_root: Path, slug: str) -> Path:
    return repo_root / "quality_reports" / "reference_verification" / f"{slug}.md"


def _read_json(path: Path) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return None, f"missing JSON file: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable JSON file {path}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, (dict, list)):
        return None, f"JSON top-level must be object or list: {path}"
    return payload, None


def _page_lookup(pages_payload: dict[str, Any] | list[Any]) -> dict[int, str]:
    raw_pages = pages_payload.get("pages") if isinstance(pages_payload, dict) else pages_payload
    if not isinstance(raw_pages, list):
        return {}
    pages: dict[int, str] = {}
    for page in raw_pages:
        if not isinstance(page, dict):
            continue
        number = page.get("number")
        content = page.get("content")
        if isinstance(number, int) and isinstance(content, str):
            pages[number] = content
    return pages


def _iter_evidence_refs(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        refs = value.get("evidence_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict):
                    yield ref
        for child in value.values():
            yield from _iter_evidence_refs(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_evidence_refs(item)


def _page_from_citation_unit_id(citation_unit_id: Any) -> int | None:
    if not isinstance(citation_unit_id, str):
        return None
    match = re.match(r"^page_(\d+)_paragraph_\d+$", citation_unit_id)
    return int(match.group(1)) if match else None


def _quote_grounded(pages: dict[int, str], page_number: Any, quote: Any) -> bool:
    if isinstance(page_number, list) and isinstance(quote, list):
        return bool(page_number) and len(page_number) == len(quote) and all(
            _quote_grounded(pages, item_page, item_quote)
            for item_page, item_quote in zip(page_number, quote, strict=True)
        )
    if isinstance(page_number, list):
        return any(_quote_grounded(pages, item_page, quote) for item_page in page_number)
    if isinstance(quote, list):
        return bool(quote) and all(_quote_grounded(pages, page_number, item_quote) for item_quote in quote)
    if not isinstance(page_number, int) or not isinstance(quote, str) or not quote:
        return False
    page_text = pages.get(page_number)
    return isinstance(page_text, str) and quote in page_text


def _validate_mechanical_grounding(repo_root: Path, slug: str, path: Path) -> list[VerificationFailure]:
    failures: list[VerificationFailure] = []
    progress_payload, progress_error = _read_json(repo_root / "state" / "progress.json")
    extraction_payload, extraction_error = _read_json(repo_root / "output" / "extractions" / f"{slug}.json")
    pages_payload, pages_error = _read_json(repo_root / "data" / "filings" / slug / "pages.json")
    for error in (progress_error, extraction_error, pages_error):
        if error:
            failures.append(VerificationFailure(slug, path, error))
    if failures:
        return failures
    assert isinstance(progress_payload, dict)
    assert isinstance(extraction_payload, dict)
    assert pages_payload is not None
    pages = _page_lookup(pages_payload)
    if not pages:
        return [VerificationFailure(slug, path, "filing pages.json has no page content to ground citations")]
    deal = progress_payload.get("deals", {}).get(slug)
    current_run_id = deal.get("last_run_id") if isinstance(deal, dict) else None
    if not isinstance(current_run_id, str) or not current_run_id:
        return [VerificationFailure(slug, path, "progress last_run_id is missing")]
    if current_run_id not in path.read_text():
        failures.append(
            VerificationFailure(
                slug,
                path,
                f"verification report must cite current run id {current_run_id}",
            )
        )
    extraction_run_id = extraction_payload.get("run_id") or extraction_payload.get("deal", {}).get("last_run_id")
    if extraction_run_id != current_run_id:
        failures.append(
            VerificationFailure(
                slug,
                path,
                f"extraction run_id {extraction_run_id!r} does not match progress last_run_id {current_run_id!r}",
            )
        )
    raw_response_path = repo_root / "output" / "audit" / slug / "runs" / current_run_id / "raw_response.json"
    raw_payload, raw_error = _read_json(raw_response_path)
    if raw_error:
        failures.append(VerificationFailure(slug, path, raw_error))
    elif isinstance(raw_payload, dict):
        parsed = raw_payload.get("parsed_json")
        refs = list(_iter_evidence_refs(parsed))
        if not refs:
            failures.append(VerificationFailure(slug, path, "raw_response parsed_json has no evidence_refs to ground"))
        for idx, ref in enumerate(refs):
            page_number = _page_from_citation_unit_id(ref.get("citation_unit_id"))
            quote = ref.get("quote_text")
            if page_number is None:
                failures.append(VerificationFailure(slug, path, f"evidence_ref[{idx}] has invalid citation_unit_id"))
                continue
            if not _quote_grounded(pages, page_number, quote):
                failures.append(
                    VerificationFailure(
                        slug,
                        path,
                        f"evidence_ref[{idx}] quote_text is not an exact substring of Filing page {page_number}",
                    )
                )
    graph = extraction_payload.get("graph")
    if not isinstance(graph, dict):
        failures.append(VerificationFailure(slug, path, "extraction is missing graph object"))
        return failures
    for idx, evidence in enumerate(graph.get("evidence", [])):
        if not isinstance(evidence, dict):
            continue
        if not _quote_grounded(pages, evidence.get("source_page"), evidence.get("quote_text")):
            failures.append(
                VerificationFailure(
                    slug,
                    path,
                    f"graph.evidence[{idx}] quote_text is not an exact substring of Filing page {evidence.get('source_page')!r}",
                )
            )
    review_rows = extraction_payload.get("review_rows")
    if not isinstance(review_rows, list):
        failures.append(VerificationFailure(slug, path, "extraction review_rows must be a list"))
        return failures
    for idx, row in enumerate(review_rows):
        if not isinstance(row, dict):
            continue
        if row.get("review_status") == "rejected_claim" and not row.get("bound_source_quote"):
            continue
        if not _review_row_quote_grounded(pages, row):
            failures.append(
                VerificationFailure(
                    slug,
                    path,
                    f"review_rows[{idx}] bound_source_quote is not an exact substring of Filing page {row.get('bound_source_page')!r}",
                )
            )
    return failures


def _review_row_quote_grounded(pages: dict[int, str], row: dict[str, object]) -> bool:
    quotes = _split_review_cell(row.get("bound_source_quote"))
    pages_raw = _split_review_cell(row.get("bound_source_page"))
    if not quotes or not pages_raw:
        return False
    if len(pages_raw) == 1 and len(quotes) > 1:
        pages_raw = pages_raw * len(quotes)
    if len(quotes) != len(pages_raw):
        return False
    for quote, page in zip(quotes, pages_raw, strict=True):
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            return False
        if not _quote_grounded(pages, page_number, quote):
            return False
    return True


def _split_review_cell(value: object) -> list[str]:
    if value in (None, ""):
        return []
    return [part.strip() for part in str(value).split(" | ") if part.strip()]


def validate_report_text(
    slug: str,
    path: Path,
    text: str,
    *,
    repo_root: Path | None = None,
) -> list[VerificationFailure]:
    failures: list[VerificationFailure] = []
    title = f"# {slug} Agent Verification"
    if title not in text:
        failures.append(VerificationFailure(slug, path, f"missing title: {title}"))
    for section in REQUIRED_SECTIONS:
        if section not in text:
            failures.append(VerificationFailure(slug, path, f"missing section: {section}"))
    has_verified_conclusion = "Conclusion: VERIFIED" in text
    if not has_verified_conclusion:
        failures.append(
            VerificationFailure(
                slug,
                path,
                "verification report must conclude with 'Conclusion: VERIFIED'",
            )
        )
    if has_verified_conclusion and "Conclusion: BLOCKED" in text:
        failures.append(VerificationFailure(slug, path, "verification report still has blockers"))
    if "Filing page" not in text and "bound_source_page" not in text:
        failures.append(
            VerificationFailure(
                slug,
                path,
                "verification report must cite filing pages or bound_source_page evidence",
            )
        )
    if repo_root is not None:
        failures.extend(_validate_mechanical_grounding(repo_root, slug, path))
    return failures


def check_reports(
    repo_root: Path,
    *,
    slugs: Sequence[str] = REFERENCE_SLUGS,
) -> list[VerificationFailure]:
    failures: list[VerificationFailure] = []
    for slug in slugs:
        path = report_path(repo_root, slug)
        if not path.exists():
            failures.append(VerificationFailure(slug, path, "missing verification report"))
            continue
        failures.extend(validate_report_text(slug, path, path.read_text(), repo_root=repo_root))
    return failures


def _parse_slugs(value: str | None) -> tuple[str, ...]:
    if not value:
        return REFERENCE_SLUGS
    return tuple(item.strip() for item in value.split(",") if item.strip())


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--slugs", help="Comma-separated slug list. Defaults to all reference slugs.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    failures = check_reports(args.repo_root, slugs=_parse_slugs(args.slugs))
    for failure in failures:
        print(f"{failure.slug}: {failure.path}: {failure.message}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

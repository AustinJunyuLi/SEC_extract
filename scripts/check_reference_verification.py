from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


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
    "## AI-vs-Alex Diff Ledger",
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


def validate_report_text(slug: str, path: Path, text: str) -> list[VerificationFailure]:
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
    if "Filing page" not in text and "source_page" not in text:
        failures.append(
            VerificationFailure(
                slug,
                path,
                "verification report must cite filing pages or source_page evidence",
            )
        )
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
        failures.extend(validate_report_text(slug, path, path.read_text()))
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

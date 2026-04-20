import sys

import pytest

from scripts import fetch_filings


def test_resolve_substantive_document_rejects_425(monkeypatch):
    monkeypatch.setattr(
        fetch_filings,
        "_parse_index_table",
        lambda _: [
            (
                "/Archives/edgar/data/1/000000000000000001/doc.htm",
                "doc.htm",
                "425",
                "100",
            )
        ],
    )

    with pytest.raises(fetch_filings.ExcludedFormTypeError) as excinfo:
        fetch_filings.resolve_substantive_document(
            "https://www.sec.gov/Archives/edgar/data/1/000000000000000001/0000000000-00-000001-index.htm"
        )

    assert excinfo.value.form_type == "425"


def test_resolve_substantive_document_raises_on_unknown_form(monkeypatch):
    monkeypatch.setattr(
        fetch_filings,
        "_parse_index_table",
        lambda _: [
            (
                "/Archives/edgar/data/1/000000000000000001/doc.htm",
                "doc.htm",
                "UNKNOWN",
                "100",
            )
        ],
    )

    with pytest.raises(ValueError, match="Unknown substantive form type"):
        fetch_filings.resolve_substantive_document(
            "https://www.sec.gov/Archives/edgar/data/1/000000000000000001/0000000000-00-000001-index.htm"
        )


def test_main_warns_and_skips_excluded_form_type(monkeypatch, capsys):
    seed = fetch_filings.Seed(
        slug="synthetic-425",
        target_name="Synthetic Co",
        acquirer="Synthetic Parent",
        date_announced="2020-01-01",
        primary_url="https://www.sec.gov/Archives/edgar/data/1/000000000000000001/0000000000-00-000001-index.htm",
        is_reference=False,
    )

    monkeypatch.setattr(fetch_filings, "load_seeds", lambda: [seed])

    def _raise_excluded(seed, force=False):
        raise fetch_filings.ExcludedFormTypeError("425")

    monkeypatch.setattr(fetch_filings, "process_deal", _raise_excluded)
    monkeypatch.setattr(sys, "argv", ["fetch_filings.py", "--all"])

    fetch_filings.main()
    captured = capsys.readouterr()

    assert "skipping slug=synthetic-425: form_type=425 is §Scope-2-excluded" in captured.err

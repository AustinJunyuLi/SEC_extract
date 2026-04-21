"""Tests for the US-007 aggregate-cohort expansion safety net."""
import pipeline


def test_expand_financial_cohort():
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "15 financial buyers",
                "bidder_name": None,
                "source_quote": "approximately 15 financial buyers executed confidentiality agreements",
                "source_page": 7,
                "bid_date_precise": "2020-02-10",
                "bidder_type": {"base": "f", "non_us": False, "public": False},
            }
        ]
    }
    log = pipeline._expand_aggregate_cohort_rows(raw)
    assert len(log) == 1
    assert log[0]["cohort_id"] == "FIN-1"
    assert log[0]["count"] == 15
    events = raw["events"]
    assert len(events) == 15
    assert events[0]["bidder_alias"] == "Financial 1"
    assert events[0]["source"] == "code_cohort_expansion"
    assert events[0]["bidder_name"] is None
    assert events[0]["source_page"] == 7
    assert events[0]["bid_date_precise"] == "2020-02-10"
    assert events[0]["bidder_type"]["base"] == "f"
    assert events[0]["source_quote"].startswith("[synthesized: atomic slot 1 of 15")
    cohort_flags = [f for f in events[0].get("flags", []) if f.get("code") == "cohort_atomic_expansion"]
    assert cohort_flags
    assert events[14]["bidder_alias"] == "Financial 15"


def test_strategic_cohort_with_word_count():
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "twenty strategic parties",
                "bidder_name": None,
                "source_quote": "twenty strategic parties signed CAs",
                "source_page": 3,
            }
        ]
    }
    pipeline._expand_aggregate_cohort_rows(raw)
    assert len(raw["events"]) == 20
    assert raw["events"][0]["bidder_alias"] == "Strategic 1"
    assert raw["events"][19]["bidder_alias"] == "Strategic 20"


def test_non_aggregate_name_is_untouched():
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "Party A",
                "bidder_name": "bidder_01",
                "source_quote": "Party A signed an NDA",
                "source_page": 4,
            }
        ]
    }
    pipeline._expand_aggregate_cohort_rows(raw)
    assert len(raw["events"]) == 1
    assert raw["events"][0]["bidder_alias"] == "Party A"
    assert raw["events"][0]["source"] == "llm"


def test_non_nda_rows_are_untouched():
    raw = {
        "events": [
            {
                "bid_note": "Bid",
                "source": "llm",
                "bidder_alias": "15 financial buyers",
                "bidder_name": None,
                "source_quote": "the 15 financial buyers each submitted bids",
                "source_page": 8,
            }
        ]
    }
    pipeline._expand_aggregate_cohort_rows(raw)
    assert len(raw["events"]) == 1


def test_synthesized_rows_are_untouched():
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "code_gap_fill",
                "bidder_alias": "15 financial buyers",
                "bidder_name": None,
                "source_quote": "[synthesized: unrelated]",
                "source_page": None,
            }
        ]
    }
    pipeline._expand_aggregate_cohort_rows(raw)
    assert len(raw["events"]) == 1
    assert raw["events"][0]["source"] == "code_gap_fill"


def test_count_outside_sanity_range_does_not_expand():
    """A bogus 500-bidder count should not explode into 500 rows."""
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "500 bidders",
                "bidder_name": None,
                "source_quote": "500 bidders",
                "source_page": 1,
            }
        ]
    }
    pipeline._expand_aggregate_cohort_rows(raw)
    assert len(raw["events"]) == 1


def test_cohort_expansion_runs_in_prepare_for_validate(monkeypatch):
    """End-to-end: prepare_for_validate triggers expansion."""
    raw = {
        "deal": {"bidder_registry": {}},
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "3 financial buyers",
                "bidder_name": None,
                "source_quote": "three financial buyers executed CAs",
                "source_page": 1,
                "bid_date_precise": "2020-02-10",
                "bidder_type": {"base": "f", "non_us": False, "public": False},
            }
        ],
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "x"}])
    prepared, _, _ = pipeline.prepare_for_validate("synthetic", raw, filing=filing)
    assert len(prepared["events"]) == 3
    assert prepared["events"][0]["source"] == "code_cohort_expansion"
    assert any(
        entry["type"] == "cohort_expansion"
        for entry in prepared.get("normalization_log", [])
    )

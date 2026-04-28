import json

from scoring import diff as scoring_diff


def test_normalize_bidder_strips_exact_suffixes():
    assert scoring_diff.normalize_bidder("Penford Inc") == "penford"
    assert scoring_diff.normalize_bidder("Alco") == "alco"
    assert scoring_diff.normalize_bidder("SomeCo, Inc.") == "someco"


def test_diff_events_collapses_bucket_cardinality_mismatch():
    ai_events = [
        {"BidderID": 1, "bidder_alias": "Party A", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
        {"BidderID": 2, "bidder_alias": "Party A", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
        {"BidderID": 3, "bidder_alias": "Party A", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("medivation", ai_events, alex_events)

    assert report.matched_rows == 0
    assert report.ai_only_rows == []
    assert report.alex_only_rows == []
    assert len(report.cardinality_mismatches) == 1
    mismatch = report.cardinality_mismatches[0]
    assert mismatch["code"] == "cardinality_mismatch"
    assert mismatch["ai_count"] == 3
    assert mismatch["alex_count"] == 1


def test_diff_events_marks_equal_cardinality_zip_matches_as_order_dependent():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "bid_type": None,
            "bidder_type": "s",
            "bid_value_pershare": None,
            "bid_value_lower": None,
            "bid_value_upper": None,
            "bid_value_unit": None,
            "bid_date_rough": None,
        },
        {
            "BidderID": 2,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "bid_type": None,
            "bidder_type": "f",
            "bid_value_pershare": None,
            "bid_value_lower": None,
            "bid_value_upper": None,
            "bid_value_unit": None,
            "bid_date_rough": None,
        },
    ]
    alex_events = [
        {
            "BidderID": 10,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "bid_type": None,
            "bidder_type": "f",
            "bid_value_pershare": None,
            "bid_value_lower": None,
            "bid_value_upper": None,
            "bid_value_unit": None,
            "bid_date_rough": None,
            "_xlsx_row": 9998,
        },
        {
            "BidderID": 11,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "bid_type": None,
            "bidder_type": "s",
            "bid_value_pershare": None,
            "bid_value_lower": None,
            "bid_value_upper": None,
            "bid_value_unit": None,
            "bid_date_rough": None,
            "_xlsx_row": 9997,
        },
    ]

    report = scoring_diff.diff_events("medivation", ai_events, alex_events)

    assert len(report.cardinality_mismatches) == 0
    assert report.matched_rows == 2
    assert len(report.divergences) == 2
    assert {d["bucket_match_mode"] for d in report.divergences} == {"order_dependent_zip"}


def test_diff_events_collapses_residual_bid_note_mismatch():
    ai_events = [
        {"BidderID": 1, "bidder_alias": "Party A", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
        {"BidderID": 2, "bidder_alias": "Party B", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
        {"BidderID": 3, "bidder_alias": "Party C", "bid_note": "NDA", "bid_date_precise": "2020-02-01"},
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Several parties",
            "bid_note": "NDA",
            "bid_date_precise": None,
            "_xlsx_row": 9999,
        },
        {
            "BidderID": 8,
            "bidder_alias": "Party Z",
            "bid_note": "NDA",
            "bid_date_precise": None,
            "_xlsx_row": 9998,
        },
    ]

    report = scoring_diff.diff_events("medivation", ai_events, alex_events)

    assert report.matched_rows == 0
    assert report.ai_only_rows == []
    assert report.alex_only_rows == []
    assert len(report.cardinality_mismatches) == 1
    mismatch = report.cardinality_mismatches[0]
    assert mismatch["match_scope"] == "residual_bid_note"
    assert mismatch["bucket_key"]["bid_note"] == "NDA"
    assert mismatch["ai_count"] == 3
    assert mismatch["alex_count"] == 2


def test_diff_events_compares_aggregate_bid_value():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": 100_000_000,
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": 90_000_000,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("medivation", ai_events, alex_events)

    assert report.field_disagreements["bid_value"] == 1
    assert report.divergences[0]["field_divergences"] == [
        {"field": "bid_value", "ai": 100_000_000, "alex": 90_000_000}
    ]


def test_write_results_uses_stable_slug_filenames(tmp_path, monkeypatch):
    monkeypatch.setattr(scoring_diff, "RESULTS_DIR", tmp_path)

    report = scoring_diff.DiffReport(slug="saks")
    md_path, json_path = scoring_diff.write_results(report)

    assert md_path == tmp_path / "saks.md"
    assert json_path == tmp_path / "saks.json"

    md_path.write_text("stale")
    scoring_diff.write_results(report)
    assert md_path.read_text().startswith("# Diff report")


def test_diff_events_annotates_alex_self_flagged_matched_divergence(tmp_path, monkeypatch):
    flagged_rows = tmp_path / "alex_flagged_rows.json"
    flagged_rows.write_text(json.dumps({
        "deals": {
            "saks": [
                {
                    "xlsx_row": 7013,
                    "reason": "Alex commented that this row should be deleted.",
                }
            ]
        }
    }))
    monkeypatch.setattr(scoring_diff, "ALEX_FLAGGED_ROWS", flagged_rows)

    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value_pershare": 12.0,
        }
    ]
    alex_events = [
        {
            "BidderID": 2,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value_pershare": 10.0,
            "_xlsx_row": 7013,
        }
    ]

    report = scoring_diff.diff_events("saks", ai_events, alex_events)

    assert report.divergences[0]["alex_self_flag"] == (
        "Alex flagged this row himself: Alex commented that this row should be deleted."
    )
    assert report.alex_flagged_hits == [report.divergences[0]]


def test_ai_only_diff_exceptions_match_current_schema_scope():
    assert scoring_diff.AI_ONLY_EVENT_FIELDS == {
        "source_quote",
        "source_page",
        "process_phase",
        "role",
        "exclusivity_days",
        "consideration_components",
    }

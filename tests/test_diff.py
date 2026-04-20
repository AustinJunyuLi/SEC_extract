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
            "bidder_type": {"base": "s", "non_us": False, "public": True},
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
            "bidder_type": {"base": "f", "non_us": False, "public": None},
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
            "bidder_type": {"base": "f", "non_us": False, "public": None},
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
            "bidder_type": {"base": "s", "non_us": False, "public": True},
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

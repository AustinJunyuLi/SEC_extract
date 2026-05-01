import json

from scoring import diff as scoring_diff


def test_normalize_bidder_strips_exact_suffixes():
    assert scoring_diff.normalize_bidder("Penford Inc") == "penford"
    assert scoring_diff.normalize_bidder("Alco") == "alco"
    assert scoring_diff.normalize_bidder("SomeCo, Inc.") == "someco"


def test_normalize_bidder_folds_smart_quotes():
    assert scoring_diff.normalize_bidder("Hudson\u2019s Bay") == "hudson's bay"


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


def test_diff_report_surfaces_zero_match_cardinality_blocker():
    ai_events = [
        {"BidderID": 1, "bidder_alias": "A", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
        {"BidderID": 2, "bidder_alias": "B", "bid_note": "NDA", "bid_date_precise": "2020-01-01"},
    ]
    alex_events = [
        {"BidderID": 10, "bidder_alias": "C", "bid_note": "NDA", "bid_date_precise": "2020-01-02"},
    ]

    report = scoring_diff.diff_events("petsmart-inc", ai_events, alex_events)

    assert report.review_blockers == [{
        "code": "zero_matched_rows_with_cardinality_mismatch",
        "severity": "review_blocker",
        "reason": "Reference diff has zero matched rows and 1 cardinality mismatch bucket(s).",
    }]


def test_diff_events_labels_buyer_group_atomization_mismatch():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "BC Partners",
            "bid_note": "Executed",
            "bid_date_precise": "2014-12-14",
            "flags": [{
                "code": "buyer_group_constituent",
                "severity": "info",
                "reason": "Filing identifies BC Partners as a buyer-group constituent.",
            }],
        },
        {
            "BidderID": 2,
            "bidder_alias": "Caisse",
            "bid_note": "Executed",
            "bid_date_precise": "2014-12-14",
            "flags": [{
                "code": "buyer_group_constituent",
                "severity": "info",
                "reason": "Filing identifies Caisse as a buyer-group constituent.",
            }],
        },
        {
            "BidderID": 3,
            "bidder_alias": "GIC",
            "bid_note": "Executed",
            "bid_date_precise": "2014-12-14",
            "flags": [{
                "code": "buyer_group_constituent",
                "severity": "info",
                "reason": "Filing identifies GIC as a buyer-group constituent.",
            }],
        },
    ]
    alex_events = [
        {
            "BidderID": 9,
            "bidder_alias": "Buyer Group",
            "bid_note": "Executed",
            "bid_date_precise": "2014-12-14",
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("petsmart-inc", ai_events, alex_events)

    assert report.ai_only_rows == []
    assert report.alex_only_rows == []
    assert len(report.cardinality_mismatches) == 1
    mismatch = report.cardinality_mismatches[0]
    assert mismatch["code"] == "atomization_vs_aggregation"
    assert mismatch["match_scope"] == "buyer_group_atomization"
    assert mismatch["bucket_key"]["bid_note"] == "Executed"
    assert mismatch["ai_count"] == 3
    assert mismatch["alex_count"] == 1


def test_diff_events_suppresses_ai_only_formal_stage_status_enrichment():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_type": "informal",
            "invited_to_formal_round": True,
            "submitted_formal_bid": False,
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_type": "informal",
            "invited_to_formal_round": None,
            "submitted_formal_bid": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("mac-gray", ai_events, alex_events)

    assert report.matched_rows == 1
    assert report.field_disagreements == {}
    assert report.divergences == []
    assert any(
        "formal-stage status enrichment" in note
        for note in report.notes
    )


def test_diff_events_intentionally_suppresses_formal_stage_enrichment_outside_bid_rows():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "invited_to_formal_round": True,
            "submitted_formal_bid": False,
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "NDA",
            "bid_date_precise": "2020-01-01",
            "invited_to_formal_round": None,
            "submitted_formal_bid": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("mac-gray", ai_events, alex_events)

    assert report.matched_rows == 1
    assert report.field_disagreements == {}
    assert report.divergences == []


def test_diff_events_keeps_non_null_formal_stage_status_disagreements():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_type": "informal",
            "invited_to_formal_round": True,
            "submitted_formal_bid": False,
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_type": "informal",
            "invited_to_formal_round": False,
            "submitted_formal_bid": True,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("mac-gray", ai_events, alex_events)

    assert report.field_disagreements == {
        "invited_to_formal_round": 1,
        "submitted_formal_bid": 1,
    }
    assert report.divergences[0]["field_divergences"] == [
        {"field": "invited_to_formal_round", "ai": True, "alex": False},
        {"field": "submitted_formal_bid", "ai": False, "alex": True},
    ]


def test_diff_events_suppresses_reference_drop_classification_underspecification():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": "target",
            "drop_reason_class": "below_minimum",
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": "unknown",
            "drop_reason_class": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("penford", ai_events, alex_events)

    assert report.matched_rows == 1
    assert report.field_disagreements == {}
    assert report.divergences == []
    assert any(
        "source-workbook drop classification underspecification" in note
        for note in report.notes
    )


def test_diff_events_intentionally_keeps_null_drop_initiator_visible():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": "target",
            "drop_reason_class": "below_minimum",
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": None,
            "drop_reason_class": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("penford", ai_events, alex_events)

    assert report.field_disagreements == {"drop_initiator": 1}
    assert report.divergences[0]["field_divergences"] == [
        {"field": "drop_initiator", "ai": "target", "alex": None}
    ]


def test_diff_events_keeps_non_null_drop_classification_disagreements():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": "target",
            "drop_reason_class": "never_advanced",
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Drop",
            "bid_date_precise": "2020-01-01",
            "drop_initiator": "target",
            "drop_reason_class": "target_other",
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("providence-worcester", ai_events, alex_events)

    assert report.field_disagreements == {"drop_reason_class": 1}
    assert report.divergences[0]["field_divergences"] == [
        {"field": "drop_reason_class", "ai": "never_advanced", "alex": "target_other"}
    ]


def test_diff_events_suppresses_alex_legacy_bid_value_when_ai_uses_pershare_field():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": None,
            "bid_value_pershare": 12.5,
            "bid_value_unit": "USD_per_share",
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": 12.5,
            "bid_value_pershare": None,
            "bid_value_unit": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("zep", ai_events, alex_events)

    assert report.field_disagreements == {}
    assert report.divergences == []
    assert any("source-workbook per-share bid value placement" in note for note in report.notes)


def test_diff_events_keeps_true_bid_value_disagreements_visible():
    ai_events = [
        {
            "BidderID": 1,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": None,
            "bid_value_pershare": 12.5,
            "bid_value_unit": "USD_per_share",
        }
    ]
    alex_events = [
        {
            "BidderID": 7,
            "bidder_alias": "Party A",
            "bid_note": "Bid",
            "bid_date_precise": "2020-01-01",
            "bid_value": 10.0,
            "bid_value_pershare": None,
            "bid_value_unit": None,
            "_xlsx_row": 9999,
        }
    ]

    report = scoring_diff.diff_events("zep", ai_events, alex_events)

    assert report.field_disagreements == {"bid_value": 1}
    assert report.divergences[0]["field_divergences"] == [
        {"field": "bid_value", "ai": None, "alex": 10.0}
    ]


def test_diff_deal_fields_suppresses_reference_effective_date_when_ai_is_null():
    report = scoring_diff.diff_deal_fields(
        {"DateEffective": None, "TargetName": "Target"},
        {"DateEffective": "2020-02-01", "TargetName": "Target"},
    )

    assert report == []


def test_diff_deal_warns_when_filtered_dropsilent_matches_alex_drop(tmp_path, monkeypatch):
    reference_dir = tmp_path / "reference"
    extraction_dir = tmp_path / "extractions"
    reference_dir.mkdir()
    extraction_dir.mkdir()
    monkeypatch.setattr(scoring_diff, "REFERENCE_DIR", reference_dir)
    monkeypatch.setattr(scoring_diff, "EXTRACTION_DIR", extraction_dir)

    (reference_dir / "synthetic.json").write_text(json.dumps({
        "deal": {},
        "events": [
            {
                "BidderID": 10,
                "bidder_alias": "Party A",
                "bid_note": "Drop",
                "bid_date_precise": "2020-02-01",
                "_xlsx_row": 9999,
            }
        ],
    }))
    (extraction_dir / "synthetic.json").write_text(json.dumps({
        "deal": {},
        "events": [
            {
                "BidderID": 1,
                "bidder_alias": "Party A",
                "bid_note": "DropSilent",
                "bid_date_precise": None,
            }
        ],
    }))

    report = scoring_diff.diff_deal("synthetic")

    warnings = [
        div for div in report.divergences
        if div.get("type") == "drop_silent_vs_explicit_drop"
    ]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "drop_silent_vs_explicit_drop"
    assert warnings[0]["ai_BidderID"] == 1
    assert warnings[0]["alex_BidderID"] == 10
    assert any("DropSilent-vs-Drop" in note for note in report.notes)


def test_diff_deal_does_not_warn_when_only_canonical_bidder_name_matches(tmp_path, monkeypatch):
    reference_dir = tmp_path / "reference"
    extraction_dir = tmp_path / "extractions"
    reference_dir.mkdir()
    extraction_dir.mkdir()
    monkeypatch.setattr(scoring_diff, "REFERENCE_DIR", reference_dir)
    monkeypatch.setattr(scoring_diff, "EXTRACTION_DIR", extraction_dir)

    (reference_dir / "synthetic.json").write_text(json.dumps({
        "deal": {},
        "events": [
            {
                "BidderID": 10,
                "bidder_name": "bidder_01",
                "bidder_alias": None,
                "bid_note": "Drop",
                "bid_date_precise": "2020-02-01",
                "_xlsx_row": 9999,
            }
        ],
    }))
    (extraction_dir / "synthetic.json").write_text(json.dumps({
        "deal": {},
        "events": [
            {
                "BidderID": 1,
                "bidder_name": "bidder_01",
                "bidder_alias": None,
                "bid_note": "DropSilent",
                "bid_date_precise": None,
            }
        ],
    }))

    report = scoring_diff.diff_deal("synthetic")

    assert [
        div for div in report.divergences
        if div.get("type") == "drop_silent_vs_explicit_drop"
    ] == []


def test_diff_deal_warns_when_registry_resolved_names_match(tmp_path, monkeypatch):
    reference_dir = tmp_path / "reference"
    extraction_dir = tmp_path / "extractions"
    reference_dir.mkdir()
    extraction_dir.mkdir()
    monkeypatch.setattr(scoring_diff, "REFERENCE_DIR", reference_dir)
    monkeypatch.setattr(scoring_diff, "EXTRACTION_DIR", extraction_dir)

    (reference_dir / "synthetic.json").write_text(json.dumps({
        "deal": {
            "bidder_registry": {
                "bidder_07": {
                    "resolved_name": "Acme Corp",
                    "aliases_observed": ["Strategic Buyer", "Acme Corp"],
                }
            }
        },
        "events": [
            {
                "BidderID": 10,
                "bidder_name": "bidder_07",
                "bidder_alias": "Strategic Buyer",
                "bid_note": "Drop",
                "bid_date_precise": "2020-02-01",
                "_xlsx_row": 9999,
            }
        ],
    }))
    (extraction_dir / "synthetic.json").write_text(json.dumps({
        "deal": {
            "bidder_registry": {
                "bidder_01": {
                    "resolved_name": "Acme Corp",
                    "aliases_observed": ["Party A", "Acme Corp"],
                }
            }
        },
        "events": [
            {
                "BidderID": 1,
                "bidder_name": "bidder_01",
                "bidder_alias": "Party A",
                "bid_note": "DropSilent",
                "bid_date_precise": None,
            }
        ],
    }))

    report = scoring_diff.diff_deal("synthetic")

    warnings = [
        div for div in report.divergences
        if div.get("type") == "drop_silent_vs_explicit_drop"
    ]
    assert len(warnings) == 1
    assert warnings[0]["ai_BidderID"] == 1
    assert warnings[0]["alex_BidderID"] == 10


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

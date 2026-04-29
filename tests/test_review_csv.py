import csv
import json

from scripts import render_review_csv


def _extraction():
    return {
        "deal": {
            "bidder_registry": {
                "bidder_01": {
                    "resolved_name": "Party E",
                    "aliases_observed": ["Party E", "Strategic 1"],
                    "first_appearance_row_index": 1,
                }
            }
        },
        "events": [
            {
                "BidderID": 1,
                "bid_date_precise": "2020-01-01",
                "bid_date_rough": None,
                "bidder_name": "bidder_01",
                "bidder_alias": "Party E",
                "process_phase": 1,
                "role": "bidder",
                "bid_note": "NDA",
                "bid_type": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "press_release_subject": None,
                "exclusivity_days": None,
                "source_page": 12,
                "source_quote": "Party E executed a confidentiality agreement.",
                "flags": [
                    {
                        "code": "nda_promoted_from_placeholder",
                        "severity": "info",
                        "reason": "synthetic",
                    }
                ],
            },
            {
                "BidderID": 2,
                "bid_date_precise": "2020-01-02",
                "bid_date_rough": None,
                "bidder_name": None,
                "bidder_alias": "Financial 3",
                "bidder_type": "f",
                "process_phase": 1,
                "role": "bidder",
                "bid_note": "NDA",
                "bid_type": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "press_release_subject": None,
                "exclusivity_days": None,
                "source_page": [12, 13],
                "source_quote": ["first page quote", "second page quote"],
                "flags": [],
            },
        ],
    }


def test_render_rows_is_pure_projection_with_display_labels():
    rows = render_review_csv.render_rows("synthetic", _extraction())

    assert rows[0]["bidder_display"] == "Party E - promoted from unnamed placeholder"
    assert rows[0]["flags_codes"] == "nda_promoted_from_placeholder"
    assert rows[0]["flag_severities"] == "H=0;S=0;I=1"
    assert rows[1]["bidder_display"] == "Unnamed financial sponsor 3"
    assert rows[1]["source_page"] == "12;13"
    assert rows[1]["source_quote"] == "first page quote\nsecond page quote"


def test_render_rows_uses_generic_display_for_vague_unnamed_party():
    extraction = _extraction()
    extraction["events"][1]["bidder_alias"] = None
    extraction["events"][1]["bidder_type"] = None

    rows = render_review_csv.render_rows("synthetic", extraction)

    assert rows[1]["bidder_display"] == "Unnamed party"


def test_cli_writes_slug_csv(tmp_path, monkeypatch):
    input_dir = tmp_path / "output" / "extractions"
    output_dir = tmp_path / "output" / "review_csv"
    input_dir.mkdir(parents=True)
    (input_dir / "synthetic.json").write_text(json.dumps(_extraction()))
    monkeypatch.setattr(render_review_csv, "EXTRACTIONS_DIR", input_dir)
    monkeypatch.setattr(render_review_csv, "REVIEW_CSV_DIR", output_dir)

    assert render_review_csv.main(["--slug", "synthetic"]) == 0

    with (output_dir / "synthetic.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["slug"] == "synthetic"

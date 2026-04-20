import pipeline


def test_prepare_for_validate_applies_failed_promotion_flag_and_canonicalizes():
    raw = {
        "deal": {
            "bidder_registry": {},
        },
        "events": [
            {
                "BidderID": 2,
                "bid_note": "NDA",
                "bidder_name": None,
                "bidder_alias": "Strategic 5",
                "bid_date_precise": "2020-01-01",
            },
            {
                "BidderID": 1,
                "bid_note": "Bid",
                "bidder_name": "bidder_99",
                "bidder_alias": "Party E",
                "bid_date_precise": "2020-02-01",
                "unnamed_nda_promotion": {
                    "target_bidder_id": 2,
                    "promote_to_bidder_alias": "Party E",
                    "promote_to_bidder_name": "bidder_99",
                    "reason": "synthetic",
                },
            },
        ],
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": ""}])

    prepared, _, promotion_log = pipeline.prepare_for_validate(
        "synthetic",
        raw,
        filing=filing,
    )

    assert promotion_log[0]["status"] == "failed"
    assert prepared["events"][0]["BidderID"] == 1
    assert prepared["events"][1]["BidderID"] == 2
    assert prepared["events"][1]["flags"][0]["code"] == "nda_promotion_failed"

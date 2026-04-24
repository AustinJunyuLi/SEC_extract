from scripts.build_reference import VALID_BID_NOTES, RawRow, build_bidder_type, build_deal


def _events(slug: str) -> list[dict]:
    return build_deal(slug)["events"]


def test_build_deal_normalizes_providence_blank_bid_note_in_memory():
    events = _events("providence-worcester")

    assert all(ev["bid_note"] in VALID_BID_NOTES for ev in events)
    g_and_w_nda = next(
        ev
        for ev in events
        if ev["bidder_alias"] == "G&W" and ev["bid_date_precise"] == "2016-04-13"
    )
    assert g_and_w_nda["bid_note"] == "NDA"
    assert g_and_w_nda["bid_type"] is None
    assert any(
        flag["code"] == "legacy_blank_bid_note_normalized"
        for flag in g_and_w_nda["flags"]
    )


def test_build_deal_migrates_zep_exclusivity_event_in_memory():
    events = _events("zep")

    assert all(ev["bid_note"] in VALID_BID_NOTES for ev in events)
    assert all(ev["bid_note"] != "Exclusivity 30 days" for ev in events)
    revised_bid = next(
        ev
        for ev in events
        if ev["bidder_alias"] == "New Mountain Capital"
        and ev["bid_date_precise"] == "2015-02-26"
        and ev["bid_note"] == "Bid"
    )
    assert revised_bid["exclusivity_days"] == 30
    assert any(
        flag["code"] == "legacy_exclusivity_event_migrated"
        for flag in revised_bid["flags"]
    )


def test_build_deal_keeps_public_unknown_for_plain_type_note():
    zep_events = _events("zep")
    new_mountain_bid = next(
        ev
        for ev in zep_events
        if ev["bidder_alias"] == "New Mountain Capital"
        and ev["bid_date_precise"] == "2015-02-10"
        and ev["bid_note"] == "Bid"
    )
    assert new_mountain_bid["bidder_type"] == {
        "base": "f",
        "non_us": False,
        "public": None,
    }
    new_mountain_executed = next(
        ev
        for ev in zep_events
        if ev["bidder_alias"] == "New Mountain Capital"
        and ev["bid_note"] == "Executed"
    )
    assert new_mountain_executed["bidder_type"] == {
        "base": "f",
        "non_us": False,
        "public": None,
    }

    medivation_events = _events("medivation")
    sanofi_bid = next(
        ev
        for ev in medivation_events
        if ev["bidder_alias"] == "Sanofi"
        and ev["bid_note"] == "Bid"
    )
    assert sanofi_bid["bidder_type"] == {"base": "s", "non_us": True, "public": True}


def test_bidder_type_sets_public_false_only_on_private_signal():
    row = RawRow(
        xlsx_row=1,
        cells={
            "bt_financial": None,
            "bt_strategic": None,
            "bt_mixed": None,
            "bt_nonUS": None,
            "bidder_type_note": "private equity F",
        },
    )

    assert build_bidder_type(row) == {
        "base": "f",
        "non_us": False,
        "public": False,
    }

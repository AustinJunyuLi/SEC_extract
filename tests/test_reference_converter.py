from scripts.build_reference import VALID_BID_NOTES, build_deal


def _events(slug: str) -> list[dict]:
    return build_deal(slug)["events"]


def test_bidder_type_emits_scalar_after_drop_geography_and_listing():
    """C1 — bidder_type is a scalar string, not a dict.

    Pre-C1 the converter emitted a nested object with base, geography, and
    listing-status fields.
    Post-C1 it emits "s" (or "f" / "mixed" / None).
    """
    payload = build_deal("medivation")
    for ev in payload["events"]:
        bt = ev.get("bidder_type")
        assert bt is None or isinstance(bt, str), f"bidder_type must be str|None, got {type(bt).__name__}: {bt!r}"
        if isinstance(bt, str):
            assert bt in ("s", "f", "mixed"), f"unexpected bidder_type value: {bt!r}"


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


def test_build_deal_emits_scalar_bidder_type():
    zep_events = _events("zep")
    new_mountain_bid = next(
        ev
        for ev in zep_events
        if ev["bidder_alias"] == "New Mountain Capital"
        and ev["bid_date_precise"] == "2015-02-10"
        and ev["bid_note"] == "Bid"
    )
    assert new_mountain_bid["bidder_type"] == "f"
    new_mountain_executed = next(
        ev
        for ev in zep_events
        if ev["bidder_alias"] == "New Mountain Capital"
        and ev["bid_note"] == "Executed"
    )
    assert new_mountain_executed["bidder_type"] == "f"

    medivation_events = _events("medivation")
    sanofi_bid = next(
        ev
        for ev in medivation_events
        if ev["bidder_alias"] == "Sanofi"
        and ev["bid_note"] == "Bid"
    )
    assert sanofi_bid["bidder_type"] == "s"

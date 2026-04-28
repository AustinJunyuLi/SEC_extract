import pytest

import scripts.build_reference as build_reference
from scripts.build_reference import VALID_BID_NOTES, build_deal


def _events(slug: str) -> list[dict]:
    return build_deal(slug)["events"]


def test_bidder_type_emits_scalar_after_drop_geography_and_listing():
    """C1 — bidder_type is a scalar string, not a dict.

    Pre-C1 the converter emitted a nested object with base, geography, and
    listing-status fields.
    Post-taxonomy-redesign it emits "s" (or "f" / None).
    """
    payload = build_deal("medivation")
    for ev in payload["events"]:
        bt = ev.get("bidder_type")
        assert bt is None or isinstance(bt, str), f"bidder_type must be str|None, got {type(bt).__name__}: {bt!r}"
        if isinstance(bt, str):
            assert bt in ("s", "f"), f"unexpected bidder_type value: {bt!r}"


def test_reference_converter_emits_redesigned_taxonomy_for_all_deals():
    required_new_columns = {
        "drop_initiator",
        "drop_reason_class",
        "final_round_announcement",
        "final_round_extension",
        "final_round_informal",
        "press_release_subject",
        "invited_to_formal_round",
        "submitted_formal_bid",
    }

    for slug in build_reference.DEAL_ROWS:
        payload = build_deal(slug)
        for ev in payload["events"]:
            assert ev["bid_note"] in VALID_BID_NOTES
            assert required_new_columns <= set(ev), (
                f"{slug} row {ev.get('BidderID')} missing redesigned columns"
            )
            assert ev.get("bidder_type") in ("s", "f", None)


def test_reference_converter_deal_object_uses_current_schema_fields_only():
    expected = {
        "TargetName",
        "Acquirer",
        "DateAnnounced",
        "DateEffective",
        "auction",
        "all_cash",
        "target_legal_counsel",
        "acquirer_legal_counsel",
        "bidder_registry",
        "deal_flags",
    }

    for slug in build_reference.DEAL_ROWS:
        assert set(build_deal(slug)["deal"]) == expected


def test_reference_converter_maps_source_rows_to_structured_modifiers():
    medivation = build_deal("medivation")
    press = next(
        ev for ev in medivation["events"]
        if ev.get("press_release_subject") == "bidder"
    )
    assert press["bid_note"] == "Press Release"

    imprivata = build_deal("imprivata")
    target_cut = next(
        ev for ev in imprivata["events"]
        if ev.get("bid_note") == "Drop"
        and ev.get("drop_initiator") == "target"
        and ev.get("drop_reason_class") == "never_advanced"
    )
    assert target_cut["bid_note"] == "Drop"
    assert target_cut["drop_initiator"] == "target"
    assert target_cut["drop_reason_class"] == "never_advanced"

    final_round = next(
        ev for ev in imprivata["events"]
        if ev.get("bid_note") == "Final Round"
        and ev.get("final_round_announcement") is True
        and ev.get("final_round_extension") is True
    )
    assert final_round["bid_note"] == "Final Round"
    assert final_round["final_round_announcement"] is True
    assert final_round["final_round_extension"] is True
    assert final_round["final_round_informal"] is False


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


def test_petsmart_executed_atomizes_to_five_rows():
    """C3 — petsmart's Buyer Group consortium emits 5 Executed rows
    (BC Partners + Caisse + GIC + StepStone + Longview), one per
    operational/economic member explicitly identified in the filing.
    """
    payload = build_deal("petsmart-inc")
    executed_rows = [ev for ev in payload["events"] if ev.get("bid_note") == "Executed"]
    assert len(executed_rows) == 5, (
        f"expected 5 atomized Executed rows for petsmart-inc; "
        f"got {len(executed_rows)}"
    )
    aliases = [ev.get("bidder_alias") for ev in executed_rows]
    expected = {"BC Partners, Inc.", "La Caisse", "GIC Pte Ltd",
                "StepStone Group", "Longview Asset Management"}
    assert set(aliases) == expected, (
        f"expected aliases {expected}; got {set(aliases)}"
    )


def test_petsmart_missing_executed_repair_is_declarative_and_evidence_checked():
    repair = build_reference.Q7_MISSING_EXECUTED_REPAIRS["petsmart-inc"]

    assert repair["template"]["bid_note"] == "Bid"
    assert repair["template"]["bidder_alias"] == "Buyer Group"
    assert repair["template"]["select"] == "latest"
    assert repair["executed_date"] == "2014-12-14"
    assert repair["members"] == [
        "BC Partners, Inc.",
        "La Caisse",
        "GIC Pte Ltd",
        "StepStone Group",
        "Longview Asset Management",
    ]

    build_reference.validate_q7_missing_executed_repair("petsmart-inc", repair)
    assert not hasattr(build_reference, "_petsmart_executed_template")
    assert not hasattr(build_reference, "Q7_SYNTHETIC_EXECUTED_DATE")


def test_missing_executed_repair_rejects_unverifiable_filing_evidence():
    repair = dict(build_reference.Q7_MISSING_EXECUTED_REPAIRS["petsmart-inc"])
    repair["membership_evidence"] = {
        "page": 2,
        "quote": "this quote is not in the local filing",
    }

    with pytest.raises(ValueError, match="membership_evidence"):
        build_reference.validate_q7_missing_executed_repair("petsmart-inc", repair)


def test_missing_executed_repair_rejects_unidentifiable_members():
    repair = dict(build_reference.Q7_MISSING_EXECUTED_REPAIRS["petsmart-inc"])
    repair["members"] = ["BC Partners, Inc.", "Unknown Party"]

    with pytest.raises(ValueError, match="unidentifiable member"):
        build_reference.validate_q7_missing_executed_repair("petsmart-inc", repair)


def test_mac_gray_executed_atomizes_to_two_rows():
    """C3 — mac-gray's CSC + Pamplona consortium emits 2 Executed rows."""
    payload = build_deal("mac-gray")
    executed_rows = [ev for ev in payload["events"] if ev.get("bid_note") == "Executed"]
    assert len(executed_rows) == 2, (
        f"expected 2 atomized Executed rows for mac-gray; "
        f"got {len(executed_rows)}"
    )
    aliases = [ev.get("bidder_alias") for ev in executed_rows]
    expected = {"CSC ServiceWorks, Inc.", "Pamplona Capital Partners"}
    assert set(aliases) == expected


def test_range_bid_with_formal_source_label_is_coerced_to_informal():
    """C4 — true range rows are informal after converter migration."""
    for slug in ("medivation", "imprivata", "zep", "providence-worcester",
                 "penford", "mac-gray", "petsmart-inc", "stec", "saks"):
        payload = build_deal(slug)
        for ev in payload["events"]:
            lower = ev.get("bid_value_lower")
            upper = ev.get("bid_value_upper")
            if lower is None or upper is None:
                continue
            if not (isinstance(lower, (int, float)) and isinstance(upper, (int, float))):
                continue
            if lower < upper:
                assert ev.get("bid_type") == "informal", (
                    f"{slug} row has range ({lower}..{upper}) but "
                    f"bid_type={ev.get('bid_type')!r}; expected informal "
                    f"per C4 auto-coerce."
                )

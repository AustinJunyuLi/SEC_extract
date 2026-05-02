from __future__ import annotations

from pipeline.core import Filing
from pipeline import obligations


def _filing(*texts: str) -> Filing:
    return Filing(
        slug="synthetic",
        pages=[
            {"number": index + 1, "content": text}
            for index, text in enumerate(texts)
        ],
    )


def _raw(events: list[dict]) -> dict:
    numbered_events = []
    for index, event in enumerate(events, start=1):
        row = dict(event)
        row["BidderID"] = index
        numbered_events.append(row)
    return {
        "deal": {
            "TargetName": "Synthetic Target",
            "Acquirer": "Synthetic Buyer",
            "DateAnnounced": None,
            "DateEffective": None,
            "auction": True,
            "all_cash": None,
            "target_legal_counsel": None,
            "acquirer_legal_counsel": None,
            "bidder_registry": {},
            "deal_flags": [],
        },
        "events": numbered_events,
    }


def _nda(alias: str, bidder_type: str = "f") -> dict:
    return {
        "BidderID": 1,
        "process_phase": 1,
        "role": "bidder",
        "bidder_alias": alias,
        "bidder_name": alias.casefold().replace(" ", "_"),
        "bidder_type": bidder_type,
        "bid_note": "NDA",
        "bid_date_precise": "2014-09-01",
        "bid_date_rough": None,
        "bid_type": None,
        "bid_type_inference_note": None,
        "source_quote": "entered into confidentiality and standstill agreements",
        "source_page": 1,
        "flags": [],
    }


def _bid(alias: str, bidder_type: str = "f") -> dict:
    row = _nda(alias, bidder_type)
    row.update({
        "bid_note": "Bid",
        "bid_type": "informal",
        "bid_type_inference_note": "G1 trigger phrase: indication of interest.",
    })
    return row


def _buyer_group_flags(alias: str) -> list[dict]:
    return [{
        "code": "buyer_group_constituent",
        "severity": "info",
        "reason": f"{alias} is a Buyer Group constituent.",
    }]


def _executed(alias: str) -> dict:
    row = _nda(alias)
    row.update({
        "bid_note": "Executed",
        "bid_date_precise": "2014-12-14",
        "source_quote": "Parent is controlled by BC Partners, La Caisse, GIC, and StepStone.",
        "source_page": 1,
    })
    return row


def _consortium(alias: str) -> dict:
    row = _nda(alias)
    row.update({
        "bid_note": "ConsortiumCA",
        "bid_date_precise": "2014-12-12",
        "source_quote": "Longview and the Buyer Group entered into a confidentiality agreement.",
        "source_page": 2,
    })
    return row


def test_exact_count_nda_obligation_requires_exact_current_process_count():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 15 potentially interested financial buyers."
    )
    result = obligations.check_obligations(
        _raw([_nda("Financial Buyer 1"), _nda("Financial Buyer 2")]),
        filing,
    )

    unmet = [item for item in result.checks if item.status == "unmet"]

    assert result.has_hard_unmet is True
    assert len(unmet) == 1
    assert unmet[0].obligation.kind == "exact_count_nda"
    assert unmet[0].obligation.expected == {"count": 15, "bidder_type": "f"}
    assert unmet[0].matched_rows == [1, 2]
    assert "expected exactly 15" in unmet[0].reason


def test_exact_count_nda_obligation_passes_when_count_matches():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 3 potentially interested financial buyers."
    )
    result = obligations.check_obligations(
        _raw([_nda("Financial Buyer 1"), _nda("Financial Buyer 2"), _nda("Financial Buyer 3")]),
        filing,
    )

    assert result.has_hard_unmet is False
    assert [check.status for check in result.checks] == ["satisfied"]
    assert result.checks[0].matched_rows == [1, 2, 3]


def test_exact_count_bid_obligation_requires_exact_submission_count():
    filing = _filing(
        "Six of the potentially interested parties submitted indications of interest."
    )
    result = obligations.check_obligations(
        _raw([_bid("Financial Buyer 1"), _bid("Financial Buyer 2")]),
        filing,
    )

    assert result.has_hard_unmet is True
    check = result.checks[0]
    assert check.obligation.kind == "exact_count_bid"
    assert check.obligation.expected == {"count": 6}
    assert check.matched_rows == [1, 2]


def test_exact_count_bid_obligation_matches_only_source_event_page():
    filing = _filing(
        "Six of the potentially interested parties submitted indications of interest.",
        "Later in the sale process, two bidders submitted final bids.",
    )
    events = []
    for index in range(6):
        row = _bid(f"Financial Buyer {index + 1}")
        row["source_page"] = 1
        events.append(row)
    for index in range(2):
        row = _bid(f"Final Bidder {index + 1}")
        row["source_page"] = 2
        events.append(row)

    result = obligations.check_obligations(_raw(events), filing)

    assert result.has_hard_unmet is False
    assert result.checks[0].matched_rows == [1, 2, 3, 4, 5, 6]


def test_exact_count_nda_collapses_buyer_group_constituents_to_one_party_unit():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 3 potentially interested financial buyers."
    )
    buyer_group_rows = []
    for alias in ["BC Partners", "La Caisse", "GIC", "StepStone"]:
        row = _nda(alias)
        row["source_quote"] = (
            "The Company entered into confidentiality and standstill agreements "
            "with 3 potentially interested financial buyers."
        )
        row["flags"] = _buyer_group_flags(alias)
        buyer_group_rows.append(row)

    result = obligations.check_obligations(
        _raw([*buyer_group_rows, _nda("Financial Buyer 1"), _nda("Financial Buyer 2")]),
        filing,
    )

    assert result.has_hard_unmet is False
    assert result.checks[0].matched_rows == [1, 5, 6]


def test_exact_count_bid_collapses_buyer_group_constituents_to_one_party_unit():
    filing = _filing(
        "Six of the potentially interested parties submitted indications of interest."
    )
    buyer_group_rows = []
    for alias in ["BC Partners", "La Caisse", "GIC", "StepStone"]:
        row = _bid(alias)
        row["source_quote"] = "Six of the potentially interested parties submitted indications of interest."
        row["flags"] = _buyer_group_flags(alias)
        buyer_group_rows.append(row)
    other_rows = [_bid(f"Financial Buyer {index}") for index in range(1, 6)]

    result = obligations.check_obligations(_raw([*buyer_group_rows, *other_rows]), filing)

    assert result.has_hard_unmet is False
    assert result.checks[0].matched_rows == [1, 5, 6, 7, 8, 9]


def test_exact_count_nda_obligation_ignores_late_member_nda_on_other_page():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 2 potentially interested financial buyers.",
        "Following the execution of a confidentiality agreement, Longview met with bidders.",
    )
    nda_1 = _nda("Financial Buyer 1")
    nda_1["source_page"] = 1
    nda_2 = _nda("Financial Buyer 2")
    nda_2["source_page"] = 1
    longview = _nda("Longview")
    longview["source_page"] = 2
    longview["flags"] = [{
        "code": "late_member_inherited_nda",
        "severity": "info",
        "reason": "Longview joined later.",
    }]

    result = obligations.check_obligations(_raw([nda_1, nda_2, longview]), filing)

    assert result.has_hard_unmet is False
    assert result.checks[0].matched_rows == [1, 2]


def test_obligation_flags_are_deal_level_hard_flags_with_source_context():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 4 potentially interested strategic buyers."
    )
    result = obligations.check_obligations(_raw([_nda("Strategic Buyer 1", "s")]), filing)

    flags = obligations.flags_for_unmet(result)

    assert flags == [{
        "code": "unmet_exact_count_nda",
        "severity": "hard",
        "reason": (
            "Obligation obl-001 exact_count_nda expected exactly 4 matching rows "
            "but found 1; source page 1."
        ),
        "deal_level": True,
        "obligation_id": "obl-001",
        "source_page": 1,
    }]


def test_buyer_group_definition_requires_constituent_executed_rows():
    filing = _filing(
        "Parent is controlled by funds advised by BC Partners and co-investors "
        "La Caisse, GIC and StepStone. These parties are referred to as the Buyer Group."
    )
    result = obligations.check_obligations(
        _raw([_executed("Buyer Group")]),
        filing,
    )

    check = next(
        item for item in result.checks
        if item.obligation.kind == "buyer_group_executed_constituents"
    )

    assert check.status == "unmet"
    assert check.obligation.expected["constituents"] == [
        "BC Partners",
        "La Caisse",
        "GIC",
        "StepStone",
    ]
    assert check.matched_rows == []


def test_buyer_group_constituents_do_not_match_bidder_3_cooperation_passage():
    filing = _filing(
        "Bidder 3 requested permission to work with another bidder.",
        "Parent is controlled by funds advised by BC Partners and co-investors "
        "La Caisse, GIC and StepStone. These parties are referred to as the Buyer Group.",
    )
    result = obligations.check_obligations(
        _raw([_executed("Bidder 3"), _executed("Other Bidder")]),
        filing,
    )

    check = next(
        item for item in result.checks
        if item.obligation.kind == "buyer_group_executed_constituents"
    )

    assert check.status == "unmet"
    assert check.matched_rows == []


def test_late_longview_join_requires_consortium_and_inherited_nda():
    filing = _filing(
        "Parent is controlled by funds advised by BC Partners and co-investors "
        "La Caisse, GIC and StepStone. These parties are referred to as the Buyer Group.",
        "On December 12, Longview and the Buyer Group entered into a confidentiality agreement."
    )
    result = obligations.check_obligations(
        _raw([_consortium("Longview")]),
        filing,
    )

    check = next(
        item for item in result.checks
        if item.obligation.kind == "late_member_inherited_nda"
    )

    assert check.status == "unmet"
    assert check.obligation.expected == {
        "member": "Longview",
        "requires_bid_notes": ["ConsortiumCA", "NDA"],
    }
    assert check.matched_rows == [1]


def test_repeated_filing_definitions_do_not_create_duplicate_obligations():
    filing = _filing(
        "The Company entered into confidentiality and standstill agreements "
        "with 15 potentially interested financial buyers. "
        "The Buyer Group refers to BC Partners, La Caisse, GIC and StepStone. "
        "On December 12, Longview and the Buyer Group entered into a confidentiality agreement.",
        "The confidentiality agreements entered into by 15 potentially interested parties "
        "were amended. Parent will be owned by a consortium comprised of BC Partners, "
        "La Caisse, GIC, StepStone and Longview. "
        "On December 12, Longview and the Buyer Group entered into a confidentiality agreement.",
    )

    kinds = [obligation.kind for obligation in obligations.derive_obligations(filing)]

    assert kinds.count("exact_count_nda") == 1
    assert kinds.count("buyer_group_executed_constituents") == 1
    assert kinds.count("late_member_inherited_nda") == 1

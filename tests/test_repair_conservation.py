from pipeline import repair_conservation


def _row(bidder: str, note: str, date: str, page: int = 1) -> dict:
    return {
        "BidderID": 1,
        "bidder_alias": bidder,
        "bidder_name": bidder.casefold().replace(" ", "_"),
        "bid_note": note,
        "bid_date_precise": date,
        "bid_date_rough": None,
        "bid_value_pershare": None,
        "bid_value_lower": None,
        "bid_value_upper": None,
        "bid_value_unit": None,
        "source_page": page,
        "source_quote": f"{bidder} {note} {date} source text",
        "flags": [],
    }


def test_repair_conservation_flags_deleted_unaffected_rows():
    before = {"events": [_row("A", "NDA", "2020-01-01"), _row("B", "Bid", "2020-01-02")]}
    after = {"events": [_row("B", "Bid", "2020-01-02")]}
    anchors = repair_conservation.protected_anchors(
        before,
        hard_row_indexes={1},
        obligation_row_indexes=set(),
    )

    flags = repair_conservation.check_repair_conservation(anchors, after)

    assert flags == [{
        "code": "repair_lost_unaffected_rows",
        "severity": "hard",
        "reason": (
            "Repair deleted or failed to preserve protected row anchor: "
            "NDA a on 2020-01-01 page 1."
        ),
        "deal_level": True,
        "anchor_index": 0,
    }]


def test_repair_conservation_allows_implicated_rows_to_change():
    before = {"events": [_row("A", "NDA", "2020-01-01"), _row("B", "Bid", "2020-01-02")]}
    after = {"events": [_row("B", "Bid", "2020-01-02")]}
    anchors = repair_conservation.protected_anchors(
        before,
        hard_row_indexes={0},
        obligation_row_indexes=set(),
    )

    assert repair_conservation.check_repair_conservation(anchors, after) == []

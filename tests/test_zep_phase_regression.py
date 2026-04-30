from pipeline import core


def _row(phase, note, date):
    return {
        "process_phase": phase,
        "role": "bidder",
        "bid_note": note,
        "bid_date_precise": date,
    }


def test_zep_2014_abandoned_process_is_stale_when_2015_gap_exceeds_180_days():
    events = [
        _row(0, "Bidder Interest", "2013-07-01"),
        _row(0, "Drop", "2013-08-20"),
        _row(0, "Target Sale", "2014-01-28"),
        _row(0, "NDA", "2014-02-14"),
        _row(0, "Drop", "2014-06-26"),
        _row(1, "Bidder Interest", "2015-02-10"),
        _row(1, "NDA", "2015-02-27"),
        _row(1, "Bid", "2015-03-18"),
        _row(1, "Executed", "2015-04-07"),
    ]

    assert core._invariant_p_l2(events) == []


def test_zep_current_process_single_nda_keeps_auction_false():
    deal = {"auction": False}
    events = [
        _row(0, "NDA", "2014-02-14"),
        _row(1, "NDA", "2015-02-27"),
    ]

    assert core._invariant_p_s2(deal, events) == []


def test_zep_old_bad_split_triggers_stale_prior_interval_flag():
    events = [
        _row(0, "Bidder Interest", "2013-07-01"),
        _row(0, "Drop", "2013-08-20"),
        _row(1, "Target Sale", "2014-01-28"),
        _row(1, "NDA", "2014-02-14"),
        _row(1, "Drop", "2014-06-26"),
        _row(2, "Bidder Interest", "2015-02-10"),
    ]

    flags = core._invariant_p_l2(events)

    assert [flag["code"] for flag in flags] == ["stale_prior_too_recent"]

"""Tests for the US-008 NDA gap-fill transform."""
import pipeline


def _nda(bidder_name: str, alias: str = "Party X", source: str = "llm") -> dict:
    return {
        "bid_note": "NDA",
        "source": source,
        "bidder_name": bidder_name,
        "bidder_alias": alias,
        "bidder_type": {"base": "f", "non_us": False, "public": False},
        "source_quote": f"{alias} signed a confidentiality agreement",
        "source_page": 1,
        "bid_date_precise": "2020-01-10",
    }


def _drop(bidder_name: str, alias: str = "Party X") -> dict:
    return {
        "bid_note": "Drop",
        "source": "llm",
        "bidder_name": bidder_name,
        "bidder_alias": alias,
        "source_quote": f"{alias} withdrew",
        "source_page": 5,
    }


def test_synthesizes_drop_when_no_closure():
    raw = {
        "events": [_nda("bidder_01", "Party A")]
    }
    log = pipeline._gapfill_nda_signers(raw)
    assert len(log) == 1
    assert log[0]["type"] == "gap_fill"
    assert log[0]["bidder_key"] == "name:bidder_01"
    events = raw["events"]
    assert len(events) == 2
    synthesized = events[-1]
    assert synthesized["source"] == "code_gap_fill"
    assert synthesized["bid_note"] == "Drop"
    assert synthesized["bidder_name"] == "bidder_01"
    assert synthesized["bid_date_rough"] == "end of process"
    assert synthesized["bid_date_precise"] is None
    assert synthesized["source_page"] is None
    assert synthesized["source_quote"].startswith("[synthesized:")
    assert any(f["code"] == "nda_gap_fill_synthesized" for f in synthesized["flags"])


def test_no_synthesis_when_explicit_drop():
    raw = {
        "events": [_nda("bidder_01", "Party A"), _drop("bidder_01", "Party A")]
    }
    log = pipeline._gapfill_nda_signers(raw)
    assert log == []
    assert len(raw["events"]) == 2


def test_no_synthesis_when_executed():
    raw = {
        "events": [
            _nda("bidder_01", "Acquirer Inc"),
            {
                "bid_note": "Executed",
                "source": "llm",
                "bidder_name": "bidder_01",
                "bidder_alias": "Acquirer Inc",
                "source_quote": "executed the merger",
                "source_page": 42,
            },
        ]
    }
    pipeline._gapfill_nda_signers(raw)
    assert len(raw["events"]) == 2


def test_no_synthesis_when_drop_target():
    raw = {
        "events": [
            _nda("bidder_01", "Party A"),
            {
                "bid_note": "DropTarget",
                "source": "llm",
                "bidder_name": "bidder_01",
                "bidder_alias": "Party A",
                "source_quote": "Company declined to advance Party A",
                "source_page": 8,
            },
        ]
    }
    pipeline._gapfill_nda_signers(raw)
    assert len(raw["events"]) == 2


def test_mixed_closure_status_only_open_ones_get_synthesized():
    raw = {
        "events": [
            _nda("bidder_01", "Party A"),
            _nda("bidder_02", "Party B"),
            _nda("bidder_03", "Party C"),
            _drop("bidder_02", "Party B"),
        ]
    }
    pipeline._gapfill_nda_signers(raw)
    # Expect synthesized drops for bidder_01 and bidder_03 (not bidder_02).
    syn = [ev for ev in raw["events"] if ev.get("source") == "code_gap_fill"]
    assert len(syn) == 2
    keys = {ev["bidder_name"] for ev in syn}
    assert keys == {"bidder_01", "bidder_03"}


def test_cohort_atomic_rows_get_individual_gap_fill():
    """Post-US-007 atomic rows identified by bidder_alias get per-slot gap-fills."""
    raw = {
        "events": [
            {
                "bid_note": "NDA",
                "source": "code_cohort_expansion",
                "bidder_name": None,
                "bidder_alias": "Financial 1",
                "source_quote": "[synthesized: ...]",
                "source_page": 7,
            },
            {
                "bid_note": "NDA",
                "source": "code_cohort_expansion",
                "bidder_name": None,
                "bidder_alias": "Financial 2",
                "source_quote": "[synthesized: ...]",
                "source_page": 7,
            },
            {
                "bid_note": "Drop",
                "source": "llm",
                "bidder_name": None,
                "bidder_alias": "Financial 2",
                "source_quote": "Financial 2 withdrew",
                "source_page": 10,
            },
        ]
    }
    pipeline._gapfill_nda_signers(raw)
    synthesized = [ev for ev in raw["events"] if ev.get("source") == "code_gap_fill"]
    assert len(synthesized) == 1
    assert synthesized[0]["bidder_alias"] == "Financial 1"


def test_gap_fill_runs_in_prepare_for_validate(monkeypatch):
    raw = {
        "deal": {"bidder_registry": {}},
        "events": [_nda("bidder_01", "Party A")]
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "x"}])
    prepared, _, _ = pipeline.prepare_for_validate("synthetic", raw, filing=filing)
    assert len(prepared["events"]) == 2
    synthesized = next(ev for ev in prepared["events"] if ev.get("source") == "code_gap_fill")
    assert synthesized["bid_note"] == "Drop"
    assert any(
        entry["type"] == "gap_fill"
        for entry in prepared.get("normalization_log", [])
    )


def test_cohort_expansion_plus_gap_fill_end_to_end():
    """Providence-worcester pattern: aggregate NDA cohort with no closures."""
    raw = {
        "deal": {"bidder_registry": {}},
        "events": [
            {
                "bid_note": "NDA",
                "source": "llm",
                "bidder_alias": "3 financial buyers",
                "bidder_name": None,
                "source_quote": "three financial buyers executed CAs",
                "source_page": 1,
                "bid_date_precise": "2020-02-10",
                "bidder_type": {"base": "f", "non_us": False, "public": False},
            }
        ]
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "x"}])
    prepared, _, _ = pipeline.prepare_for_validate("synthetic", raw, filing=filing)
    # Expect: 3 atomic cohort rows + 3 synthesized gap-fill Drops = 6 total.
    assert len(prepared["events"]) == 6
    atomic_ndas = [ev for ev in prepared["events"] if ev.get("bid_note") == "NDA"]
    assert len(atomic_ndas) == 3
    assert all(ev["source"] == "code_cohort_expansion" for ev in atomic_ndas)
    synthesized_drops = [
        ev for ev in prepared["events"]
        if ev.get("bid_note") == "Drop" and ev.get("source") == "code_gap_fill"
    ]
    assert len(synthesized_drops) == 3

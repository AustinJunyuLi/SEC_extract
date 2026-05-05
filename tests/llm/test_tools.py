import pytest

from pipeline.llm import tools


def _filing_pages():
    return [
        {
            "number": 22,
            "content": "On May 15, 2014, the Special Committee met to discuss the offer.",
        }
    ]


def _clean_bid_row():
    return {
        "BidderID": 1,
        "process_phase": 1,
        "role": "bidder",
        "bidder_alias": "Bidder F",
        "bidder_name": "bidder_f",
        "bidder_type": "f",
        "bid_note": "Bid",
        "bid_type": "informal",
        "bid_type_inference_note": "G1 trigger phrase: preliminary indication of interest.",
        "exclusivity_days": None,
        "drop_initiator": None,
        "drop_reason_class": None,
        "final_round_announcement": None,
        "final_round_extension": None,
        "final_round_informal": None,
        "press_release_subject": None,
        "invited_to_formal_round": None,
        "submitted_formal_bid": None,
        "bid_date_precise": "2014-05-15",
        "bid_date_rough": None,
        "bid_value": None,
        "bid_value_pershare": 25.0,
        "bid_value_lower": None,
        "bid_value_upper": None,
        "bid_value_unit": "USD_per_share",
        "consideration_components": ["cash"],
        "additional_note": None,
        "comments": None,
        "unnamed_nda_promotion": None,
        "source_quote": "On May 15, 2014, the Special Committee met to discuss the offer.",
        "source_page": 22,
        "flags": [],
    }


def test_check_row_passes_clean_bid_row():
    result = tools.check_row(_clean_bid_row(), filing_pages=_filing_pages())

    assert result["ok"] is True
    assert result["violations"] == []


def test_check_row_catches_p_r9_violation_on_executed_row():
    row = {
        "BidderID": 1,
        "process_phase": 1,
        "role": "bidder",
        "bidder_alias": "G&W",
        "bidder_type": "s",
        "bid_note": "Executed",
        "bid_value_pershare": 25.0,
        "bid_value_unit": "USD_per_share",
        "consideration_components": ["cash"],
        "source_quote": "On May 15, 2014, the Special Committee met to discuss the offer.",
        "source_page": 22,
        "flags": [],
    }

    result = tools.check_row(row, filing_pages=_filing_pages())

    assert result["ok"] is False
    codes = {violation["code"] for violation in result["violations"]}
    assert "conditional_field_mismatch" in codes


def test_check_row_catches_quote_not_in_page():
    row = _clean_bid_row()
    row["source_quote"] = "This text does not appear anywhere on page 22."

    result = tools.check_row(row, filing_pages=_filing_pages())

    assert result["ok"] is False
    codes = {violation["code"] for violation in result["violations"]}
    assert "source_quote_not_in_page" in codes


def test_search_filing_finds_substring_returns_page_and_snippet():
    pages = [
        {"number": 5, "content": "Pre-merger discussions began in early 2013."},
        {"number": 22, "content": "On May 15, 2014, the Special Committee met."},
        {"number": 41, "content": "by and among Acquirer and BC Partners and La Caisse."},
    ]

    result = tools.search_filing(
        "BC Partners",
        filing_pages=pages,
        page_range=None,
        max_hits=10,
    )

    hits = result["hits"]
    assert len(hits) == 1
    assert hits[0]["page"] == 41
    assert "BC Partners" in hits[0]["snippet"]


def test_search_filing_respects_page_range():
    pages = [
        {"number": 1, "content": "Match here."},
        {"number": 10, "content": "Match here."},
        {"number": 50, "content": "Match here."},
    ]

    result = tools.search_filing(
        "Match",
        filing_pages=pages,
        page_range=[5, 20],
        max_hits=10,
    )

    assert {hit["page"] for hit in result["hits"]} == {10}


def test_search_filing_caps_at_max_hits():
    pages = [{"number": i, "content": "match"} for i in range(1, 21)]

    result = tools.search_filing(
        "match",
        filing_pages=pages,
        page_range=None,
        max_hits=3,
    )

    assert len(result["hits"]) == 3


def test_get_pages_returns_contiguous_pages():
    pages = [{"number": i, "content": f"page {i} text"} for i in range(20, 30)]

    result = tools.get_pages(start_page=22, end_page=24, filing_pages=pages)

    assert [page["page"] for page in result["pages"]] == [22, 23, 24]
    assert result["pages"][0]["text"] == "page 22 text"


def test_get_pages_rejects_range_over_cap():
    pages = [{"number": i, "content": "x"} for i in range(1, 100)]

    with pytest.raises(ValueError, match="page range too wide"):
        tools.get_pages(start_page=1, end_page=20, filing_pages=pages)


def test_get_pages_skips_missing_page_numbers():
    pages = [{"number": 22, "content": "x"}, {"number": 24, "content": "y"}]

    result = tools.get_pages(start_page=22, end_page=24, filing_pages=pages)

    assert {page["page"] for page in result["pages"]} == {22, 24}


def test_targeted_repair_tool_definitions_include_expected_tools_only():
    names = {tool["name"] for tool in tools.TARGETED_REPAIR_TOOL_DEFINITIONS}

    assert names == {"check_row", "search_filing", "get_pages", "check_obligations"}


def test_no_generic_extractor_tool_catalog_is_exposed():
    assert not hasattr(tools, "TOOL_DEFINITIONS")


def test_dispatch_invokes_check_row():
    result = tools.dispatch(
        name="check_row",
        arguments={"row": _clean_bid_row()},
        filing_pages=_filing_pages(),
    )

    assert result == {"ok": True, "violations": []}


def test_dispatch_accepts_unwrapped_check_row_arguments():
    result = tools.dispatch(
        name="check_row",
        arguments=_clean_bid_row(),
        filing_pages=_filing_pages(),
    )

    assert result == {"ok": True, "violations": []}


def test_dispatch_invokes_search_filing():
    result = tools.dispatch(
        name="search_filing",
        arguments={"query": "Special Committee", "page_range": None, "max_hits": 5},
        filing_pages=_filing_pages(),
    )

    assert result["hits"]
    assert result["hits"][0]["page"] == 22


def test_dispatch_invokes_get_pages():
    result = tools.dispatch(
        name="get_pages",
        arguments={"start_page": 22, "end_page": 22},
        filing_pages=_filing_pages(),
    )

    assert result["pages"] == [{"page": 22, "text": _filing_pages()[0]["content"]}]


def test_dispatch_rejects_retired_check_obligations_tool():
    with pytest.raises(RuntimeError, match="retired under deal_graph_v1"):
        tools.dispatch(
            name="check_obligations",
            arguments={"candidate_extraction": {"deal": {}, "events": []}},
            filing_pages=_filing_pages(),
        )


def test_check_obligations_rejects_partial_candidate_extractions():
    with pytest.raises(RuntimeError, match="retired under deal_graph_v1"):
        tools.check_obligations(
            {"deal": {}, "events": []},
            filing_pages=_filing_pages(),
        )


def test_tools_contract_version_is_stable_hash():
    first = tools.tools_contract_version()
    second = tools.tools_contract_version()

    assert first == second
    assert len(first) == 16

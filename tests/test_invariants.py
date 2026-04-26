import json
from pathlib import Path

import pytest

import pipeline


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _make_filing(fixture: dict) -> pipeline.Filing:
    return pipeline.Filing(
        slug=fixture.get("slug", "synthetic"),
        pages=fixture.get("pages", [{"number": 1, "content": ""}]),
    )


def _flatten(result: pipeline.ValidatorResult) -> list[dict]:
    return result.row_flags + result.deal_flags


RUNNERS = {
    "pr1": lambda fixture: pipeline._invariant_p_r1(
        {
            "deal": fixture.get("deal", {}),
            "events": fixture.get("events"),
        }
    ),
    "validate": lambda fixture: _flatten(
        pipeline.validate(
            {
                "deal": fixture.get("deal", {}),
                "events": fixture.get("events", []),
            },
            _make_filing(fixture),
        )
    ),
    "pr2": lambda fixture: pipeline._invariant_p_r2(
        fixture.get("events", []),
        _make_filing(fixture),
    ),
    "pr3": lambda fixture: pipeline._invariant_p_r3(fixture.get("events", [])),
    "pr4": lambda fixture: pipeline._invariant_p_r4(fixture.get("events", [])),
    "pr5": lambda fixture: pipeline._invariant_p_r5(
        fixture.get("events", []),
        fixture.get("deal", {}),
    ),
    "pd1": lambda fixture: pipeline._invariant_p_d1(fixture.get("events", [])),
    "pd2": lambda fixture: pipeline._invariant_p_d2(fixture.get("events", [])),
    "pd3": lambda fixture: pipeline._invariant_p_d3(fixture.get("events", [])),
    "pd5": lambda fixture: pipeline._invariant_p_d5(fixture.get("events", [])),
    "pd6": lambda fixture: pipeline._invariant_p_d6(fixture.get("events", [])),
    "ph5": lambda fixture: pipeline._invariant_p_h5(fixture.get("events", [])),
    "pl1": lambda fixture: pipeline._invariant_p_l1(fixture.get("events", [])),
    "pl2": lambda fixture: pipeline._invariant_p_l2(fixture.get("events", [])),
    "pg2": lambda fixture: pipeline._invariant_p_g2(fixture.get("events", [])),
    "ps1": lambda fixture: pipeline._invariant_p_s1(fixture.get("events", [])),
    "ps2": lambda fixture: pipeline._invariant_p_s2(
        fixture.get("deal", {}),
        fixture.get("events", []),
    ),
    "ps3": lambda fixture: pipeline._invariant_p_s3(
        fixture.get("deal", {}),
        fixture.get("events", []),
    ),
    "ps4": lambda fixture: pipeline._invariant_p_s4(fixture.get("events", [])),
}


def _assert_fixture(fixture_name: str, runner_key: str) -> None:
    fixture = _load_fixture(fixture_name)
    actual_flags = RUNNERS[runner_key](fixture)
    expected_flags = fixture.get("expected_flags", [])
    assert len(actual_flags) == len(expected_flags)
    for expected in expected_flags:
        assert any(
            all(flag.get(k) == v for k, v in expected.items())
            for flag in actual_flags
        ), actual_flags


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr1_pass.json", "synthetic_pr1_fail.json"],
)
def test_pr1(fixture_name):
    _assert_fixture(fixture_name, "pr1")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr1_pass.json", "synthetic_pr1_fail.json"],
)
def test_pr1_validate(fixture_name):
    _assert_fixture(fixture_name, "validate")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr2_pass.json", "synthetic_pr2_fail.json"],
)
def test_pr2(fixture_name):
    _assert_fixture(fixture_name, "pr2")


@pytest.mark.parametrize(
    "fixture_name",
    ["pr2_curly_quote_accepted.json", "pr2_paraphrase_rejected.json"],
)
def test_pr2_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "pr2")


def test_pr2_rejects_whitespace_only_quote():
    flags = pipeline._invariant_p_r2(
        [{"source_quote": "   ", "source_page": 1}],
        pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "real text"}]),
    )

    assert flags == [
        {
            "row_index": 0,
            "code": "missing_evidence",
            "severity": "hard",
            "reason": "source_quote element is empty after trimming whitespace",
        }
    ]


def test_pr2_rejects_whitespace_only_multi_quote_element():
    """A multi-quote list with one valid element and one whitespace-only
    element must flag the whitespace one (and only the whitespace one)."""
    flags = pipeline._invariant_p_r2(
        [{"source_quote": ["real text", "   "], "source_page": [1, 1]}],
        pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "real text"}]),
    )

    assert len(flags) == 1
    assert flags[0]["code"] == "missing_evidence"
    assert flags[0]["row_index"] == 0
    assert "empty after trimming whitespace" in flags[0]["reason"]


def test_pr2_multi_quote_distinguishes_paraphrase_from_whitespace():
    """A multi-quote list with a paraphrase element AND a whitespace element
    must produce TWO distinct flags with different codes, both tied to the
    same row. Guards against the previous `any(...)` assertion that would
    have passed even if only one failure fired."""
    flags = pipeline._invariant_p_r2(
        [{"source_quote": ["not on page", "   "], "source_page": [1, 1]}],
        pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": "real text"}]),
    )

    codes = [f["code"] for f in flags]
    assert "source_quote_not_in_page" in codes
    assert "missing_evidence" in codes
    assert all(f["row_index"] == 0 for f in flags)


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr3_pass.json", "synthetic_pr3_fail.json"],
)
def test_pr3(fixture_name):
    _assert_fixture(fixture_name, "pr3")


@pytest.mark.parametrize(
    "fixture_name",
    ["pr3_null_bid_note.json"],
)
def test_pr3_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "pr3")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr4_pass.json", "synthetic_pr4_fail.json"],
)
def test_pr4(fixture_name):
    _assert_fixture(fixture_name, "pr4")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pr5_pass.json", "synthetic_pr5_fail.json"],
)
def test_pr5(fixture_name):
    _assert_fixture(fixture_name, "pr5")


@pytest.mark.parametrize(
    "fixture_name",
    ["pr5_alias_mismatch.json", "pr5_resolved_name_mismatch.json"],
)
def test_pr5_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "pr5")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pd1_pass.json", "synthetic_pd1_fail.json"],
)
def test_pd1(fixture_name):
    _assert_fixture(fixture_name, "pd1")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pd2_pass.json", "synthetic_pd2_fail.json"],
)
def test_pd2(fixture_name):
    _assert_fixture(fixture_name, "pd2")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pd3_pass.json", "synthetic_pd3_fail.json"],
)
def test_pd3(fixture_name):
    _assert_fixture(fixture_name, "pd3")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pd5_pass.json", "synthetic_pd5_fail.json"],
)
def test_pd5(fixture_name):
    _assert_fixture(fixture_name, "pd5")


@pytest.mark.parametrize(
    "fixture_name",
    ["pd5_drop_after_nda_same_phase.json", "pd5_drop_orphan.json"],
)
def test_pd5_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "pd5")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pd6_pass.json", "synthetic_pd6_fail.json"],
)
def test_pd6(fixture_name):
    _assert_fixture(fixture_name, "pd6")


@pytest.mark.parametrize(
    "fixture_name",
    ["ph5_out_of_order.json", "ph5_in_order.json"],
)
def test_ph5(fixture_name):
    _assert_fixture(fixture_name, "ph5")


@pytest.mark.parametrize(
    "fixture_name",
    ["pl1_phase2_without_restart.json", "pl1_phase2_with_pair.json"],
)
def test_pl1(fixture_name):
    _assert_fixture(fixture_name, "pl1")


@pytest.mark.parametrize(
    "fixture_name",
    ["pl2_stale_prior_too_recent.json", "pl2_stale_prior_ok.json"],
)
def test_pl2(fixture_name):
    _assert_fixture(fixture_name, "pl2")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pg2_pass.json", "synthetic_pg2_fail.json"],
)
def test_pg2(fixture_name):
    _assert_fixture(fixture_name, "pg2")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "pg2_range_valid.json",
        "pg2_range_inverted.json",
        "pg2_range_nonnumeric.json",
        "pg2_note_formal_process_position.json",
        "pg2_note_informal_process_position.json",
        "pg2_note_empty.json",
        "pg2_note_over_cap.json",
        "pg2_note_at_cap.json",
    ],
)
def test_pg2_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "pg2")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "synthetic_ps1_pass.json",
        "synthetic_ps1_fail.json",
        "synthetic_ps1_dropsilent_pass.json",
    ],
)
def test_ps1(fixture_name):
    _assert_fixture(fixture_name, "ps1")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_ps2_pass.json", "synthetic_ps2_fail.json"],
)
def test_ps2(fixture_name):
    _assert_fixture(fixture_name, "ps2")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_ps3_pass.json", "synthetic_ps3_fail.json"],
)
def test_ps3(fixture_name):
    _assert_fixture(fixture_name, "ps3")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "ps3_terminator_mid_phase.json",
        "ps3_no_terminator.json",
        "ps3_phase0_no_terminator_exempt.json",
    ],
)
def test_ps3_acceptance_fixtures(fixture_name):
    _assert_fixture(fixture_name, "ps3")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_ps4_pass.json", "synthetic_ps4_fail.json"],
)
def test_ps4(fixture_name):
    _assert_fixture(fixture_name, "ps4")


@pytest.mark.parametrize(
    ("final_extraction", "expected_counts", "expected_status"),
    [
        (
            {"deal": {}, "events": []},
            {"hard": 0, "soft": 0, "info": 0},
            "passed_clean",
        ),
        (
            {
                "deal": {},
                "events": [
                    {"flags": [{"code": "soft_flag", "severity": "soft"}]},
                ],
            },
            {"hard": 0, "soft": 1, "info": 0},
            "passed",
        ),
        (
            {
                "deal": {
                    "deal_flags": [{"code": "hard_flag", "severity": "hard"}],
                },
                "events": [
                    {"flags": [{"code": "info_flag", "severity": "info"}]},
                ],
            },
            {"hard": 1, "soft": 0, "info": 1},
            "validated",
        ),
        (
            {
                "deal": {},
                "events": [
                    {"flags": [{"code": "info_flag", "severity": "info"}]},
                ],
            },
            {"hard": 0, "soft": 0, "info": 1},
            "passed",
        ),
    ],
)
def test_count_flags(final_extraction, expected_counts, expected_status):
    assert pipeline.count_flags(final_extraction) == expected_counts
    status, flag_count, notes = pipeline.summarize(final_extraction)
    assert status == expected_status
    assert flag_count == sum(expected_counts.values())
    assert notes == (
        f"hard={expected_counts['hard']} "
        f"soft={expected_counts['soft']} info={expected_counts['info']}"
    )

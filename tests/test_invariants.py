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
    ["synthetic_pr3_pass.json", "synthetic_pr3_fail.json"],
)
def test_pr3(fixture_name):
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
    ["synthetic_pd6_pass.json", "synthetic_pd6_fail.json"],
)
def test_pd6(fixture_name):
    _assert_fixture(fixture_name, "pd6")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_pg2_pass.json", "synthetic_pg2_fail.json"],
)
def test_pg2(fixture_name):
    _assert_fixture(fixture_name, "pg2")


@pytest.mark.parametrize(
    "fixture_name",
    ["synthetic_ps1_pass.json", "synthetic_ps1_fail.json"],
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

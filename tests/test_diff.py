from scoring import diff as scoring_diff


def test_normalize_bidder_strips_exact_suffixes():
    assert scoring_diff.normalize_bidder("Penford Inc") == "penford"
    assert scoring_diff.normalize_bidder("Alco") == "alco"
    assert scoring_diff.normalize_bidder("SomeCo, Inc.") == "someco"

import pytest

from risk import classify_risk


def test_low_risk_auto_approve():
    decision = classify_risk(tamper_score=8.0, authentic_confidence=92.0)
    assert decision.risk_tier == "Low"
    assert decision.intervention == "AUTO_APPROVE"


def test_medium_risk_manual_review_at_80_to_90_gap():
    decision = classify_risk(tamper_score=15.0, authentic_confidence=85.0)
    assert decision.risk_tier == "Medium"
    assert decision.intervention == "MANUAL_REVIEW"


def test_medium_risk_manual_review_at_60_boundary():
    decision = classify_risk(tamper_score=25.0, authentic_confidence=60.0)
    assert decision.risk_tier == "Medium"


def test_high_risk_low_authentic_confidence():
    decision = classify_risk(tamper_score=30.0, authentic_confidence=59.99)
    assert decision.risk_tier == "High"
    assert decision.intervention == "BLOCK_AND_ESCALATE"
    assert decision.flagged_status == "Suspicious"


def test_high_risk_high_tamper_score_overrides_confidence():
    decision = classify_risk(tamper_score=40.0, authentic_confidence=95.0)
    assert decision.risk_tier == "High"


@pytest.mark.parametrize(
    "tamper_score, authentic_confidence",
    [(-0.1, 80.0), (100.1, 80.0), (20.0, -1.0), (20.0, 101.0)],
)
def test_invalid_scores_rejected(tamper_score, authentic_confidence):
    with pytest.raises(ValueError):
        classify_risk(
            tamper_score=tamper_score,
            authentic_confidence=authentic_confidence,
        )

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    risk_tier: str
    intervention: str
    flagged_status: str
    reason: str


def classify_risk(*, tamper_score: float, authentic_confidence: float) -> RiskDecision:
    """Map model outputs to one exhaustive operational action.

    Thresholds intentionally cover 100% of the score space. The original
    business brief leaves 80-90% confidence undefined, so that interval is
    conservatively assigned to manual review.
    """
    if not 0 <= tamper_score <= 100:
        raise ValueError("tamper_score must be between 0 and 100")
    if not 0 <= authentic_confidence <= 100:
        raise ValueError("authentic_confidence must be between 0 and 100")

    if authentic_confidence < 60 or tamper_score >= 40:
        return RiskDecision(
            risk_tier="High",
            intervention="BLOCK_AND_ESCALATE",
            flagged_status="Suspicious",
            reason="Low authentic confidence or high tamper probability",
        )

    if authentic_confidence >= 90 and tamper_score < 20:
        return RiskDecision(
            risk_tier="Low",
            intervention="AUTO_APPROVE",
            flagged_status="Authentic",
            reason="High authentic confidence with low tamper probability",
        )

    return RiskDecision(
        risk_tier="Medium",
        intervention="MANUAL_REVIEW",
        flagged_status="Authentic" if tamper_score < 40 else "Suspicious",
        reason="Uncertain score band requires human verification",
    )

"""
Confidence Scorer
=================
Aggregates findings from all detection strategies into an overall
hallucination risk score and a per-category breakdown.

Scoring model:
    - Each finding contributes a weighted risk delta
    - Weights are based on severity and per-category confidence
    - Final score is a 0-100 scale (0 = no risk, 100 = almost certainly hallucinated)
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict

from .utils import Finding, Severity, sigmoid, clamp


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of the hallucination risk score."""
    overall: float                           # 0-100 overall risk score
    risk_level: str                          # LOW / MODERATE / HIGH / CRITICAL
    by_category: Dict[str, float] = field(default_factory=dict)  # per-category risk
    by_severity: Dict[str, int] = field(default_factory=dict)      # count by severity
    total_findings: int = 0
    top_issues: List[str] = field(default_factory=list)           # top issue descriptions

    def to_dict(self) -> dict:
        return {
            "overall_risk_score": round(self.overall, 1),
            "risk_level": self.risk_level,
            "total_findings": self.total_findings,
            "by_category": {k: round(v, 1) for k, v in self.by_category.items()},
            "by_severity": self.by_severity,
            "top_issues": self.top_issues,
        }


class ConfidenceScorer:
    """Calculates hallucination risk scores from findings."""

    # Severity → base weight
    SEVERITY_WEIGHTS = {
        Severity.CRITICAL: 40.0,
        Severity.HIGH: 22.0,
        Severity.MEDIUM: 10.0,
        Severity.LOW: 4.0,
        Severity.INFO: 0.0,
    }

    # Category-specific multipliers (some categories are stronger signals)
    CATEGORY_MULTIPLIERS = {
        "url_dns_failure": 1.5,
        "url_404": 1.4,
        "fake_url_domain": 1.5,
        "fake_citation": 1.3,
        "doi_not_found": 1.3,
        "arxiv_not_found": 1.3,
        "internal_contradiction": 1.2,
        "number_not_found": 1.1,
        "source_not_found": 1.1,
        "possibly_fake_study": 1.1,
        "hyper_specific_number": 0.9,
        "possible_fake_entity": 1.0,
        "excessive_hedging": 0.7,
        "excessive_overconfidence": 0.6,
        "excessive_flavor_text": 0.4,
        "repetitive_phrasing": 0.3,
        "unverifiable_claim": 0.8,
        "offline_risk_indicators": 0.5,
        "suspicious_url": 1.0,
        "unknown_tld": 0.8,
        "url_timeout": 0.6,
        "url_connection_error": 0.5,
        "url_check_failed": 0.3,
        "verification_skipped": 0.0,
    }

    # Risk level thresholds (on the 0-100 scale)
    RISK_THRESHOLDS = [
        (70.0, "CRITICAL"),
        (45.0, "HIGH"),
        (25.0, "MODERATE"),
        (0.0, "LOW"),
    ]

    def score(self, findings: List[Finding]) -> ScoreBreakdown:
        """Calculate the overall hallucination risk score from findings."""
        if not findings:
            return ScoreBreakdown(
                overall=0.0,
                risk_level="LOW",
                total_findings=0,
                by_category={},
                by_severity={},
                top_issues=["No issues detected"],
            )

        total_score = 0.0
        by_category = defaultdict(float)
        by_severity = defaultdict(int)
        all_issues = []

        for finding in findings:
            # Get base weight from severity
            base_weight = self.SEVERITY_WEIGHTS.get(finding.severity, 0.0)

            # Apply category multiplier
            multiplier = self.CATEGORY_MULTIPLIERS.get(finding.category, 1.0)

            # Apply finding's own confidence
            confidence = clamp(finding.confidence, 0.0, 1.0)

            # Calculate this finding's contribution
            contribution = base_weight * multiplier * (0.5 + 0.5 * confidence)

            total_score += contribution
            by_category[finding.category] += contribution
            by_severity[finding.severity.to_plain()] += 1

            all_issues.append((contribution, f"[{finding.severity.to_plain()}] {finding.category}: {finding.message}"))

        # Apply diminishing returns — each additional finding contributes less
        # This prevents a few dozen low-severity findings from dominating
        n = len(findings)
        if n > 5:
            dim_factor = 1.0 / (1.0 + math.log(n / 5.0))
            total_score *= dim_factor

        # Clamp to 0-100
        total_score = clamp(total_score, 0.0, 100.0)

        # Determine risk level
        risk_level = "LOW"
        for threshold, level in self.RISK_THRESHOLDS:
            if total_score >= threshold:
                risk_level = level
                break

        # Sort issues by contribution and take top 5
        all_issues.sort(key=lambda x: x[0], reverse=True)
        top_issues = [issue for _, issue in all_issues[:5]]

        return ScoreBreakdown(
            overall=total_score,
            risk_level=risk_level,
            total_findings=len(findings),
            by_category=dict(by_category),
            by_severity=dict(by_severity),
            top_issues=top_issues,
        )

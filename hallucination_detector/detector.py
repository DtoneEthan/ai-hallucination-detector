"""
Main Detector
=============
Orchestrates all detection strategies and produces a unified AnalysisResult.

Usage:
    from hallucination_detector import HallucinationDetector

    detector = HallucinationDetector(verify_online=True)
    result = detector.analyze(text)

    print(result.terminal_report())
    # or result.json_report(), result.markdown_report()
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict

from .utils import Finding
from .claim_extractor import ClaimExtractor, Claim
from .url_verifier import URLVerifier
from .pattern_analyzer import PatternAnalyzer
from .fact_checker import FactChecker
from .scorer import ConfidenceScorer, ScoreBreakdown
from .reporter import Reporter


@dataclass
class AnalysisResult:
    """Complete analysis result containing all findings and metadata."""
    text: str
    findings: List[Finding] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    score: Optional[ScoreBreakdown] = None
    strategies_used: List[str] = field(default_factory=list)

    def terminal_report(self, use_color: bool = True) -> str:
        """Generate a terminal-friendly colored report."""
        reporter = Reporter(use_color=use_color)
        return reporter.terminal_report(self.text, self.findings, self.score, self.claims)

    def json_report(self) -> str:
        """Generate a JSON report."""
        reporter = Reporter(use_color=False)
        return reporter.json_report(self.text, self.findings, self.score, self.claims)

    def markdown_report(self) -> str:
        """Generate a Markdown report."""
        reporter = Reporter(use_color=False)
        return reporter.markdown_report(self.text, self.findings, self.score, self.claims)

    def summary(self) -> str:
        """Return a brief one-line summary."""
        if not self.score:
            return "Analysis not completed."
        return (f"Hallucination Risk: {self.score.overall:.1f}/100 "
                f"({self.score.risk_level}) — {self.score.total_findings} findings")

    def to_dict(self) -> dict:
        """Return a dictionary representation of the result."""
        return {
            "score": self.score.to_dict() if self.score else None,
            "strategies_used": self.strategies_used,
            "findings_count": len(self.findings),
            "claims_count": len(self.claims),
        }


class HallucinationDetector:
    """
    Main detector class that coordinates all analysis strategies.

    Args:
        verify_online: Whether to perform web-based verification (URL checking, fact checking)
        url_timeout: Timeout for URL verification requests (seconds)
        max_claims_to_verify: Maximum number of claims to verify via web search
        enable_strategies: Optional list of strategy names to enable (default: all)
    """

    ALL_STRATEGIES = ["claim_extraction", "pattern_analysis", "url_verification", "fact_checking"]

    def __init__(
        self,
        verify_online: bool = True,
        url_timeout: float = 10.0,
        max_claims_to_verify: int = 10,
        enable_strategies: Optional[List[str]] = None,
    ):
        self.verify_online = verify_online

        # Select strategies
        if enable_strategies is None:
            enable_strategies = self.ALL_STRATEGIES
        self.enabled_strategies = enable_strategies

        # Initialize strategy modules
        self.claim_extractor = ClaimExtractor()
        self.pattern_analyzer = PatternAnalyzer()
        self.url_verifier = URLVerifier(timeout=url_timeout, verify_online=verify_online)
        self.fact_checker = FactChecker(
            verify_online=verify_online,
            max_claims=max_claims_to_verify,
        )
        self.scorer = ConfidenceScorer()

    def analyze(self, text: str) -> AnalysisResult:
        """
        Analyze text for potential AI hallucinations.

        Args:
            text: The text to analyze (supports English and Chinese)

        Returns:
            AnalysisResult containing all findings, extracted claims, and a risk score
        """
        if not text or not text.strip():
            return AnalysisResult(
                text=text or "",
                findings=[],
                claims=[],
                score=self.scorer.score([]),
                strategies_used=[],
            )

        all_findings: List[Finding] = []
        claims: List[Claim] = []
        strategies_used: List[str] = []

        # Strategy 1: Extract claims (always enabled — other strategies depend on it)
        if "claim_extraction" in self.enabled_strategies:
            claims = self.claim_extractor.extract(text)
            strategies_used.append("claim_extraction")

        # Strategy 2: Pattern analysis (always works, even offline)
        if "pattern_analysis" in self.enabled_strategies:
            pattern_findings = self.pattern_analyzer.analyze(text)
            all_findings.extend(pattern_findings)
            strategies_used.append("pattern_analysis")

        # Strategy 3: URL/citation verification
        if "url_verification" in self.enabled_strategies:
            url_findings = self.url_verifier.verify(text)
            all_findings.extend(url_findings)
            strategies_used.append("url_verification")

        # Strategy 4: Web-based fact checking
        if "fact_checking" in self.enabled_strategies:
            fact_findings = self.fact_checker.verify_claims(claims)
            all_findings.extend(fact_findings)
            strategies_used.append("fact_checking")

        # Deduplicate findings (same category + snippet)
        all_findings = self._deduplicate(all_findings)

        # Calculate overall score
        score = self.scorer.score(all_findings)

        return AnalysisResult(
            text=text,
            findings=all_findings,
            claims=claims,
            score=score,
            strategies_used=strategies_used,
        )

    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """Remove duplicate findings (same category + similar snippet)."""
        seen = set()
        unique = []
        for f in findings:
            key = (f.category, f.snippet[:50])
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def analyze_file(self, file_path: str, encoding: str = "utf-8") -> AnalysisResult:
        """Analyze text from a file."""
        with open(file_path, "r", encoding=encoding) as f:
            text = f.read()
        return self.analyze(text)

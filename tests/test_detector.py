"""
Unit tests for the AI Hallucination Detector.
Run with: pytest tests/
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hallucination_detector import HallucinationDetector, AnalysisResult
from hallucination_detector.claim_extractor import ClaimExtractor, Claim
from hallucination_detector.pattern_analyzer import PatternAnalyzer
from hallucination_detector.url_verifier import URLVerifier
from hallucination_detector.scorer import ConfidenceScorer
from hallucination_detector.utils import (
    split_sentences, extract_urls, extract_numbers, extract_dates,
    Severity, Finding, text_similarity
)


class TestUtilities:
    """Test utility functions."""

    def test_split_sentences_english(self):
        text = "First sentence. Second sentence! Third sentence?"
        result = split_sentences(text)
        assert len(result) == 3

    def test_split_sentences_chinese(self):
        text = "第一句话。第二句话！第三句话？"
        result = split_sentences(text)
        assert len(result) >= 2

    def test_split_sentences_empty(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_extract_urls(self):
        text = "Visit https://example.com and http://test.org/path"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://example.com" in urls[0]

    def test_extract_numbers(self):
        text = "There were 1,234 people and 56.7% agreed. The cost was $2.5 million."
        numbers = extract_numbers(text)
        assert len(numbers) >= 3

    def test_extract_dates(self):
        text = "In 1999 and also in 2024, something happened."
        dates = extract_dates(text)
        assert "1999" in dates
        assert "2024" in dates

    def test_text_similarity(self):
        assert text_similarity("hello world", "hello world") == 1.0
        assert text_similarity("", "test") == 0.0
        sim = text_similarity("the quick brown fox", "the quick red fox")
        assert 0.0 < sim < 1.0


class TestClaimExtractor:
    """Test claim extraction."""

    def test_extract_numerical_claims(self):
        extractor = ClaimExtractor()
        text = "The study found that 87.3% of users prefer dark mode. The company has 1,500 employees."
        claims = extractor.extract(text)
        assert len(claims) >= 1
        assert any(c.claim_type == "numerical" for c in claims)

    def test_extract_citation_claims(self):
        extractor = ClaimExtractor()
        text = "According to Smith et al., the results were significant."
        claims = extractor.extract(text)
        assert len(claims) >= 1
        assert any(c.claim_type == "citation" for c in claims)

    def test_extract_historical_claims(self):
        extractor = ClaimExtractor()
        text = "The company was founded in 2015 and launched its product in 2020."
        claims = extractor.extract(text)
        assert len(claims) >= 1

    def test_risk_indicators_hedging(self):
        extractor = ClaimExtractor()
        text = "It is reportedly true that the system processes 5 million requests per day."
        claims = extractor.extract(text)
        assert any("hedging" in ri.lower() for c in claims for ri in c.risk_indicators)

    def test_empty_text(self):
        extractor = ClaimExtractor()
        assert extractor.extract("") == []
        assert extractor.extract("Hello.") == []


class TestPatternAnalyzer:
    """Test pattern analysis."""

    def test_hyper_specific_numbers(self):
        analyzer = PatternAnalyzer()
        text = "The system has exactly 1,247,832 active users worldwide."
        findings = analyzer.analyze(text)
        assert any(f.category == "hyper_specific_number" for f in findings)

    def test_excessive_hedging(self):
        analyzer = PatternAnalyzer()
        text = ("It is reportedly true that the system works. "
                "Some sources allegedly claim it is reliable. "
                "It is believed that many think it is effective. "
                "Purportedly, the results are good.")
        findings = analyzer.analyze(text)
        assert any(f.category == "excessive_hedging" for f in findings)

    def test_excessive_overconfidence(self):
        analyzer = PatternAnalyzer()
        text = ("This is undoubtedly true. "
                "It is well known that this works. "
                "Clearly, the results are perfect. "
                "Without question, this is the best approach.")
        findings = analyzer.analyze(text)
        assert any(f.category == "excessive_overconfidence" for f in findings)

    def test_flavor_text(self):
        analyzer = PatternAnalyzer()
        text = ("In today's rapidly evolving world, AI is important. "
                "It is important to note that things change. "
                "It's worth mentioning that technology matters. "
                "As we all know, innovation plays a crucial role. "
                "At the end of the day, it's all about progress.")
        findings = analyzer.analyze(text)
        assert any(f.category == "excessive_flavor_text" for f in findings)

    def test_internal_contradiction(self):
        analyzer = PatternAnalyzer()
        text = ("The market was valued at 1.5 billion dollars in 2023. "
                "The market was valued at 2.3 billion dollars in 2023.")
        findings = analyzer.analyze(text)
        # Should detect some contradiction or suspicious pattern
        assert len(findings) > 0

    def test_clean_text_no_findings(self):
        analyzer = PatternAnalyzer()
        text = "The sky is blue. Water is wet."
        findings = analyzer.analyze(text)
        # Clean factual text should have minimal findings
        assert len(findings) == 0 or all(f.severity == Severity.LOW for f in findings)


class TestURLVerifier:
    """Test URL verification."""

    def test_suspicious_url_pattern(self):
        verifier = URLVerifier(verify_online=False)
        text = "Visit https://www.research-paper.com/study"
        findings = verifier.verify(text)
        assert any(f.category == "fake_url_domain" for f in findings)

    def test_fake_tld(self):
        verifier = URLVerifier(verify_online=False)
        text = "Check https://example.fake/source"
        findings = verifier.verify(text)
        assert len(findings) > 0

    def test_normal_url_no_issue(self):
        verifier = URLVerifier(verify_online=False)
        text = "Visit https://www.python.org for documentation."
        findings = verifier.verify(text)
        # Should not flag a legitimate domain (offline mode)
        assert not any(f.severity == Severity.CRITICAL for f in findings)

    def test_doi_extraction(self):
        verifier = URLVerifier(verify_online=False)
        text = "See the paper with DOI 10.1000/test123 for details."
        dois = verifier._extract_dois(text)
        assert len(dois) == 1
        assert "10.1000/test123" in dois[0]


class TestScorer:
    """Test the confidence scorer."""

    def test_empty_findings(self):
        scorer = ConfidenceScorer()
        result = scorer.score([])
        assert result.overall == 0.0
        assert result.risk_level == "LOW"
        assert result.total_findings == 0

    def test_single_critical(self):
        scorer = ConfidenceScorer()
        findings = [Finding(
            severity=Severity.CRITICAL,
            category="fake_url_domain",
            message="Fake URL detected",
            confidence=0.9,
        )]
        result = scorer.score(findings)
        assert result.risk_level in ("HIGH", "CRITICAL")
        assert result.overall > 25

    def test_multiple_low_severity(self):
        scorer = ConfidenceScorer()
        findings = [
            Finding(severity=Severity.LOW, category="flavor_text", message=f"Issue {i}", confidence=0.2)
            for i in range(10)
        ]
        result = scorer.score(findings)
        # Many low-severity findings shouldn't produce a critical score
        assert result.overall < 70

    def test_category_weights(self):
        """fake_url_domain should weight more than repetitive_phrasing."""
        scorer = ConfidenceScorer()
        critical_finding = [Finding(
            severity=Severity.CRITICAL, category="fake_url_domain",
            message="Test", confidence=1.0
        )]
        low_finding = [Finding(
            severity=Severity.LOW, category="repetitive_phrasing",
            message="Test", confidence=1.0
        )]
        score_critical = scorer.score(critical_finding)
        score_low = scorer.score(low_finding)
        assert score_critical.overall > score_low.overall


class TestDetector:
    """Test the main detector integration."""

    def test_analyze_empty_text(self):
        detector = HallucinationDetector(verify_online=False)
        result = detector.analyze("")
        assert result.score.risk_level == "LOW"
        assert len(result.findings) == 0

    def test_analyze_hallucinated_text(self):
        detector = HallucinationDetector(verify_online=False)
        text = (
            "According to a 2024 study by the Global Research Institute, "
            "87.3% of users prefer AI content. Visit https://www.research-paper.com/study. "
            "The study surveyed 1,247,832 participants."
        )
        result = detector.analyze(text)
        assert len(result.findings) > 0
        assert result.score.overall > 0
        assert len(result.claims) > 0

    def test_analyze_clean_text(self):
        detector = HallucinationDetector(verify_online=False)
        text = "The sky is blue. Water boils at 100 degrees Celsius."
        result = detector.analyze(text)
        # Clean text should have low risk score
        assert result.score.risk_level in ("LOW", "MODERATE")

    def test_result_formats(self):
        detector = HallucinationDetector(verify_online=False)
        result = detector.analyze("Test text with some claims about 42% of things.")
        # All report formats should produce non-empty output
        assert len(result.terminal_report(use_color=False)) > 0
        assert len(result.json_report()) > 0
        assert len(result.markdown_report()) > 0
        assert len(result.summary()) > 0

    def test_json_report_valid(self):
        import json
        detector = HallucinationDetector(verify_online=False)
        result = detector.analyze("Some test text with 99% reliability claims.")
        json_str = result.json_report()
        parsed = json.loads(json_str)
        assert "summary" in parsed
        assert "findings" in parsed
        assert "claims" in parsed

    def test_strategy_selection(self):
        detector = HallucinationDetector(
            verify_online=False,
            enable_strategies=["pattern_analysis"]
        )
        result = detector.analyze("Some text with https://example.com URLs and 42% stats.")
        assert "pattern_analysis" in result.strategies_used
        assert "url_verification" not in result.strategies_used

    def test_analyze_file(self):
        detector = HallucinationDetector(verify_online=False)
        # Use the sample file
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "sample_ai_text.txt"
        )
        result = detector.analyze_file(sample_path)
        assert len(result.findings) > 0
        assert result.score.overall > 10  # should detect issues


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

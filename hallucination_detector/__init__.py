"""
AI Hallucination Detector
=========================
A multi-strategy toolkit for detecting potential AI hallucinations in text.

Strategies:
    - Claim extraction & verifiability scoring
    - URL / citation verification
    - Hallucination pattern analysis
    - Web-based fact checking (optional)
    - Aggregate confidence scoring

Usage:
    from hallucination_detector import HallucinationDetector

    detector = HallucinationDetector()
    result = detector.analyze("Your AI-generated text here...")
    print(result.summary())
"""

from .detector import HallucinationDetector, AnalysisResult
from .claim_extractor import ClaimExtractor
from .url_verifier import URLVerifier
from .pattern_analyzer import PatternAnalyzer
from .fact_checker import FactChecker
from .scorer import ConfidenceScorer
from .reporter import Reporter
from .plagiarism_checker import PlagiarismChecker
from .web_search import WebSearcher

__version__ = "1.0.0"
__author__ = "Ethan Xu"
__license__ = "MIT"

__all__ = [
    "HallucinationDetector",
    "AnalysisResult",
    "ClaimExtractor",
    "URLVerifier",
    "PatternAnalyzer",
    "FactChecker",
    "ConfidenceScorer",
    "Reporter",
    "PlagiarismChecker",
    "WebSearcher",
]

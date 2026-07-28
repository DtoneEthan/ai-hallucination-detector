"""
Claim Extractor
==============
Extracts verifiable factual claims from text and scores their verifiability.

A "claim" is a sentence or clause that makes a factual assertion that could
in principle be checked: statistics, dates, attributions, cause-effect statements,
existence claims, etc.
"""

import re
from dataclasses import dataclass, field
from typing import List
from .utils import split_sentences, extract_numbers, extract_dates, extract_quotes


@dataclass
class Claim:
    """A single extracted factual claim."""
    text: str                           # the full claim sentence
    claim_type: str                     # numerical, citation, historical, biographical, technical, causal, other
    verifiability: float = 0.0          # 0.0-1.0, how easy it is to verify
    evidence: List[str] = field(default_factory=list)  # numbers, dates, quotes found in the claim
    risk_indicators: List[str] = field(default_factory=list)  # specific things that look suspicious

    def __str__(self):
        return f"[{self.claim_type}] (verifiability={self.verifiability:.2f}) {self.text[:100]}..."


class ClaimExtractor:
    """Extracts and categorizes factual claims from text."""

    # Patterns that indicate factual claims
    NUMERICAL_PATTERNS = [
        (r'\d[\d,]*\.\d+\s*%', "percentage"),
        (r'\$[\d,.]+\s?(?:million|billion|trillion)', "money"),
        (r'￥[\d,.]+\s?(?:万|亿)', "money_cn"),
        (r'\d[\d,]*\s?(?:million|billion|trillion|thousand)', "large_number"),
        (r'\d[\d,]*\s?(?:万|亿|百万|千万)', "large_number_cn"),
        (r'\d+(?:\.\d+)?\s?(?:percent|per cent|%)', "percentage"),
    ]

    # Patterns that indicate citations or references
    CITATION_PATTERNS = [
        r'according to\s+[^,.]+',
        r'stated by\s+[^,.]+',
        r'reported (?:by|in)\s+[^,.]+',
        r'published in\s+[^,.]+',
        r'研究(?:表明|发现|显示)',
        r'根据[^，。]+',
        r'据(?:报道|统计|调查)',
        r'(?:Smith|Johnson|Brown|Wilson|Taylor|Lee|Wang|Zhang|Li|Liu|Chen)\s+et\s+al\.?',
        r'et al\.?',
        r'\(?\d{4}\)?\s*(?:,)?\s*p\.?\s*\d+',  # APA-style page refs
    ]

    # Patterns that indicate historical/biographical claims
    HISTORICAL_PATTERNS = [
        r'(?:in|during|since|before|after)\s+(?:1[5-9]\d{2}|20\d{2})',
        r'(?:born|died|founded|established|created|invented)\s+(?:in\s+)?(?:1[5-9]\d{2}|20\d{2})',
        r'\d{4}年',
        r'(?:春秋|战国|秦|汉|唐|宋|元|明|清)(?:时期|年间|代)',
    ]

    # Patterns that indicate causal claims
    CAUSAL_PATTERNS = [
        r'\b(?:causes?|leads? to|results? in|due to|because of|effect of|impact of)\b',
        r'(?:导致|引起|使得|由于|因为|影响|作用)',
    ]

    # Patterns indicating technical/API claims
    TECHNICAL_PATTERNS = [
        r'\b(?:API|function|method|class|module|library|package|framework|SDK)\b',
        r'\b(?:endpoint|parameter|argument|return value|callback)\b',
        r'[a-zA-Z_][a-zA-Z0-9_]*\(\)',       # function call syntax
        r'[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*',  # dot notation
    ]

    # Hedging language — common in hallucinations when the model is unsure
    HEDGE_WORDS = {
        "reportedly", "allegedly", "supposedly", "purportedly",
        "it is said", "it is believed", "it is thought",
        "some sources", "many believe", "reportedly",
        "据说", "据称", "有人认为", "有传言称", "据信",
    }

    # Overly confident language — also a hallucination red flag
    ABSOLUTE_WORDS = {
        "definitely", "certainly", "undoubtedly", "without question",
        "it is well known", "it is widely recognized",
        "always", "never", "all", "none",
        "毫无疑问", "众所周知", "确实", "绝对",
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self._numerical = [(re.compile(p, re.IGNORECASE), label) for p, label in self.NUMERICAL_PATTERNS]
        self._citation = [re.compile(p, re.IGNORECASE) for p in self.CITATION_PATTERNS]
        self._historical = [re.compile(p, re.IGNORECASE) for p in self.HISTORICAL_PATTERNS]
        self._causal = [re.compile(p, re.IGNORECASE) for p in self.CAUSAL_PATTERNS]
        self._technical = [re.compile(p, re.IGNORECASE) for p in self.TECHNICAL_PATTERNS]

    def extract(self, text: str) -> List[Claim]:
        """
        Extract all factual claims from the input text.
        Returns a list of Claim objects sorted by verifiability (descending).
        """
        sentences = split_sentences(text)
        claims = []

        for idx, sentence in enumerate(sentences):
            if len(sentence.strip()) < 15:
                continue

            claim_type, verifiability, evidence, risk_indicators = self._analyze_sentence(sentence, idx)
            if claim_type:
                claims.append(Claim(
                    text=sentence.strip(),
                    claim_type=claim_type,
                    verifiability=verifiability,
                    evidence=evidence,
                    risk_indicators=risk_indicators,
                ))

        # Sort by verifiability (most verifiable first — highest priority for checking)
        claims.sort(key=lambda c: c.verifiability, reverse=True)
        return claims

    def _analyze_sentence(self, sentence: str, idx: int) -> tuple:
        """Analyze a single sentence and return (type, verifiability, evidence, risk_indicators)."""
        evidence = []
        risk_indicators = []
        claim_type = None
        verifiability = 0.0

        # Check numerical claims
        numbers = extract_numbers(sentence)
        if numbers:
            evidence.extend(numbers)
            claim_type = "numerical"
            verifiability = 0.8  # numbers are fairly verifiable
            for n in numbers:
                # Very specific large numbers are harder to verify
                digits = re.sub(r'[^0-9]', '', n)
                if len(digits) > 6:
                    risk_indicators.append(f"Highly specific number: {n}")
                    verifiability = max(verifiability - 0.1, 0.3)

        # Check citation claims
        for pattern in self._citation:
            if pattern.search(sentence):
                claim_type = claim_type or "citation"
                match = pattern.search(sentence)
                evidence.append(match.group())
                verifiability = max(verifiability, 0.7)
                break

        # Check historical claims
        dates = extract_dates(sentence)
        if dates:
            evidence.extend(dates)
            if claim_type is None:
                claim_type = "historical"
            verifiability = max(verifiability, 0.6)

        # Check causal claims
        for pattern in self._causal:
            if pattern.search(sentence):
                if claim_type is None:
                    claim_type = "causal"
                verifiability = max(verifiability, 0.4)  # causal claims are harder to verify
                break

        # Check technical claims
        for pattern in self._technical:
            if pattern.search(sentence):
                if claim_type is None:
                    claim_type = "technical"
                evidence.append(pattern.search(sentence).group())
                verifiability = max(verifiability, 0.5)
                break

        # Check for quotes
        quotes = extract_quotes(sentence)
        if quotes:
            evidence.extend(quotes)
            risk_indicators.append("Contains quoted text — verify source")
            verifiability = max(verifiability, 0.6)

        # Check for hedge words — red flag for hallucination
        words_lower = sentence.lower()
        for hedge in self.HEDGE_WORDS:
            if hedge in words_lower:
                risk_indicators.append(f"Hedging language: '{hedge}'")
                verifiability -= 0.15

        # Check for absolute language — also a red flag
        for absolute in self.ABSOLUTE_WORDS:
            if absolute in words_lower:
                risk_indicators.append(f"Absolute language: '{absolute}'")
                verifiability -= 0.1

        # If no specific type was found, check if it's a general factual statement
        if claim_type is None:
            # Heuristic: if the sentence makes an assertion with a proper noun, it's a claim
            if re.search(r'\b[A-Z][a-z]+', sentence) or re.search(r'[\u4e00-\u9fff]{2,}(?:是|有|为|可以|能够)', sentence):
                claim_type = "other"
                verifiability = 0.3

        verifiability = max(0.0, min(1.0, verifiability))

        return claim_type, verifiability, evidence, risk_indicators

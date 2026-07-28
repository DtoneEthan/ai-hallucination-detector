"""
Utility functions shared across the hallucination detector modules.
"""

import re
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class Severity(Enum):
    """Severity level of a detected issue."""
    INFO = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

    def __str__(self):
        names = {
            "INFO": "\033[36mINFO\033[0m",
            "LOW": "\033[32mLOW\033[0m",
            "MEDIUM": "\033[33mMEDIUM\033[0m",
            "HIGH": "\033[35mHIGH\033[0m",
            "CRITICAL": "\033[31mCRITICAL\033[0m",
        }
        if self.name in names:
            return names[self.name]
        return self.name

    def to_plain(self) -> str:
        return self.name


@dataclass
class Finding:
    """A single issue found during analysis."""
    severity: Severity
    category: str           # e.g. "url_broken", "fake_citation", "unverifiable_stat"
    message: str            # human-readable description
    snippet: str = ""       # the offending text snippet
    location: str = ""      # location info (e.g. "sentence 3", "line 5")
    suggestion: str = ""    # optional fix suggestion
    confidence: float = 0.0  # 0.0-1.0 how confident we are this is a real issue

    def __str__(self):
        parts = [f"[{self.severity.to_plain()}] {self.category}: {self.message}"]
        if self.snippet:
            parts.append(f'    Snippet: "{self.snippet[:120]}{"..." if len(self.snippet) > 120 else ""}"')
        if self.location:
            parts.append(f"    Location: {self.location}")
        if self.suggestion:
            parts.append(f"    Suggestion: {self.suggestion}")
        return "\n".join(parts)


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences. Supports both English and Chinese.

    English: split on . ! ? (followed by space or end)
    Chinese: split on 。！？；
    """
    # Normalize whitespace
    text = text.strip()
    if not text:
        return []

    # Combined pattern: English sentence endings + Chinese sentence endings
    # For English: split on . ! ? followed by whitespace
    # For Chinese: split on 。！？ even without trailing whitespace (Chinese doesn't use spaces)
    pattern = r'(?<=[.!?])\s+|(?<=[.!?])$|(?<=[。！？；])'
    raw_parts = re.split(pattern, text)

    # Also handle newlines as sentence boundaries
    sentences = []
    for part in raw_parts:
        # Further split on double newlines (paragraph breaks)
        sub_parts = re.split(r'\n{2,}', part)
        for sp in sub_parts:
            sp = sp.strip()
            if sp:
                # Also split on single newlines if they look like sentence boundaries
                lines = sp.split('\n')
                current = ""
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if current:
                        # Check if current ends with a sentence delimiter
                        if re.search(r'[.!?。！？；]$', current):
                            sentences.append(current)
                            current = line
                        else:
                            current += " " + line
                    else:
                        current = line
                if current:
                    sentences.append(current)

    return sentences if sentences else [text]


def extract_urls(text: str) -> List[str]:
    """Extract all URLs from text."""
    url_pattern = r'https?://[^\s<>"\')\]]+(?:[^\s<>"\')\].,;:!?])'
    return re.findall(url_pattern, text)


def extract_numbers(text: str) -> List[str]:
    """Extract numbers/statistics from text (including percentages, large numbers with commas)."""
    # Match numbers with optional commas, decimals, percentages, and units
    pattern = r'(?:[$￥€£]\s?)?\d[\d,]*(?:\.\d+)?(?:%|\s?(?:million|billion|trillion|thousand|万|亿|百万|千万))?'
    return re.findall(pattern, text)


def extract_dates(text: str) -> List[str]:
    """Extract date references from text."""
    patterns = [
        r'\b(?:19|20)\d{2}\b',                          # 1999, 2024
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,)?\s*(?:19|20)?\d{2}?\b',
        r'\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b',          # 01/15/2024
        r'\b\d{4}年\d{1,2}月\d{1,2}日\b',                  # 2024年1月15日
    ]
    results = []
    for p in patterns:
        results.extend(re.findall(p, text))
    return results


def extract_quotes(text: str) -> List[str]:
    """Extract quoted text (both English and Chinese quotes)."""
    quotes = []
    # English double quotes
    quotes.extend(re.findall(r'"([^"]{5,})"', text))
    # English single quotes (avoid contractions)
    quotes.extend(re.findall(r"(?<!\w)'([^']{5,})'", text))
    # Chinese quotes
    quotes.extend(re.findall(r'\u201c([^\u201d]{5,})\u201d', text))
    quotes.extend(re.findall(r'\u300c([^\u300d]{5,})\u300d', text))
    return quotes


def sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp value to [low, high]."""
    return max(low, min(high, value))


def text_similarity(a: str, b: str) -> float:
    """
    Simple text similarity using character n-gram overlap.
    Returns 0.0-1.0.
    """
    if not a or not b:
        return 0.0

    def ngrams(text, n=3):
        text = text.lower().strip()
        return {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}

    grams_a = ngrams(a)
    grams_b = ngrams(b)

    intersection = grams_a & grams_b
    union = grams_a | grams_b

    return len(intersection) / len(union) if union else 0.0

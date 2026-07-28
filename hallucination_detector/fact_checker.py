"""
Fact Checker
============
Uses web search to verify extracted claims against external sources.

This module performs optional web-based verification. It degrades gracefully
when network access is unavailable — pattern-based analysis still works.
"""

import re
from typing import List, Optional
from .utils import Finding, Severity, text_similarity, extract_numbers
from .claim_extractor import Claim


class FactChecker:
    """Verifies claims by searching the web for corroborating or contradicting evidence."""

    # Search query templates — each strategy generates a search query for a claim
    QUERY_TEMPLATES = {
        "numerical": '"{number}" {keywords}',
        "citation": '"{source}" {keywords}',
        "historical": '"{date}" {keywords}',
        "causal": "{keywords}",
        "technical": '"{entity}" {keywords}',
        "other": "{keywords}",
    }

    # Search engines to try (in order)
    SEARCH_ENGINES = [
        {
            "name": "DuckDuckGo",
            "url": "https://html.duckduckgo.com/html/?q={query}",
            "result_selector": ".result__snippet",
        },
        {
            "name": "Google",
            "url": "https://www.google.com/search?q={query}",
            "result_selector": ".BNeawe",
        },
    ]

    def __init__(self, verify_online: bool = True, max_claims: int = 10):
        """
        Args:
            verify_online: If False, skip all web requests (offline mode)
            max_claims: Maximum number of claims to verify online (to avoid rate limits)
        """
        self.verify_online = verify_online
        self.max_claims = max_claims
        self._session = None

    def _get_session(self):
        """Lazily create a requests session."""
        if self._session is not None:
            return self._session
        try:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (AIHallucinationDetector/1.0)',
                'Accept': 'text/html',
            })
        except ImportError:
            self._session = False
        return self._session

    def verify_claims(self, claims: List[Claim]) -> List[Finding]:
        """
        Verify a list of claims against web sources.
        Returns findings for claims that couldn't be corroborated or that appear false.
        """
        findings = []

        if not self.verify_online:
            return self._offline_findings(claims)

        session = self._get_session()
        if session is False:
            return self._offline_findings(claims)

        # Verify the top N most verifiable claims
        claims_to_check = sorted(claims, key=lambda c: c.verifiability, reverse=True)[:self.max_claims]

        for claim in claims_to_check:
            finding = self._verify_single_claim(claim, session)
            if finding:
                findings.append(finding)

        return findings

    def _verify_single_claim(self, claim: Claim, session) -> Optional[Finding]:
        """Verify a single claim against web sources."""
        # Build search query from the claim
        query = self._build_query(claim)
        if not query:
            return None

        # Try each search engine
        for engine in self.SEARCH_ENGINES:
            results = self._search(query, engine, session)
            if results:
                # Analyze search results
                analysis = self._analyze_search_results(claim, results)
                if analysis:
                    return analysis
                break  # if we got results but no finding, stop trying other engines

        return None

    def _build_query(self, claim: Claim) -> str:
        """Build a search query from a claim."""
        # Extract key terms from the claim
        # For numerical claims, use the numbers + surrounding keywords
        if claim.claim_type == "numerical" and claim.evidence:
            numbers = [e for e in claim.evidence if any(c.isdigit() for c in e)]
            if numbers:
                # Use the most significant number + some keywords from the sentence
                keywords = self._extract_keywords(claim.text, exclude=numbers)
                return f'"{numbers[0]}" {keywords[:80]}'

        # For citations, search for the source
        elif claim.claim_type == "citation" and claim.evidence:
            return f'"{claim.evidence[0]}" {self._extract_keywords(claim.text)[:60]}'

        # For historical claims, use the dates
        elif claim.claim_type == "historical" and claim.evidence:
            dates = [e for e in claim.evidence if e.isdigit()]
            if dates:
                keywords = self._extract_keywords(claim.text, exclude=dates)
                return f'"{dates[0]}" {keywords[:80]}'

        # Default: use keywords from the sentence
        keywords = self._extract_keywords(claim.text)
        return keywords[:100] if keywords else ""

    def _extract_keywords(self, text: str, exclude: List[str] = None) -> str:
        """Extract meaningful keywords from text, excluding common words."""
        exclude = set(exclude or [])
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
            'their', 'there', 'here', 'who', 'what', 'when', 'where',
            'why', 'how', 'which', 'and', 'or', 'but', 'not', 'no',
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
            'as', 'about', 'into', 'through', 'during', 'before', 'after',
            '的', '了', '是', '在', '和', '与', '或', '但', '不', '没',
            '这', '那', '些', '个', '中', '上', '下', '为', '有',
        }

        # Extract words, filtering out stopwords and excluded terms
        words = re.findall(r'[a-zA-Z\u4e00-\u9fff]{2,}', text)
        keywords = [w for w in words if w.lower() not in stop_words and w not in exclude]

        return ' '.join(keywords)

    def _search(self, query: str, engine: dict, session) -> List[str]:
        """Perform a web search and return result snippets."""
        try:
            from urllib.parse import quote_plus
            url = engine["url"].format(query=quote_plus(query))
            response = session.get(url, timeout=15)

            if response.status_code != 200:
                return []

            # Parse HTML to extract result snippets
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                snippets = []
                for elem in soup.select(engine["result_selector"]):
                    text = elem.get_text(strip=True)
                    if text:
                        snippets.append(text)
                return snippets[:5]  # top 5 results
            except ImportError:
                # Fallback: regex extraction
                # Look for text between common snippet tags
                snippets = re.findall(r'<span[^>]*>(.{20,200}?)</span>', response.text)
                return [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:5]]

        except Exception:
            return []

    def _analyze_search_results(self, claim: Claim, results: List[str]) -> Optional[Finding]:
        """Analyze search results to determine if the claim is supported."""
        if not results:
            return Finding(
                severity=Severity.MEDIUM,
                category="unverifiable_claim",
                message=f"No search results found for claim — may be fabricated",
                snippet=claim.text[:120],
                location=f"claim type: {claim.claim_type}",
                suggestion=f"Search manually for: \"{self._extract_keywords(claim.text)[:60]}\"",
                confidence=0.5,
            )

        # For numerical claims, check if the exact number appears in results
        if claim.claim_type == "numerical":
            numbers = [e for e in claim.evidence if any(c.isdigit() for c in e)]
            for num in numbers:
                clean_num = re.sub(r'[^0-9]', '', num)
                if len(clean_num) >= 4:  # only check significant numbers
                    found_exact = False
                    found_approx = False
                    for result in results:
                        if clean_num in re.sub(r'[^0-9]', '', result):
                            found_exact = True
                            break
                        # Check if a similar number (within 10%) appears
                        result_nums = re.findall(r'\d{3,}', result)
                        for rn in result_nums:
                            rn_val = int(rn.replace(',', ''))
                            try:
                                if abs(rn_val - int(clean_num)) / max(int(clean_num), 1) < 0.1:
                                    found_approx = True
                            except (ValueError, ZeroDivisionError):
                                continue

                    if not found_exact and not found_approx:
                        return Finding(
                            severity=Severity.HIGH,
                            category="number_not_found",
                            message=f"Specific number '{num}' not found in any search result — likely fabricated",
                            snippet=claim.text[:120],
                            location=f"claim type: numerical",
                            suggestion=f"Verify this number: search for '{num}' with context",
                            confidence=0.65,
                        )

        # For citation claims, check if the cited source appears in results
        elif claim.claim_type == "citation":
            if claim.evidence:
                source = claim.evidence[0].lower()
                found = any(source in result.lower() for result in results)
                if not found:
                    return Finding(
                        severity=Severity.HIGH,
                        category="source_not_found",
                        message=f"Cited source '{claim.evidence[0]}' not found in search results",
                        snippet=claim.text[:120],
                        location=f"claim type: citation",
                        suggestion="Verify this source exists and was quoted correctly",
                        confidence=0.6,
                    )

        return None

    def _offline_findings(self, claims: List[Claim]) -> List[Finding]:
        """Generate findings based on offline heuristics when web verification is unavailable."""
        findings = []
        for claim in claims[:self.max_claims]:
            if claim.risk_indicators:
                findings.append(Finding(
                    severity=Severity.LOW,
                    category="offline_risk_indicators",
                    message=f"Risk indicators found (offline analysis): {'; '.join(claim.risk_indicators[:3])}",
                    snippet=claim.text[:120],
                    location=f"claim type: {claim.claim_type}, verifiability: {claim.verifiability:.0%}",
                    suggestion="Run with --online flag to verify claims against web sources",
                    confidence=0.3,
                ))
        return findings

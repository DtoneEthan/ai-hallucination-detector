"""
URL & Citation Verifier
======================
Verifies URLs, DOIs, and reference patterns found in text.

Checks:
    - URL reachability (HTTP status)
    - Suspicious URL patterns (fake domains, typosquatting)
    - DOI resolution
    - Broken/redirected links
"""

import re
import socket
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from .utils import Finding, Severity, extract_urls


class URLVerifier:
    """Verifies URLs and citations found in text."""

    # Known legitimate TLDs (subset — doesn't need to be exhaustive)
    VALID_TLDS = {
        '.com', '.org', '.net', '.edu', '.gov', '.io', '.ai', '.co',
        '.dev', '.app', '.info', '.biz', '.me', '.xyz', '.tech',
        # Common country code TLDs
        '.cn', '.jp', '.kr', '.uk', '.de', '.fr', '.au', '.ca',
        '.ch', '.nl', '.se', '.no', '.fi', '.dk', '.be', '.at',
        '.es', '.it', '.pt', '.br', '.mx', '.ar', '.in', '.id',
        '.ru', '.ua', '.pl', '.cz', '.hu', '.ro', '.gr', '.ie',
        '.nz', '.za', '.sg', '.hk', '.tw', '.th', '.my', '.ph',
        '.vn', '.tr', '.il', '.ae', '.sa', '.eg', '.ng', '.ke',
    }

    # Suspicious domain patterns often seen in hallucinated URLs
    SUSPICIOUS_PATTERNS = [
        (re.compile(r'\.(fake|test|example|invalid|localhost)\b', re.I), "Known fake/test TLD"),
        (re.compile(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'), "IP address as URL"),
        (re.compile(r'(.)\1{4,}'), "Suspicious repeated characters in domain"),
    ]

    # Common hallucinated domain patterns
    HALLUCINATED_DOMAIN_HINTS = [
        "research-paper", "academic-source", "study-findings",
        "official-source", "verified-data", "credible-source",
    ]

    def __init__(self, timeout: float = 10.0, verify_online: bool = True):
        """
        Args:
            timeout: HTTP request timeout in seconds
            verify_online: If False, skip all HTTP requests (offline mode)
        """
        self.timeout = timeout
        self.verify_online = verify_online
        self._session = None

    def _get_session(self):
        """Lazily create a requests session."""
        if self._session is not None:
            return self._session
        try:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'AIHallucinationDetector/1.0 (https://github.com/ethanxu/ai-hallucination-detector)'
            })
        except ImportError:
            self._session = False  # mark as unavailable
        return self._session

    def verify(self, text: str) -> List[Finding]:
        """
        Find and verify all URLs and citations in the text.
        Returns a list of Findings for any issues detected.
        """
        findings = []
        urls = extract_urls(text)

        for url in urls:
            # Check for suspicious patterns first (always done, even offline)
            finding = self._check_suspicious(url)
            if finding:
                findings.append(finding)
                continue  # don't bother HTTP-checking suspicious URLs

            # Online verification
            if self.verify_online:
                finding = self._check_reachability(url)
                if finding:
                    findings.append(finding)

        # Check for DOI references
        dois = self._extract_dois(text)
        for doi in dois:
            if self.verify_online:
                finding = self._check_doi(doi)
                if finding:
                    findings.append(finding)

        # Check for reference patterns that look fabricated
        findings.extend(self._check_fake_references(text))

        return findings

    def _check_suspicious(self, url: str) -> Optional[Finding]:
        """Check for suspicious URL patterns."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check for known fake TLDs
        for pattern, reason in self.SUSPICIOUS_PATTERNS:
            if pattern.search(domain):
                return Finding(
                    severity=Severity.HIGH,
                    category="suspicious_url",
                    message=f"URL has suspicious pattern: {reason}",
                    snippet=url,
                    location=f"domain: {domain}",
                    suggestion="Verify this URL manually — it may be fabricated",
                    confidence=0.85,
                )

        # Check for hallucinated domain hints
        for hint in self.HALLUCINATED_DOMAIN_HINTS:
            if hint in domain:
                return Finding(
                    severity=Severity.CRITICAL,
                    category="fake_url_domain",
                    message=f"URL domain contains hallucinated pattern: '{hint}'",
                    snippet=url,
                    location=f"domain: {domain}",
                    suggestion="This URL is very likely fabricated by an AI model",
                    confidence=0.95,
                )

        # Check for valid TLD
        has_valid_tld = any(domain.endswith(tld) or f'.{tld.strip(".")}' in f'.{domain.split(".")[-0+1]}' for tld in self.VALID_TLDS)
        # Simpler check
        tld = '.' + domain.split('.')[-1] if '.' in domain else ''
        if tld and tld not in self.VALID_TLDS and not any(domain.endswith(t) for t in self.VALID_TLDS):
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):  # skip IP check here
                return Finding(
                    severity=Severity.MEDIUM,
                    category="unknown_tld",
                    message=f"URL has an unrecognized TLD: {tld}",
                    snippet=url,
                    location=f"domain: {domain}",
                    suggestion="Verify this domain exists",
                    confidence=0.5,
                )

        return None

    def _check_reachability(self, url: str) -> Optional[Finding]:
        """Check if a URL is actually reachable via HTTP."""
        session = self._get_session()
        if session is False:
            return Finding(
                severity=Severity.INFO,
                category="verification_skipped",
                message="Online verification skipped (requests library not installed)",
                snippet=url,
                suggestion="Install requests: pip install requests",
                confidence=0.0,
            )

        try:
            response = session.head(url, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 404:
                return Finding(
                    severity=Severity.CRITICAL,
                    category="url_404",
                    message=f"URL returns 404 Not Found — link is broken or page doesn't exist",
                    snippet=url,
                    suggestion="This URL likely doesn't exist — possible hallucination",
                    confidence=0.9,
                )
            elif response.status_code >= 400:
                return Finding(
                    severity=Severity.HIGH,
                    category="url_error",
                    message=f"URL returns HTTP {response.status_code}",
                    snippet=url,
                    suggestion="URL may be broken or access is restricted",
                    confidence=0.7,
                )
        except socket.timeout:
            return Finding(
                severity=Severity.MEDIUM,
                category="url_timeout",
                message="URL request timed out — domain may not resolve",
                snippet=url,
                suggestion="Check if this domain actually exists",
                confidence=0.5,
            )
        except ConnectionError as e:
            # Could be DNS failure or connection refused
            error_str = str(e).lower()
            if 'name or service not known' in error_str or 'getaddrinfo' in error_str or 'nodename' in error_str or 'no address' in error_str:
                return Finding(
                    severity=Severity.CRITICAL,
                    category="url_dns_failure",
                    message="URL domain does not resolve (DNS failure) — domain likely does not exist",
                    snippet=url,
                    suggestion="This URL is very likely fabricated",
                    confidence=0.92,
                )
            return Finding(
                severity=Severity.MEDIUM,
                category="url_connection_error",
                message=f"Could not connect to URL: {str(e)[:100]}",
                snippet=url,
                suggestion="Verify URL manually",
                confidence=0.4,
            )
        except Exception as e:
            return Finding(
                severity=Severity.LOW,
                category="url_check_failed",
                message=f"URL verification failed: {type(e).__name__}",
                snippet=url,
                suggestion="Verify URL manually",
                confidence=0.2,
            )

        return None

    def _extract_dois(self, text: str) -> List[str]:
        """Extract DOI references from text."""
        doi_pattern = r'\b10\.\d{4,}/[^\s<>"\')\]]+'
        return list(set(re.findall(doi_pattern, text)))

    def _check_doi(self, doi: str) -> Optional[Finding]:
        """Check if a DOI resolves via the DOI resolver."""
        session = self._get_session()
        if session is False:
            return None

        url = f"https://doi.org/{doi}"
        try:
            response = session.head(url, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 404:
                return Finding(
                    severity=Severity.CRITICAL,
                    category="doi_not_found",
                    message=f"DOI does not resolve: {doi}",
                    snippet=doi,
                    suggestion="This DOI may be fabricated",
                    confidence=0.9,
                )
        except Exception:
            pass  # Don't report network errors for DOI checks

        return None

    def _check_fake_references(self, text: str) -> List[Finding]:
        """Check for reference patterns that look fabricated."""
        findings = []

        # Check for APA-style references that look suspicious
        # Pattern: Author, A. (Year). Title. Journal, Volume(Issue), Pages.
        apa_pattern = re.compile(
            r'([A-Z][a-z]+,\s+[A-Z]\.(?:,\s+[A-Z]\.)*)\s+\((\d{4})\)\.\s+(.+?)\.\s+([^,]+),\s+(\d+)(?:\((\d+)\))?,\s+(\d+[-–]\d+|\d+)\.'
        )

        for match in apa_pattern.finditer(text):
            journal = match.group(4).strip()
            # Check if journal name looks suspiciously generic
            generic_journals = ["Journal of Science", "Journal of Research",
                              "International Journal of Studies", "Journal of Data",
                              "Academic Research Journal"]
            for generic in generic_journals:
                if text_similarity(journal, generic) > 0.7:
                    findings.append(Finding(
                        severity=Severity.HIGH,
                        category="fake_citation",
                        message=f"Citation references a suspiciously generic journal: '{journal}'",
                        snippet=match.group(0)[:120],
                        suggestion="Verify this publication actually exists",
                        confidence=0.7,
                    ))
                    break

        # Check for arXiv references
        arxiv_pattern = re.compile(r'arXiv:(\d{4}\.\d{4,5})', re.IGNORECASE)
        for match in arxiv_pattern.finditer(text):
            arxiv_id = match.group(1)
            if self.verify_online:
                finding = self._check_arxiv(arxiv_id)
                if finding:
                    findings.append(finding)

        return findings

    def _check_arxiv(self, arxiv_id: str) -> Optional[Finding]:
        """Check if an arXiv paper exists."""
        session = self._get_session()
        if session is False:
            return None

        try:
            url = f"https://arxiv.org/abs/{arxiv_id}"
            response = session.head(url, timeout=self.timeout)
            if response.status_code == 404:
                return Finding(
                    severity=Severity.CRITICAL,
                    category="arxiv_not_found",
                    message=f"arXiv paper does not exist: {arxiv_id}",
                    snippet=f"arXiv:{arxiv_id}",
                    suggestion="This arXiv reference may be fabricated",
                    confidence=0.9,
                )
        except Exception:
            pass

        return None


def text_similarity(a: str, b: str) -> float:
    """Simple text similarity."""
    from .utils import text_similarity as ts
    return ts(a, b)

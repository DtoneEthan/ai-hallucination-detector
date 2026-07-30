"""
Web Search — online duplicate / source lookup
==============================================

Searches the web (DuckDuckGo HTML, no API key required) to check whether a
piece of text already exists online — i.e. "is there an identical or highly
similar paragraph somewhere on the web?".

This is a best-effort heuristic:
  * It performs an *exact quoted* search of a paragraph and inspects the
    returned results. If results come back, the paragraph (or something very
    close) likely exists online.
  * A character n-gram similarity between the paragraph and the best result
    snippet gives a rough "match strength".
  * It is NOT a substitute for academic databases (CNKI / WanFang / Turnitin).

The module degrades gracefully: when no network or `requests` is unavailable,
every call returns `found=False` with a `note` describing the failure.
"""

import re
import urllib.parse
from typing import Dict, List, Optional


def _strip_tags(html: str) -> str:
    """Remove HTML tags and unescape the most common entities."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#x27;", "'")
            .replace("&#39;", "'"))
    return re.sub(r"\s+", " ", text).strip()


def _extract_uddg(href: str) -> Optional[str]:
    """DuckDuckGo wraps the real URL in a `uddg=` query parameter."""
    if not href:
        return None
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        try:
            return urllib.parse.unquote(m.group(1))
        except Exception:
            return None
    return None


def _char_ngrams(text: str, n: int = 3) -> set:
    """Lowercase alphanumeric + CJK character n-grams."""
    low = (text or "").lower()
    # keep letters, digits and CJK; drop punctuation/whitespace
    chars = re.findall(r"[a-z0-9\u4e00-\u9fff]", low)
    if len(chars) < n:
        return {"".join(chars)}
    return {"".join(chars[i:i + n]) for i in range(len(chars) - n + 1)}


def _ngram_sim(a: str, b: str, n: int = 3) -> float:
    sa, sb = _char_ngrams(a, n), _char_ngrams(b, n)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / len(sa | sb)


def _split_sentences(text: str) -> List[str]:
    """Very small sentence splitter (enough to pick representative paragraphs)."""
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？；\n])\s*", text)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out or [text]


class WebSearcher:
    """Search the web to check whether text already exists online."""

    SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
    UA = ("Mozilla/5.0 (compatible; AIDocDetector/1.0; "
          "+https://github.com/DtoneEthan/ai-hallucination-detector)")

    def __init__(self, timeout: int = 15, max_results: int = 5):
        self.timeout = timeout
        self.max_results = max_results
        self._session = None

    # ---- request plumbing -------------------------------------------------
    def _get_session(self):
        if self._session is not None:
            return self._session
        try:
            import requests  # type: ignore
            s = requests.Session()
            s.headers.update({
                "User-Agent": self.UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            self._session = s
        except ImportError:
            self._session = False
        return self._session

    # ---- public API -------------------------------------------------------
    def search(self, query: str) -> List[Dict[str, str]]:
        """Return a list of {title, url, snippet}. Empty list on any failure."""
        q = urllib.parse.quote_plus(query)
        url = self.SEARCH_URL.format(query=q)
        session = self._get_session()
        if session is False:
            return []
        try:
            r = session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return []
            return self._parse_html(r.text)
        except Exception:
            return []

    @staticmethod
    def _parse_html(html: str) -> List[Dict[str, str]]:
        """Parse DuckDuckGo HTML results into structured records."""
        results: List[Dict[str, str]] = []
        blocks = re.split(r'(?=<a class="result__a")', html or "")
        for b in blocks:
            if 'result__a' not in b:
                continue
            m = re.search(
                r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                b, re.S,
            )
            if not m:
                continue
            href = m.group(1)
            title = _strip_tags(m.group(2))
            real = _extract_uddg(href) or href
            sm = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', b, re.S)
            snippet = _strip_tags(sm.group(1)) if sm else ""
            if title or snippet:
                results.append({
                    "title": title,
                    "url": real,
                    "snippet": snippet,
                })
        return results

    def check_paragraph(self, text: str) -> Dict:
        """Check whether a single paragraph/sentence exists online."""
        clean = (text or "").strip().strip('"').strip()
        if len(clean) < 12:
            return {"checked": False, "reason": "too_short",
                    "found": False, "results": [], "best_similarity": 0.0,
                    "query": ""}
        query = f'"{clean}"'
        try:
            results = self.search(query)[: self.max_results]
        except Exception as e:  # pragma: no cover - network dependent
            return {"checked": True, "found": False, "results": [],
                    "best_similarity": 0.0, "query": query,
                    "note": f"search failed: {e}"}
        found = len(results) > 0
        best_sim = max((_ngram_sim(clean, r["snippet"]) for r in results), default=0.0)
        return {
            "checked": True,
            "found": found,
            "results": results,
            "best_similarity": round(best_sim, 3),
            "query": query,
        }

    def check_text(self, text: str, top_n: int = 8, min_len: int = 20) -> Dict:
        """Check the most informative paragraphs of a longer text online."""
        sents = [s for s in _split_sentences(text) if len(s) >= min_len]
        # de-dup, then pick the longest (most distinctive) to limit requests
        seen, uniq = set(), []
        for s in sents:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        picked = sorted(uniq, key=len, reverse=True)[:top_n]
        checks = [self.check_paragraph(s) for s in picked]
        return {
            "paragraphs_checked": len(checks),
            "checks": checks,
        }

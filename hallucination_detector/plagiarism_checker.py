#!/usr/bin/env python3
"""
Plagiarism Checker (offline, heuristic)
======================================
Local approximate plagiarism detection: computes how much of a paper overlaps
with a set of reference documents (n-gram fingerprint matching) and how much
the paper repeats *itself* (internal self-plagiarism).

This is a FREE, offline heuristic — it does NOT connect to academic databases
(CNKI / Wanfang / Turnitin / PubMed). It only compares against the reference
documents *you* provide. Treat results as indicative only.

Algorithm (mirrors the web version in docs/plagiarism.html):
  - Build n-gram fingerprints: CJK text -> character 4-grams, English -> word 3-grams
  - Overall rate = fraction of the paper's n-grams covered by the union of references
  - Per-reference similarity = Jaccard(paper, reference)
  - Self-repetition rate = fraction of sentences that overlap >=0.55 with another sentence
  - Repeated fragments = sentences >=50% covered by some reference
"""

import re
from typing import Dict, List, Optional, Tuple


class PlagiarismChecker:
    """Offline, reference-based plagiarism estimator."""

    def __init__(self, n_cjk: int = 4, n_en: int = 3, max_sentences: int = 500):
        self.n_cjk = n_cjk
        self.n_en = n_en
        self.max_sentences = max_sentences

    # ---------------------------------------------------------------- utils
    @staticmethod
    def split_sentences(text: str) -> List[str]:
        if not text or not text.strip():
            return []
        # Split on sentence-ending punctuation (EN + CJK), keep delimiters attached
        raw = re.split(r"(?<=[.!?])\s+|(?<=[.!?])$|(?<=[。！？；])", text.strip())
        sentences: List[str] = []
        for part in raw:
            for sp in part.split("\n\n"):
                s = sp.strip()
                if not s:
                    continue
                cur = ""
                for line in s.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if cur:
                        if re.search(r"[.!?。！？；]$", cur):
                            sentences.append(cur)
                            cur = line
                        else:
                            cur += " " + line
                    else:
                        cur = line
                if cur:
                    sentences.append(cur)
        return sentences if sentences else [text]

    def build_ngrams(self, text: str) -> set:
        """Return a set of n-gram fingerprints for the given text."""
        low = (text or "").lower()
        cjk = re.sub(r"[a-z0-9]", "", low)
        eng = re.sub(r"[^a-z0-9\s]", "", low)
        grams = set()
        # CJK: character n-grams
        c_arr = list(cjk.replace(" ", ""))
        for i in range(len(c_arr) - self.n_cjk + 1):
            grams.add("c:" + "".join(c_arr[i : i + self.n_cjk]))
        # English: word n-grams
        words = eng.split()
        for i in range(len(words) - self.n_en + 1):
            grams.add("e:" + " ".join(words[i : i + self.n_en]))
        return grams

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        if len(a) < len(b):
            small, large = a, b
        else:
            small, large = b, a
        inter = sum(1 for x in small if x in large)
        return inter / (len(a) + len(b) - inter)

    @staticmethod
    def _intersect_count(a: set, b: set) -> int:
        small, large = (a, b) if len(a) < len(b) else (b, a)
        return sum(1 for x in small if x in large)

    # ---------------------------------------------------------------- core
    def check(
        self,
        paper: str,
        refs: Optional[List[str]] = None,
        ref_names: Optional[List[str]] = None,
    ) -> Dict:
        """Run plagiarism analysis.

        Args:
            paper: the text to check.
            refs: list of reference document texts.
            ref_names: optional display names for references.

        Returns:
            dict with keys: overall, self_rate, per_ref, fragments,
            paper_len, ref_count.
        """
        refs = refs or []
        ref_names = ref_names or [f"ref{i+1}" for i in range(len(refs))]

        p_set = self.build_ngrams(paper)

        ref_union: set = set()
        per_ref: List[Dict] = []
        for name, rtext in zip(ref_names, refs):
            rs = self.build_ngrams(rtext)
            ref_union |= rs
            per_ref.append({"name": name, "jaccard": self._jaccard(p_set, rs)})
        per_ref.sort(key=lambda x: x["jaccard"], reverse=True)

        overall = self._intersect_count(p_set, ref_union) / len(p_set) if p_set else 0.0

        # --- sentence-level precomputation (for self-rate + fragments) ---
        sents = [s for s in self.split_sentences(paper) if len(s.strip()) > 6]
        n = len(sents)
        sent_sets = [self.build_ngrams(s) for s in sents]

        # document frequency, used to drop ultra-frequent boilerplate n-grams
        df: Dict[str, int] = {}
        for g in sent_sets:
            for x in g:
                df[x] = df.get(x, 0) + 1
        kept = []
        for g in sent_sets:
            k = set(x for x in g if df.get(x, 0) <= max(2, int(n * 0.25)))
            kept.append(k)

        dup_sent = 0
        idxs = list(range(n))
        compare = (
            idxs[:: max(1, (n + self.max_sentences - 1) // self.max_sentences)]
            if n > self.max_sentences
            else idxs
        )
        for i in compare:
            if len(kept[i]) < 5:
                continue
            max_j = 0.0
            for j in idxs:
                if i == j or len(kept[j]) < 5:
                    continue
                jj = self._jaccard(kept[i], kept[j])
                if jj > max_j:
                    max_j = jj
            if max_j >= 0.55:
                dup_sent += 1
        self_rate = (dup_sent / len(compare)) if compare else 0.0

        # --- repeated fragments (sentence coverage by a reference) ---
        fragments: List[Dict] = []
        for pr in per_ref:
            if pr["jaccard"] < 0.02:
                continue
            rset = self.build_ngrams(refs[ref_names.index(pr["name"])])
            for i in range(n):
                if len(sents[i]) < 12:
                    continue
                cov = (
                    self._intersect_count(sent_sets[i], rset) / len(sent_sets[i])
                    if sent_sets[i]
                    else 0.0
                )
                if cov >= 0.5:
                    fragments.append(
                        {"ref": pr["name"], "text": sents[i], "score": cov}
                    )
        fragments.sort(key=lambda x: x["score"], reverse=True)
        fragments = fragments[:30]

        return {
            "overall": overall,
            "self_rate": self_rate,
            "per_ref": per_ref,
            "fragments": fragments,
            "paper_len": len(paper),
            "ref_count": len(refs),
        }

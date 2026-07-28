"""
Pattern Analyzer
================
Detects linguistic and structural patterns commonly associated with AI hallucinations.

Hallucination signatures:
    - Overly specific fabricated statistics
    - Plausible but unverifiable technical details
    - Fake API/method/library names
    - Internal contradictions
    - Excessive hedging or overconfidence
    - Hallucinated quotes and attributions
    - Repetitive "flavor text" patterns
    - Circular reasoning / self-referential claims
"""

import re
from collections import Counter
from typing import List, Tuple

from .utils import Finding, Severity, split_sentences, extract_numbers


class PatternAnalyzer:
    """Analyzes text for patterns commonly seen in AI hallucinations."""

    # --- Hallucination pattern signatures ---

    # Very specific numbers that are unlikely to be real
    # Matches comma-separated numbers (e.g., 1,247,832) or plain large numbers (e.g., 1234567)
    HYPER_SPECIFIC_NUMBER = re.compile(
        r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d{4,}(?:\.\d+)?\b'
    )

    # Fake-looking version numbers / release dates
    VERSION_PATTERN = re.compile(r'v?\d+\.\d+\.\d+(?:\.\d+)?')

    # Common hallucinated technical terms (checked against known real ones)
    REAL_FRAMEWORKS = {
        'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'Nuxt',
        'Django', 'Flask', 'FastAPI', 'Spring', 'Express',
        'TensorFlow', 'PyTorch', 'scikit-learn', 'Keras', 'JAX',
        'Pandas', 'NumPy', 'SciPy', 'Matplotlib', 'Plotly',
        'LangChain', 'LlamaIndex', 'Transformers',
    }

    # Hedging patterns — too many of these is suspicious
    HEDGE_PATTERNS = [
        r'\b(?:may|might|could|possibly|potentially|arguably|purportedly|reportedly|allegedly)\b',
        r'\b(?:it is (?:said|believed|thought|reported|claimed|argued|suggested))\b',
        r'\b(?:some (?:experts|sources|studies|researchers)|many (?:believe|think|argue))\b',
        r'(?:据说|据称|有人(?:认为|说)|有(?:研究|报告|调查)(?:表明|显示|指出)|可能|或许|大概|也许)',
    ]

    # Overconfidence patterns
    OVERCONFIDENCE_PATTERNS = [
        r'\b(?:undoubtedly|undeniably|indisputably|without (?:a )?doubt|beyond (?:any )?doubt|clearly|obviously|evidently|manifestly)\b',
        r'\b(?:it is (?:well )?known|it is widely (?:accepted|recognized|acknowledged|believed)|universally)\b',
        r'\b(?:definitely|certainly|absolutely|positively|invariably)\b',
        r'(?:毫无疑问|众所周知|不言而喻|绝对|确实|的确|毫无疑问地)',
    ]

    # "Flavor text" — generic filler that AI models produce
    FLAVOR_TEXT_PATTERNS = [
        r'In today\'s (?:rapidly )?(?:evolving|changing|fast-paced) world',
        r'It is important to note that',
        r'It\'s worth (?:noting|mentioning|considering) that',
        r'(?:As|Since) we (?:all know|navigate|move|enter)',
        r'(?:At the end of the day|In conclusion|To summarize)',
        r'(?:Furthermore|Moreover|Additionally|In addition),',
        r'plays a (?:crucial|vital|pivotal|significant|key) (?:role|part)',
        r'在当今(?:社会|时代|世界)',
        r'随着(?:社会|时代|科技)的(?:发展|进步)',
        r'众所周知',
        r'值得一提',
    ]

    # Patterns suggesting fabricated research/studies
    FAKE_STUDY_PATTERNS = [
        r'A (?:recent )?(?:study|survey|report|research) (?:conducted|published|released) by\s+([^,.]+)',
        r'(?:According to|Based on) a (?:recent )?(?:study|survey|report) by\s+([^,.]+)',
        r'研究表明[^，。]*?(?:发现|显示|指出)',
    ]

    def __init__(self):
        self._compiled_hedges = [re.compile(p, re.IGNORECASE) for p in self.HEDGE_PATTERNS]
        self._compiled_overconf = [re.compile(p, re.IGNORECASE) for p in self.OVERCONFIDENCE_PATTERNS]
        self._compiled_flavor = [re.compile(p, re.IGNORECASE) for p in self.FLAVOR_TEXT_PATTERNS]
        self._compiled_fake_study = [re.compile(p, re.IGNORECASE) for p in self.FAKE_STUDY_PATTERNS]

    def analyze(self, text: str) -> List[Finding]:
        """Run all pattern analysis checks and return findings."""
        findings = []
        sentences = split_sentences(text)

        findings.extend(self._check_hyper_specific_numbers(text, sentences))
        findings.extend(self._check_hedging_density(text))
        findings.extend(self._check_overconfidence(text))
        findings.extend(self._check_flavor_text(text))
        findings.extend(self._check_fake_studies(text, sentences))
        findings.extend(self._check_internal_contradictions(sentences))
        findings.extend(self._check_repetition(text, sentences))
        findings.extend(self._check_fabricated_entities(text, sentences))

        return findings

    def _check_hyper_specific_numbers(self, text: str, sentences: List[str]) -> List[Finding]:
        """Detect overly specific numbers that may be fabricated."""
        findings = []
        for idx, sentence in enumerate(sentences):
            numbers = self.HYPER_SPECIFIC_NUMBER.findall(sentence)
            for num in numbers:
                # Skip arXiv IDs (e.g., arXiv:1706.03762)
                if 'arXiv' in sentence or 'arxiv' in sentence.lower():
                    continue
                # Remove commas and check digits
                digits = num.replace(',', '').replace('.', '')
                if len(digits) >= 7:  # 7+ digit numbers are suspiciously specific
                    # Check if the number appears in a statistical context
                    context_patterns = [
                        r'(?:users?|people|customers?|articles?|papers?|studies?|cases?|instances?)',
                        r'(?:用户|人|文章|论文|研究|案例|实例)',
                    ]
                    is_stat = any(re.search(p, sentence, re.IGNORECASE) for p in context_patterns)
                    if is_stat:
                        findings.append(Finding(
                            severity=Severity.MEDIUM,
                            category="hyper_specific_number",
                            message=f"Very specific statistic ({num}) in a factual context — verify this number",
                            snippet=sentence[:120],
                            location=f"sentence {idx + 1}",
                            suggestion=f"Search for this exact figure: {num}",
                            confidence=0.55,
                        ))
        return findings

    def _check_hedging_density(self, text: str) -> List[Finding]:
        """Too much hedging language can indicate uncertainty/hallucination."""
        findings = []
        total_hedges = 0
        hedge_locations = []

        for pattern in self._compiled_hedges:
            for match in pattern.finditer(text):
                total_hedges += 1
                hedge_locations.append(match.group())

        # Calculate density
        word_count = len(text.split())
        if word_count > 0:
            density = total_hedges / word_count
            if density > 0.03:  # more than 3% hedge words
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category="excessive_hedging",
                    message=f"High density of hedging language ({total_hedges} instances, {density:.1%} of text) — model may be uncertain",
                    snippet=", ".join(hedge_locations[:5]),
                    suggestion="Hedging doesn't guarantee hallucination, but high density correlates with fabricated content",
                    confidence=0.45,
                ))
        return findings

    def _check_overconfidence(self, text: str) -> List[Finding]:
        """Excessive overconfidence can also be a hallucination indicator."""
        findings = []
        total_confident = 0
        confident_locations = []

        for pattern in self._compiled_overconf:
            for match in pattern.finditer(text):
                total_confident += 1
                confident_locations.append(match.group())

        if total_confident >= 3:
            findings.append(Finding(
                severity=Severity.LOW,
                category="excessive_overconfidence",
                message=f"Multiple absolute certainty claims ({total_confident} instances) — hallucinated content often uses overconfident language",
                snippet=", ".join(confident_locations[:5]),
                suggestion="Verify claims that use absolute language especially carefully",
                confidence=0.35,
            ))
        return findings

    def _check_flavor_text(self, text: str) -> List[Finding]:
        """Detect generic filler text patterns."""
        findings = []
        flavor_count = 0
        flavor_snippets = []

        for pattern in self._compiled_flavor:
            for match in pattern.finditer(text):
                flavor_count += 1
                flavor_snippets.append(match.group()[:50])

        if flavor_count >= 3:
            findings.append(Finding(
                severity=Severity.LOW,
                category="excessive_flavor_text",
                message=f"High frequency of generic filler phrases ({flavor_count} instances) — content may be padded with AI-generated boilerplate",
                snippet=" | ".join(flavor_snippets[:4]),
                suggestion="Filler text isn't inherently hallucinated, but it often accompanies fabricated content",
                confidence=0.25,
            ))
        return findings

    def _check_fake_studies(self, text: str, sentences: List[str]) -> List[Finding]:
        """Detect references to possibly fabricated studies or institutions."""
        findings = []
        for idx, sentence in enumerate(sentences):
            for pattern in self._compiled_fake_study:
                match = pattern.search(sentence)
                if match:
                    source = match.group(1) if match.groups() else "unknown"
                    source = source.strip()

                    # Check if the source looks suspicious
                    suspicious_sources = [
                        "the Institute", "the Research Center",
                        "the Data Lab", "the Innovation Group",
                        "the Analysis Group", "the Study Center",
                    ]
                    is_suspicious = any(s.lower() in source.lower() for s in suspicious_sources)

                    # Check if it's a real institution name (heuristic: has proper noun)
                    has_real_org = re.search(r'\b[A-Z][a-z]+\s+(?:University|Institute|Lab|Center|Foundation|Society|Association)\b', source)

                    severity = Severity.HIGH if is_suspicious else Severity.MEDIUM
                    confidence = 0.7 if is_suspicious else 0.45

                    findings.append(Finding(
                        severity=severity,
                        category="possibly_fake_study",
                        message=f"References a study by '{source}' — verify this institution and study exist",
                        snippet=sentence[:120],
                        location=f"sentence {idx + 1}",
                        suggestion=f"Search for: \"{source}\" to verify it exists",
                        confidence=confidence,
                    ))
        return findings

    def _check_internal_contradictions(self, sentences: List[str]) -> List[Finding]:
        """Detect when the text contradicts itself."""
        findings = []

        # Extract numerical claims and check for contradictions
        num_claims = []
        for idx, sentence in enumerate(sentences):
            numbers = extract_numbers(sentence)
            for num in numbers:
                # Extract the leading numeric part (digits with optional decimal)
                # This handles "1.5 billion", "87.3%", "$2.5 million", etc.
                num_match = re.match(r'[\d,.]+', num)
                if not num_match:
                    continue
                raw_num = num_match.group()
                # Parse the numeric value, handling commas and decimals
                clean = raw_num.replace(',', '')
                try:
                    if '.' in clean:
                        val = float(clean)
                    else:
                        val = int(clean)
                    # Skip zero and negative (meaningless for contradiction)
                    if val <= 0:
                        continue
                    num_claims.append((val, num, idx, sentence))
                except ValueError:
                    continue

        # Check for contradictory numbers in similar contexts
        for i, (val1, raw1, idx1, sent1) in enumerate(num_claims):
            for j, (val2, raw2, idx2, sent2) in enumerate(num_claims[i+1:], i+1):
                if abs(idx1 - idx2) > 10:  # only check nearby sentences
                    continue
                if idx1 == idx2:  # skip numbers from the same sentence
                    continue
                # If they refer to the same thing but give different numbers
                # (simple heuristic: similar sentence context but different values)
                if val1 != val2:
                    # Check if sentences are about the same topic
                    from .utils import text_similarity
                    sim = text_similarity(sent1, sent2)
                    if sim > 0.4:  # similar sentences with different numbers
                        findings.append(Finding(
                            severity=Severity.HIGH,
                            category="internal_contradiction",
                            message=f"Possible contradiction: '{raw1}' vs '{raw2}' in similar contexts",
                            snippet=f'"{sent1[:80]}..." vs "{sent2[:80]}..."',
                            location=f"sentences {idx1+1} vs {idx2+1}",
                            suggestion="Check if these refer to the same metric — contradiction is a hallucination signal",
                            confidence=0.6,
                        ))
        return findings

    def _check_repetition(self, text: str, sentences: List[str]) -> List[Finding]:
        """Detect suspicious repetition patterns."""
        findings = []

        # Check for repeated phrases across sentences
        phrase_counts = Counter()
        for sentence in sentences:
            # Extract n-grams (3-4 word phrases)
            words = sentence.lower().split()
            for i in range(len(words) - 2):
                phrase = ' '.join(words[i:i+3])
                if len(phrase) > 10:
                    phrase_counts[phrase] += 1

        # Phrases repeated 3+ times are suspicious
        for phrase, count in phrase_counts.items():
            if count >= 3:
                findings.append(Finding(
                    severity=Severity.LOW,
                    category="repetitive_phrasing",
                    message=f"Phrase repeated {count} times: '{phrase}'",
                    snippet=phrase,
                    suggestion="Repetition may indicate AI-generated padding rather than genuine content",
                    confidence=0.2,
                ))

        return findings

    def _check_fabricated_entities(self, text: str, sentences: List[str]) -> List[Finding]:
        """Detect possibly fabricated technical entities (APIs, libraries, methods)."""
        findings = []

        # Find CamelCase or snake_case identifiers that look like API names
        identifier_pattern = re.compile(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b')
        snake_pattern = re.compile(r'\b([a-z][a-z_]*_[a-z_]+)\b')

        potential_entities = set()
        for match in identifier_pattern.finditer(text):
            entity = match.group(1)
            # Skip if it's a known framework
            if entity not in self.REAL_FRAMEWORKS:
                # Check if it looks like a made-up library name
                if len(entity) > 6 and entity not in {'JavaScript', 'TypeScript', 'GitHub', 'StackOverflow'}:
                    potential_entities.add(entity)

        for match in snake_pattern.finditer(text):
            entity = match.group(1)
            if len(entity) > 8:
                potential_entities.add(entity)

        for entity in list(potential_entities)[:10]:  # limit to 10 findings
            # Check if it appears in a technical context
            context = text.lower()
            tech_context = any(kw in context for kw in ['api', 'function', 'method', 'library', 'package',
                                                          'import', 'install', 'install', 'version'])
            if tech_context:
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category="possible_fake_entity",
                    message=f"Technical entity '{entity}' may not exist — verify it's a real library/API/method",
                    snippet=entity,
                    suggestion=f"Search for '{entity}' in official documentation or package registries",
                    confidence=0.4,
                ))

        return findings

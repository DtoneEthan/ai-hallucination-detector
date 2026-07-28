# AI Hallucination Detector

A multi-strategy toolkit for detecting potential **AI hallucinations** in text. It analyzes AI-generated content using linguistic pattern detection, claim extraction, URL/citation verification, and optional web-based fact checking.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-beta-orange.svg)

> **Ethan X 工作室出品** · Produced by Ethan X Studio

## Why?

Large language models sometimes produce text that **looks authoritative but contains fabricated facts** — nonexistent studies, invented URLs, fake statistics, contradictory claims. This tool helps you catch those before they cause damage.

## Features

| Strategy | What It Detects | Requires Network |
|---|---|---|
| **Claim Extraction** | Extracts factual claims (statistics, dates, citations, technical assertions) and scores their verifiability | No |
| **Pattern Analysis** | Hedging language, overconfidence, flavor text, fabricated entities, internal contradictions, hyper-specific numbers | No |
| **URL Verification** | Broken links, DNS failures, suspicious domain patterns, fake DOIs, nonexistent arXiv papers | Yes (partial offline) |
| **Fact Checking** | Cross-references extracted claims against web search results | Yes |

## Installation

```bash
# From source
git clone https://github.com/DtoneEthan/ai-hallucination-detector.git
cd ai-hallucination-detector
pip install -e .

# Or just install dependencies
pip install -r requirements.txt
```

## Quick Start

### CLI

```bash
# Analyze a file
hallucination-detector detect article.txt

# Analyze inline text
hallucination-detector detect --text "A 2024 study by the Global Research Institute found that 87.3% of users prefer AI-generated content."

# Output as JSON
hallucination-detector detect article.txt --format json -o report.json

# Markdown report
hallucination-detector detect article.txt --format markdown -o report.md

# Offline mode (no network requests — pattern analysis only)
hallucination-detector detect article.txt --offline

# Interactive mode
hallucination-detector interactive
```

### Python API

```python
from hallucination_detector import HallucinationDetector

detector = HallucinationDetector(verify_online=True)
result = detector.analyze("Your AI-generated text here...")

print(result.summary())
# "Hallucination Risk: 62.5/100 (HIGH) — 8 findings"

# Get detailed terminal report
print(result.terminal_report())

# Get JSON for programmatic use
json_str = result.json_report()

# Get Markdown report
md_str = result.markdown_report()
```

### Selecting Specific Strategies

```python
# Only use pattern analysis (fastest, fully offline)
detector = HallucinationDetector(
    verify_online=False,
    enable_strategies=["claim_extraction", "pattern_analysis"]
)

# Only verify URLs (if you just want to check links)
detector = HallucinationDetector(
    enable_strategies=["url_verification"]
)
```

## Output Example

```
================================================================
  AI Hallucination Detection Report
  Generated: 2026-07-28 14:30:00
================================================================

  OVERALL RISK SCORE
    Score:  62.5/100 (HIGH)
    Findings: 8

    ██████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░
    LOW              MOD              HIGH             CRIT

  FINDINGS BY SEVERITY
    CRITICAL                         2
    HIGH                             3
    MEDIUM                           2
    LOW                              1

  TOP ISSUES
    • [CRITICAL] fake_url_domain: URL domain contains hallucinated pattern
    • [CRITICAL] url_dns_failure: URL domain does not resolve (DNS failure)
    • [HIGH] number_not_found: Specific number '87.3%' not found in any search result
    • [HIGH] possibly_fake_study: References a study by 'the Global Research Institute'
    • [HIGH] internal_contradiction: Possible contradiction: '1.2 million' vs '950,000'
```

## How It Works

```
Input Text
    │
    ▼
┌──────────────────┐     ┌────────────────────┐
│  Claim Extractor │────▶│  Pattern Analyzer  │
│  (extract facts) │     │  (linguistic signs)│
└──────────────────┘     └────────────────────┘
         │                         │
         │              ┌──────────┘
         ▼              ▼
┌──────────────────┐  ┌────────────────────┐
│  URL Verifier    │  │  Fact Checker       │
│  (check links)   │  │  (web search)       │
└──────────────────┘  └────────────────────┘
         │                         │
         └──────────┬──────────────┘
                    ▼
         ┌────────────────────┐
         │  Confidence Scorer │
         │  (aggregate score) │
         └────────────────────┘
                    │
                    ▼
         ┌────────────────────┐
         │     Reporter       │
         │  (terminal/JSON/MD)│
         └────────────────────┘
```

### Scoring Model

Each finding contributes a weighted risk delta to the overall score (0-100):

- **Base weight** from severity: CRITICAL=40, HIGH=22, MEDIUM=10, LOW=4
- **Category multiplier**: stronger signals (e.g., `fake_url_domain`) get 1.5x; weaker signals (e.g., `repetitive_phrasing`) get 0.3x
- **Confidence factor**: each finding's confidence (0-1) modulates its contribution
- **Diminishing returns**: logarithmic scaling prevents a flood of low-severity findings from inflating the score

| Score Range | Risk Level |
|---|---|
| 0-24 | LOW |
| 25-44 | MODERATE |
| 45-69 | HIGH |
| 70-100 | CRITICAL |

## Detection Categories

| Category | Severity | Description |
|---|---|---|
| `fake_url_domain` | CRITICAL | URL domain contains hallucinated patterns (e.g., "research-paper.com") |
| `url_dns_failure` | CRITICAL | URL domain doesn't resolve via DNS — domain likely doesn't exist |
| `url_404` | CRITICAL | URL returns HTTP 404 |
| `doi_not_found` | CRITICAL | DOI doesn't resolve via doi.org |
| `arxiv_not_found` | CRITICAL | arXiv paper ID doesn't exist |
| `fake_citation` | HIGH | Citation references a suspiciously generic journal |
| `internal_contradiction` | HIGH | Text contradicts itself (different numbers for same metric) |
| `possibly_fake_study` | HIGH/MEDIUM | References a study by an unverifiable institution |
| `number_not_found` | HIGH | Specific statistic not found in web search results |
| `source_not_found` | HIGH | Cited source not found in web search results |
| `hyper_specific_number` | MEDIUM | Very specific 7+ digit number in a statistical context |
| `excessive_hedging` | MEDIUM | High density of hedging language (>3% of text) |
| `possible_fake_entity` | MEDIUM | Technical entity (API/library/method) may not exist |
| `excessive_overconfidence` | LOW | Multiple absolute certainty claims |
| `excessive_flavor_text` | LOW | High frequency of generic AI filler phrases |
| `repetitive_phrasing` | LOW | Same 3-word phrase repeated 3+ times |

## Limitations

- **No tool can perfectly detect hallucinations.** This is a heuristic system that flags *suspicious patterns* — it will have false positives and false negatives.
- **Web search may not cover all sources.** A claim not found in search results isn't necessarily false.
- **Chinese language support is basic.** Pattern matching works but is optimized for English text.
- **Rate limits.** Web-based verification checks a limited number of URLs/claims to avoid being blocked.

**Always verify critical claims manually.**

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy hallucination_detector

# Linting
flake8 hallucination_detector
```

## Project Structure

```
ai-hallucination-detector/
├── hallucination_detector/
│   ├── __init__.py          # Package exports
│   ├── __main__.py          # python -m hallucination_detector
│   ├── cli.py               # CLI interface (argparse)
│   ├── detector.py          # Main orchestrator
│   ├── claim_extractor.py   # Claim extraction & verifiability
│   ├── url_verifier.py      # URL/DOI/citation verification
│   ├── pattern_analyzer.py # Hallucination pattern detection
│   ├── fact_checker.py      # Web-based fact checking
│   ├── scorer.py            # Confidence scoring
│   ├── reporter.py          # Report generation
│   └── utils.py             # Shared utilities
├── examples/
│   ├── sample_ai_text.txt   # Text with hallucinations
│   └── sample_clean.txt     # Well-sourced text
├── tests/
│   └── test_detector.py     # Unit tests
├── pyproject.toml
├── setup.py
├── requirements.txt
├── LICENSE
├── .gitignore
└── README.md
```

## Contributing

Pull requests welcome! Areas that need help:

1. **More language support** — better Chinese/Japanese/Korean pattern detection
2. **Additional fact-checking sources** — Wikipedia API, Google Scholar, Semantic Scholar
3. **ML-based detection** — train a classifier on labeled hallucinated vs. real text
4. **More hallucination patterns** — share examples of hallucinated text to improve detection

## License

MIT — see [LICENSE](LICENSE).

## Citation

If you use this tool in research, please cite:

```bibtex
@software{xu2026hallucination,
  title={AI Hallucination Detector: A Multi-Strategy Toolkit},
  author={Xu, Ethan},
  year={2026},
  url={https://github.com/ethanxu/ai-hallucination-detector}
}
```

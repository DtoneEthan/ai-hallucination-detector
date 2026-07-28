# AI Hallucination Detection Report

**Generated:** 2026-07-28 14:17:40

## Summary

| Metric | Value |
|--------|-------|
| Overall Risk Score | **100.0/100** |
| Risk Level | **CRITICAL** |
| Total Findings | 11 |

### Findings by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| MEDIUM | 4 |
| LOW | 4 |

### Findings by Category

| Category | Risk Contribution |
|----------|-------------------|
| `fake_url_domain` | 175.5 |
| `possible_fake_entity` | 21.0 |
| `hyper_specific_number` | 7.0 |
| `offline_risk_indicators` | 2.6 |
| `excessive_overconfidence` | 1.6 |
| `excessive_flavor_text` | 1.0 |

## Top Issues

- [CRITICAL] fake_url_domain: URL domain contains hallucinated pattern: 'research-paper'
- [CRITICAL] fake_url_domain: URL domain contains hallucinated pattern: 'official-source'
- [CRITICAL] fake_url_domain: URL domain contains hallucinated pattern: 'verified-data'
- [MEDIUM] possible_fake_entity: Technical entity 'NeuralTextPro' may not exist — verify it's a real library/API/method
- [MEDIUM] possible_fake_entity: Technical entity 'calculate_confidence_score' may not exist — verify it's a real library/API/method

## Extracted Claims (15 total)

1. **[numerical]** (verifiability: 80%)
   > According to a 2024 study by the Global Research Institute, 87.3% of users prefer AI-generated content over human-written text.

2. **[numerical]** (verifiability: 80%)
   > found that the average user spends 12.4 hours per day interacting with AI assistants.

3. **[numerical]** (verifiability: 80%)
   > The research was published at https://www.research-paper.com/studies/harrison2024 and is available at https://www.official-source.org/data/survey-resu...

4. **[numerical]** (verifiability: 80%)
   > Furthermore, the market for AI tools reached $847.5 billion in 2023.

5. **[numerical]** (verifiability: 80%)
   > However, the same market was valued at only $295 billion in 2022, before growing to $1.2 trillion by early 2024.

6. **[numerical]** (verifiability: 80%)
   > The Institute for Data Analysis confirmed that 99.7% of experts agree.

7. **[numerical]** (verifiability: 70%) ⚠️ Highly specific number: 1,247,832
   > The study, published in the Journal of Contemporary Digital Studies, surveyed 1,247,832 participants across 42 countries.

8. **[numerical]** (verifiability: 70%) ⚠️ Highly specific number: 2024.99999
   > Additional findings can be found in the arXiv paper 2024.99999.

9. **[citation]** (verifiability: 70%)
   > Emily Harrison et al.

10. **[citation]** (verifiability: 70%)
   > For more information, visit https://www.verified-data.net/research or check the study by Smith et al.

11. **[technical]** (verifiability: 50%)
   > The calculate_confidence_score() method in the NeuralTextPro library is particularly noteworthy.

12. **[technical]** (verifiability: 40%) ⚠️ Absolute language: 'it is widely recognized'
   > It is widely recognized that the GlobalDataPro framework provides the most accurate results.

13. **[other]** (verifiability: 30%) ⚠️ Absolute language: 'all'
   > This is a sample text containing several common types of AI hallucinations.

14. **[other]** (verifiability: 30%)
   > In today's rapidly evolving world, AI plays a crucial role in various industries.

15. **[other]** (verifiability: 30%) ⚠️ Absolute language: 'all'
   > It is important to note that these findings are universally accepted and beyond any doubt.

## Detailed Findings

### 1. 🟡 [MEDIUM] hyper_specific_number
**Message:** Very specific statistic (1,247,832) in a factual context — verify this number

> The study, published in the Journal of Contemporary Digital Studies, surveyed 1,247,832 participants across 42 countries

*Suggestion: Search for this exact figure: 1,247,832*

*Location: sentence 3*

### 2. 🟢 [LOW] excessive_overconfidence
**Message:** Multiple absolute certainty claims (3 instances) — hallucinated content often uses overconfident language

> beyond any doubt, It is widely recognized, universally

*Suggestion: Verify claims that use absolute language especially carefully*

### 3. 🟢 [LOW] excessive_flavor_text
**Message:** High frequency of generic filler phrases (4 instances) — content may be padded with AI-generated boilerplate

> In today's rapidly evolving world | It is important to note that | Furthermore, | plays a crucial role

*Suggestion: Filler text isn't inherently hallucinated, but it often accompanies fabricated content*

### 4. 🟡 [MEDIUM] possible_fake_entity
**Message:** Technical entity 'NeuralTextPro' may not exist — verify it's a real library/API/method

> NeuralTextPro

*Suggestion: Search for 'NeuralTextPro' in official documentation or package registries*

### 5. 🟡 [MEDIUM] possible_fake_entity
**Message:** Technical entity 'calculate_confidence_score' may not exist — verify it's a real library/API/method

> calculate_confidence_score

*Suggestion: Search for 'calculate_confidence_score' in official documentation or package registries*

### 6. 🟡 [MEDIUM] possible_fake_entity
**Message:** Technical entity 'GlobalDataPro' may not exist — verify it's a real library/API/method

> GlobalDataPro

*Suggestion: Search for 'GlobalDataPro' in official documentation or package registries*

### 7. 🔴 [CRITICAL] fake_url_domain
**Message:** URL domain contains hallucinated pattern: 'research-paper'

> https://www.research-paper.com/studies/harrison2024

*Suggestion: This URL is very likely fabricated by an AI model*

*Location: domain: www.research-paper.com*

### 8. 🔴 [CRITICAL] fake_url_domain
**Message:** URL domain contains hallucinated pattern: 'official-source'

> https://www.official-source.org/data/survey-results

*Suggestion: This URL is very likely fabricated by an AI model*

*Location: domain: www.official-source.org*

### 9. 🔴 [CRITICAL] fake_url_domain
**Message:** URL domain contains hallucinated pattern: 'verified-data'

> https://www.verified-data.net/research

*Suggestion: This URL is very likely fabricated by an AI model*

*Location: domain: www.verified-data.net*

### 10. 🟢 [LOW] offline_risk_indicators
**Message:** Risk indicators found (offline analysis): Highly specific number: 1,247,832

> The study, published in the Journal of Contemporary Digital Studies, surveyed 1,247,832 participants across 42 countries

*Suggestion: Run with --online flag to verify claims against web sources*

*Location: claim type: numerical, verifiability: 70%*

### 11. 🟢 [LOW] offline_risk_indicators
**Message:** Risk indicators found (offline analysis): Highly specific number: 2024.99999

> Additional findings can be found in the arXiv paper 2024.99999.

*Suggestion: Run with --online flag to verify claims against web sources*

*Location: claim type: numerical, verifiability: 70%*

---

*This tool uses heuristics and cannot guarantee accuracy. Always verify critical claims manually.*
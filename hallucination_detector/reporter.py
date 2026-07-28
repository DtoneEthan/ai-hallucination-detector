"""
Reporter
========
Generates human-readable and machine-readable reports from analysis results.

Output formats:
    - Terminal (with colors)
    - Plain text
    - JSON
    - Markdown
"""

import json
from datetime import datetime
from typing import List, Optional

from .utils import Finding, Severity
from .scorer import ScoreBreakdown
from .claim_extractor import Claim


class Reporter:
    """Formats analysis results into various output formats."""

    # Risk level colors (ANSI)
    RISK_COLORS = {
        "CRITICAL": "\033[1;31m",  # bold red
        "HIGH": "\033[31m",         # red
        "MODERATE": "\033[33m",     # yellow
        "LOW": "\033[32m",          # green
    }

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"

    def __init__(self, use_color: bool = True):
        self.use_color = use_color

    def _c(self, code: str, text: str) -> str:
        """Wrap text with ANSI color code if color is enabled."""
        if not self.use_color:
            return text
        return f"{code}{text}{self.RESET}"

    def terminal_report(self, text: str, findings: List[Finding],
                        score: ScoreBreakdown, claims: List[Claim]) -> str:
        """Generate a rich, colored report for terminal output."""
        lines = []

        # Header
        lines.append(self._c(self.BOLD, "=" * 64))
        lines.append(self._c(self.BOLD, "  AI Hallucination Detection Report"))
        lines.append(self._c(self.DIM, f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
        lines.append(self._c(self.BOLD, "=" * 64))
        lines.append("")

        # Overall Score
        risk_color = self.RISK_COLORS.get(score.risk_level, "")
        lines.append(self._c(self.BOLD, "  OVERALL RISK SCORE"))
        lines.append(f"    Score:  {self._c(risk_color, f'{score.overall:.1f}/100')} ({self._c(risk_color, score.risk_level)})")
        lines.append(f"    Findings: {score.total_findings}")
        lines.append("")

        # Score Bar (visual)
        bar_width = 50
        filled = int(score.overall / 100 * bar_width)
        bar_char = "\u2588" * filled + "\u2591" * (bar_width - filled)
        lines.append(f"    {self._c(risk_color, bar_char)}")
        lines.append(f"    {'LOW':<{bar_width//3}}{'MOD':<{bar_width//3}}{'HIGH':<{bar_width//3}}{'CRIT'}")
        lines.append("")

        # Severity Summary
        lines.append(self._c(self.BOLD, "  FINDINGS BY SEVERITY"))
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = score.by_severity.get(sev, 0)
            if count > 0:
                sev_obj = Severity[sev]
                lines.append(f"    {str(sev_obj):<30} {count}")
        lines.append("")

        # Category Breakdown
        if score.by_category:
            lines.append(self._c(self.BOLD, "  FINDINGS BY CATEGORY"))
            for cat, val in sorted(score.by_category.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"    {cat:<30} {val:.1f}")
            lines.append("")

        # Top Issues
        lines.append(self._c(self.BOLD, "  TOP ISSUES"))
        for issue in score.top_issues:
            lines.append(f"    {self._c(self.CYAN, '\u2022')} {issue}")
        if not score.top_issues or score.top_issues == ["No issues detected"]:
            lines.append(f"    {self._c('\033[32m', '\u2713')} No issues detected")
        lines.append("")

        # Extracted Claims Summary
        if claims:
            lines.append(self._c(self.BOLD, f"  EXTRACTED CLAIMS ({len(claims)} total)"))
            for i, claim in enumerate(claims[:10]):  # show top 10
                risk = ""
                if claim.risk_indicators:
                    risk = self._c("\033[33m", f" [{', '.join(claim.risk_indicators[:2])}]")
                lines.append(f"    {i+1}. [{claim.claim_type}] (v={claim.verifiability:.0%})")
                lines.append(f"       {claim.text[:100]}{'...' if len(claim.text) > 100 else ''}{risk}")
            if len(claims) > 10:
                lines.append(f"    ... and {len(claims) - 10} more claims")
            lines.append("")

        # Detailed Findings
        if findings:
            lines.append(self._c(self.BOLD, "  DETAILED FINDINGS"))
            lines.append("-" * 64)
            for i, finding in enumerate(findings):
                lines.append(f"  {i+1}. {finding}")
                lines.append("")
            lines.append("-" * 64)
        else:
            lines.append(self._c("\033[32m", "  No issues found. The text appears to be well-sourced."))

        # Footer
        lines.append("")
        lines.append(self._c(self.DIM, "=" * 64))
        lines.append(self._c(self.DIM, "  Note: This tool uses heuristics and cannot guarantee accuracy."))
        lines.append(self._c(self.DIM, "  Always verify critical claims manually."))
        lines.append(self._c(self.DIM, "=" * 64))

        return "\n".join(lines)

    def json_report(self, text: str, findings: List[Finding],
                    score: ScoreBreakdown, claims: List[Claim]) -> str:
        """Generate a JSON report."""
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "tool": "AI Hallucination Detector",
                "version": "1.0.0",
            },
            "summary": score.to_dict(),
            "claims": [
                {
                    "text": c.text[:200],
                    "type": c.claim_type,
                    "verifiability": round(c.verifiability, 2),
                    "evidence": c.evidence,
                    "risk_indicators": c.risk_indicators,
                }
                for c in claims
            ],
            "findings": [
                {
                    "severity": f.severity.to_plain(),
                    "category": f.category,
                    "message": f.message,
                    "snippet": f.snippet,
                    "location": f.location,
                    "suggestion": f.suggestion,
                    "confidence": round(f.confidence, 2),
                }
                for f in findings
            ],
        }
        return json.dumps(report, indent=2, ensure_ascii=False)

    def markdown_report(self, text: str, findings: List[Finding],
                        score: ScoreBreakdown, claims: List[Claim]) -> str:
        """Generate a Markdown report."""
        lines = []

        # Header
        lines.append("# AI Hallucination Detection Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Overall Risk Score | **{score.overall:.1f}/100** |")
        lines.append(f"| Risk Level | **{score.risk_level}** |")
        lines.append(f"| Total Findings | {score.total_findings} |")
        lines.append("")

        # Severity breakdown
        lines.append("### Findings by Severity")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = score.by_severity.get(sev, 0)
            if count > 0:
                lines.append(f"| {sev} | {count} |")
        lines.append("")

        # Category breakdown
        if score.by_category:
            lines.append("### Findings by Category")
            lines.append("")
            lines.append("| Category | Risk Contribution |")
            lines.append("|----------|-------------------|")
            for cat, val in sorted(score.by_category.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| `{cat}` | {val:.1f} |")
            lines.append("")

        # Top issues
        lines.append("## Top Issues")
        lines.append("")
        for issue in score.top_issues:
            lines.append(f"- {issue}")
        lines.append("")

        # Claims
        if claims:
            lines.append(f"## Extracted Claims ({len(claims)} total)")
            lines.append("")
            for i, claim in enumerate(claims[:15]):
                risk_str = ""
                if claim.risk_indicators:
                    risk_str = f" \u26A0\uFE0F {', '.join(claim.risk_indicators[:2])}"
                lines.append(f"{i+1}. **[{claim.claim_type}]** (verifiability: {claim.verifiability:.0%}){risk_str}")
                lines.append(f"   > {claim.text[:150]}{'...' if len(claim.text) > 150 else ''}")
                lines.append("")

        # Detailed findings
        if findings:
            lines.append("## Detailed Findings")
            lines.append("")
            for i, finding in enumerate(findings):
                emoji = {"CRITICAL": "\U0001F534", "HIGH": "\U0001F7E0", "MEDIUM": "\U0001F7E1",
                         "LOW": "\U0001F7E2", "INFO": "\u2139\uFE0F"}.get(finding.severity.to_plain(), "")
                lines.append(f"### {i+1}. {emoji} [{finding.severity.to_plain()}] {finding.category}")
                lines.append(f"**Message:** {finding.message}")
                lines.append("")
                if finding.snippet:
                    lines.append(f"> {finding.snippet}")
                    lines.append("")
                if finding.suggestion:
                    lines.append(f"*Suggestion: {finding.suggestion}*")
                    lines.append("")
                if finding.location:
                    lines.append(f"*Location: {finding.location}*")
                    lines.append("")

        # Disclaimer
        lines.append("---")
        lines.append("")
        lines.append("*This tool uses heuristics and cannot guarantee accuracy. Always verify critical claims manually.*")

        return "\n".join(lines)

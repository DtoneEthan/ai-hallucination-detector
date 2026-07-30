#!/usr/bin/env python3
"""
AI Hallucination Detector — CLI Interface
=========================================
Command-line tool for detecting potential AI hallucinations in text.

Usage:
    # Analyze text from a file
    python -m hallucination_detector detect sample.txt

    # Analyze text from stdin
    echo "Some AI-generated text..." | python -m hallucination_detector detect -

    # Analyze with online verification disabled
    python -m hallucination_detector detect sample.txt --offline

    # Output as JSON
    python -m hallucination_detector detect sample.txt --format json

    # Output as Markdown to a file
    python -m hallucination_detector detect sample.txt --format markdown -o report.md

    # Analyze text inline
    python -m hallucination_detector detect --text "The Earth is 12,756 km in diameter."

    # Interactive mode
    python -m hallucination_detector interactive

    # Show available strategies
    python -m hallucination_detector strategies
"""

import sys
import os
import argparse

# Ensure we can import the package when run directly
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from hallucination_detector import HallucinationDetector
    from hallucination_detector.utils import Severity
    from hallucination_detector import PlagiarismChecker
else:
    from . import HallucinationDetector
    from .utils import Severity
    from . import PlagiarismChecker


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="hallucination-detector",
        description="""
AI Hallucination Detector
Detect potential AI hallucinations in text using multiple analysis strategies.

Strategies:
  - Claim extraction & verifiability scoring
  - Hallucination pattern analysis
  - URL & citation verification
  - Web-based fact checking (optional)

Example:
  %(prog)s detect article.txt --format json -o report.json
  %(prog)s detect --text "According to a 2024 study by the Institute, 87.3% of users..."
  %(prog)s interactive
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- detect command ---
    detect_parser = subparsers.add_parser(
        "detect", help="Analyze text for hallucinations"
    )
    detect_parser.add_argument(
        "input", nargs="?", default="-",
        help="Input file path (use '-' or omit for stdin)"
    )
    detect_parser.add_argument(
        "--text", "-t", metavar="TEXT",
        help="Analyze text provided directly on the command line"
    )
    detect_parser.add_argument(
        "--format", "-f", choices=["terminal", "json", "markdown", "plain"],
        default="terminal", help="Output format (default: terminal)"
    )
    detect_parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Write output to file instead of stdout"
    )
    detect_parser.add_argument(
        "--offline", action="store_true",
        help="Disable all web-based verification (URL checking, fact checking)"
    )
    detect_parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored output"
    )
    detect_parser.add_argument(
        "--strategies", nargs="+",
        choices=["claim_extraction", "pattern_analysis", "url_verification", "fact_checking"],
        help="Select specific strategies to use (default: all)"
    )
    detect_parser.add_argument(
        "--max-claims", type=int, default=10, metavar="N",
        help="Maximum number of claims to verify via web search (default: 10)"
    )
    detect_parser.add_argument(
        "--url-timeout", type=float, default=10.0, metavar="SECONDS",
        help="Timeout for URL verification requests (default: 10s)"
    )
    detect_parser.add_argument(
        "--min-severity", choices=["info", "low", "medium", "high", "critical"],
        default="low", help="Minimum severity to include in report (default: low)"
    )

    # --- interactive command ---
    subparsers.add_parser(
        "interactive", help="Enter interactive analysis mode"
    )

    # --- strategies command ---
    subparsers.add_parser(
        "strategies", help="List available detection strategies"
    )

    # --- version command ---
    subparsers.add_parser(
        "version", help="Show version information"
    )

    # --- plagiarism command ---
    plag_parser = subparsers.add_parser(
        "plagiarism", help="Check a paper against reference documents (offline, heuristic)"
    )
    plag_parser.add_argument(
        "paper", nargs="?", default="-",
        help="Paper text file (use '-' or omit for stdin)"
    )
    plag_parser.add_argument(
        "--refs", nargs="+", metavar="FILES",
        help="Reference document files to compare against"
    )
    plag_parser.add_argument(
        "--format", "-f", choices=["terminal", "json", "markdown"],
        default="terminal", help="Output format (default: terminal)"
    )
    plag_parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Write output to file instead of stdout"
    )

    return parser


def read_input(args) -> str:
    """Read input text from file, stdin, or --text argument."""
    if args.text:
        return args.text

    if args.input == "-":
        return sys.stdin.read()
    else:
        if not os.path.exists(args.input):
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            return f.read()


def filter_findings_by_severity(findings, min_severity: str):
    """Filter findings to only show those at or above the minimum severity."""
    severity_order = ["info", "low", "medium", "high", "critical"]
    min_idx = severity_order.index(min_severity)
    return [f for f in findings if severity_order.index(f.severity.to_plain().lower()) >= min_idx]


def cmd_detect(args):
    """Execute the detect command."""
    text = read_input(args)

    if not text.strip():
        print("Error: No input text provided.", file=sys.stderr)
        sys.exit(1)

    # Create detector with specified options
    detector = HallucinationDetector(
        verify_online=not args.offline,
        url_timeout=args.url_timeout,
        max_claims_to_verify=args.max_claims,
        enable_strategies=args.strategies,
    )

    # Run analysis
    result = detector.analyze(text)

    # Filter findings by severity
    if args.min_severity != "info":
        result.findings = filter_findings_by_severity(result.findings, args.min_severity)
        # Recalculate score with filtered findings
        result.score = detector.scorer.score(result.findings)

    # Generate output
    use_color = not args.no_color and sys.stdout.isatty()
    if args.format == "terminal":
        output = result.terminal_report(use_color=use_color)
    elif args.format == "json":
        output = result.json_report()
    elif args.format == "markdown":
        output = result.markdown_report()
    elif args.format == "plain":
        output = _plain_report(result)
    else:
        output = result.terminal_report(use_color=False)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        print(f"Report saved to: {args.output}", file=sys.stderr)
    else:
        print(output)


def _plain_report(result):
    """Generate a simple plain-text report."""
    lines = []
    lines.append(f"Hallucination Risk Score: {result.score.overall:.1f}/100 ({result.score.risk_level})")
    lines.append(f"Total Findings: {result.score.total_findings}")
    lines.append(f"Claims Extracted: {len(result.claims)}")
    lines.append("")
    for f in result.findings:
        lines.append(f"[{f.severity.to_plain()}] {f.category}: {f.message}")
        if f.snippet:
            lines.append(f"  Snippet: {f.snippet[:100]}")
        lines.append("")
    return "\n".join(lines)


def cmd_interactive():
    """Run interactive analysis mode."""
    print("=" * 60)
    print("  AI Hallucination Detector — Interactive Mode")
    print("  Type or paste text, then press Enter twice to analyze.")
    print("  Type 'quit' or 'exit' to leave.")
    print("  Type 'help' for commands.")
    print("=" * 60)
    print()

    detector = HallucinationDetector(verify_online=True)

    while True:
        try:
            print("\033[36m> \033[0m", end="", flush=True)
            lines = []
            empty_count = 0
            while True:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 1 and lines:
                        break
                else:
                    empty_count = 0
                lines.append(line)

            text = "\n".join(lines).strip()

            if not text:
                continue
            if text.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if text.lower() == "help":
                print("Commands: type text and press Enter twice to analyze. 'quit' to exit.")
                continue

            result = detector.analyze(text)
            print()
            print(result.terminal_report(use_color=True))
            print()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def cmd_strategies():
    """List available strategies."""
    strategies = [
        ("claim_extraction", "Extract factual claims and score their verifiability", "Always enabled"),
        ("pattern_analysis", "Detect hallucination linguistic patterns (hedging, overconfidence, fake entities)", "Works offline"),
        ("url_verification", "Verify URLs resolve and check for suspicious domain patterns", "Online + offline"),
        ("fact_checking", "Verify claims against web search results", "Requires network"),
    ]
    print("Available Detection Strategies:")
    print("=" * 70)
    for name, desc, note in strategies:
        print(f"  {name:<25} {desc}")
        print(f"  {'':25} Status: {note}")
        print()


def cmd_plagiarism(args):
    """Run plagiarism check (offline, reference-based)."""
    # Read paper
    if args.paper == "-":
        paper = sys.stdin.read()
    else:
        if not os.path.exists(args.paper):
            print(f"Error: File not found: {args.paper}", file=sys.stderr)
            sys.exit(1)
        with open(args.paper, "r", encoding="utf-8") as f:
            paper = f.read()

    refs, ref_names = [], []
    if args.refs:
        for p in args.refs:
            if not os.path.exists(p):
                print(f"Error: Reference file not found: {p}", file=sys.stderr)
                sys.exit(1)
            with open(p, "r", encoding="utf-8") as f:
                refs.append(f.read())
                ref_names.append(os.path.basename(p))

    checker = PlagiarismChecker()
    result = checker.check(paper, refs, ref_names)

    if args.format == "json":
        import json
        out = json.dumps(result, ensure_ascii=False, indent=2)
    elif args.format == "markdown":
        out = _plagiarism_markdown(result)
    else:
        out = _plagiarism_terminal(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8", errors="replace") as f:
            f.write(out)
        print(f"Report saved to: {args.output}", file=sys.stderr)
    else:
        print(out)


def _rate_color(r: float) -> str:
    if r >= 0.5:
        return "\033[31m"  # red
    if r >= 0.3:
        return "\033[33m"  # yellow
    if r >= 0.15:
        return "\033[93m"  # light yellow
    return "\033[32m"  # green


def _plagiarism_terminal(result) -> str:
    RESET = "\033[0m"
    lines = []
    lines.append("=" * 60)
    lines.append("  Paper Plagiarism Check (offline, free trial)")
    lines.append("  ⚠ This is a local heuristic — accuracy not guaranteed.")
    lines.append("=" * 60)
    lines.append("")
    overall = result["overall"]
    self_rate = result["self_rate"]
    lines.append(f"  Total overlap rate (vs references): {_rate_color(overall)}{overall*100:.1f}%{RESET}")
    lines.append(f"  Internal self-repetition rate:      {_rate_color(self_rate)}{self_rate*100:.1f}%{RESET}")
    lines.append(f"  Reference documents: {result['ref_count']}   Paper length: {result['paper_len']} chars")
    lines.append("")
    lines.append("  Per-reference similarity:")
    if result["per_ref"]:
        for pr in result["per_ref"]:
            lines.append(f"    - {pr['name']}: {_rate_color(pr['jaccard'])}{pr['jaccard']*100:.1f}%{RESET}")
    else:
        lines.append("    (no reference documents provided)")
    lines.append("")
    lines.append(f"  Repeated fragments (top {len(result['fragments'])}):")
    if result["fragments"]:
        for i, f in enumerate(result["fragments"], 1):
            snippet = f["text"][:90].replace("\n", " ")
            lines.append(f"    {i}. [{f['score']*100:.0f}% · {f['ref']}] {snippet}")
    else:
        lines.append("    ✓ No highly-overlapping fragments found.")
    return "\n".join(lines)


def _plagiarism_markdown(result) -> str:
    lines = []
    lines.append("# 论文查重报告（免费试用版 · 本地近似比对）")
    lines.append("")
    lines.append("> ⚠️ 本工具为免费试用版，仅做本地近似比对，暂无法保证准确率，不能替代正规查重服务。")
    lines.append("")
    lines.append(f"**总重叠率（参考库）：** {result['overall']*100:.1f}%")
    lines.append(f"**论文自重复率：** {result['self_rate']*100:.1f}%")
    lines.append(f"**参考文档数：** {result['ref_count']}")
    lines.append(f"**待查论文字数：** {result['paper_len']}")
    lines.append("")
    lines.append("## 与各参考文档相似度")
    if result["per_ref"]:
        for pr in result["per_ref"]:
            lines.append(f"- {pr['name']}: {pr['jaccard']*100:.1f}%")
    else:
        lines.append("- 未上传参考文档")
    lines.append("")
    lines.append("## 疑似重复片段")
    if result["fragments"]:
        for i, f in enumerate(result["fragments"], 1):
            lines.append(f"{i}. **[{f['score']*100:.0f}% · {f['ref']}]** {f['text'][:180]}")
    else:
        lines.append("- 未发现高度重叠片段")
    lines.append("")
    lines.append("---")
    lines.append("*本地计算，文件未上传服务器。Ethan X 工作室出品。*")
    return "\n".join(lines)


def cmd_version():
    """Show version information."""
    from hallucination_detector import __version__, __author__, __license__
    print(f"AI Hallucination Detector v{__version__}")
    print(f"Author: {__author__}")
    print(f"License: {__license__}")
    print(f"Python: {sys.version}")
    print()
    print("A multi-strategy toolkit for detecting AI hallucinations in text.")
    print("https://github.com/ethanxu/ai-hallucination-detector")


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "interactive":
        cmd_interactive()
    elif args.command == "strategies":
        cmd_strategies()
    elif args.command == "version":
        cmd_version()
    elif args.command == "plagiarism":
        cmd_plagiarism(args)


if __name__ == "__main__":
    main()

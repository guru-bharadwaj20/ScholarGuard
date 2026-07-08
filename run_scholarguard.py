#!/usr/bin/env python
"""ScholarGuard — the ONE command to analyze a scientific paper PDF.

Runs the full unified pipeline (copy-move, cross-figure reuse, AI-generation,
and text/claim-consistency) over every figure in a PDF and prints a clean risk
summary, plus the path to the full JSON + Markdown report.

Usage:
    python run_scholarguard.py --pdf path/to/paper.pdf
    python run_scholarguard.py --pdf paper.pdf --config src/config/config.yaml \
        --output-dir outputs/stage6_results
"""

from __future__ import annotations

import argparse
import logging
import sys

# Make console output robust on Windows (cp1252) terminals — never let a
# non-ASCII character in a caption or warning crash the summary print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - older Pythons
        pass


def _setup_logging(level: str) -> None:
    """Send ScholarGuard's INFO/WARNING logs to the console, cleanly formatted."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root = logging.getLogger("scholarguard")
    root.handlers[:] = [handler]  # replace the library NullHandler
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False


# ASCII risk markers (portable across Windows/Unix terminals).
_CATEGORY_ICON = {"low": "[ LOW  ]", "moderate": "[ MOD  ]", "high": "[ HIGH ]",
                  "critical": "[ CRIT ]", "unknown": "[  ?   ]"}


def _print_summary(report: dict) -> None:
    print("\n" + "=" * 62)
    print(f"  ScholarGuard report — {report['paper']['filename']}")
    print("=" * 62)

    if report["status"] == "failed":
        print(f"  STATUS: FAILED — {report.get('error')}")
        print("=" * 62)
        return

    if report["pipeline_warnings"]:
        print("  Pipeline notes (degraded / skipped):")
        for w in report["pipeline_warnings"]:
            print(f"    - {w}")

    n = report["paper"]["n_figures"]
    if n == 0:
        print("  No figures were extracted from this PDF.")
    else:
        print(f"  Figures analyzed: {n}")
        for fig in report["figures"]:
            risk = fig["risk"]
            icon = _CATEGORY_ICON.get(risk["category"], "⚪")
            print(f"    {icon} {fig['figure']:<28} {risk['score']:>5}/100")

    overall = report["overall_risk"]
    icon = _CATEGORY_ICON.get(overall.get("category", "unknown"), "⚪")
    print("-" * 62)
    print(f"  {icon} OVERALL PAPER RISK: {overall.get('category', 'n/a').upper()} "
          f"({overall.get('score', 0)}/100)")
    print("=" * 62)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="ScholarGuard — scientific figure integrity pipeline")
    parser.add_argument("--pdf", required=True, help="paper PDF to analyze")
    parser.add_argument("--config", default=None,
                        help="config.yaml path (default: src/config/config.yaml)")
    parser.add_argument("--output-dir", default=None,
                        help="where to write reports (default: config's output_dir)")
    args = parser.parse_args(argv)

    # Determine log level from config if available, else INFO.
    level = "INFO"
    try:
        from src.config.settings import load_settings
        level = load_settings(args.config).log_level if args.config \
            else load_settings().log_level
    except Exception:  # noqa: BLE001 - fall back to INFO; run_pipeline re-validates
        pass
    _setup_logging(level)

    from src.pipeline.orchestrator import run_pipeline
    report = run_pipeline(args.pdf, config_path=args.config,
                          output_dir=args.output_dir)

    _print_summary(report)
    paths = report.get("report_paths")
    if paths:
        print(f"\n  Full report : {paths['json']}")
        print(f"  Readable    : {paths['markdown']}")

    # Exit code communicates the headline result to shell callers / CI.
    if report["status"] == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

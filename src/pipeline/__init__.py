"""Stage 6 — the unified ScholarGuard pipeline.

* :mod:`orchestrator` — the single entry point (``run_pipeline``).
* :mod:`risk_scorer`  — combines all detector signals into risk scores.
* :mod:`report_builder` — renders the final JSON + Markdown report.
"""

from src.pipeline.orchestrator import run_pipeline

__all__ = ["run_pipeline"]

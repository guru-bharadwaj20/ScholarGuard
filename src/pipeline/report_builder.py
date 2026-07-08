"""Render the unified integrity report as structured JSON + Markdown.

The JSON is the machine-readable source of truth (consumed by Stage 7's
evaluation harness); the Markdown is a human-readable summary for a reviewer.
Both are written to the configured output directory.
"""

from __future__ import annotations

import datetime
import json
import os

import numpy as np


def _json_safe(obj):
    """Recursively drop numpy arrays and coerce numpy scalars for JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()
                if not isinstance(v, np.ndarray)}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def build_report(
    pdf_path: str,
    status: str,
    figures: list[dict],
    paper_risk: dict,
    warnings: list[str],
    sections_found: list[str] | None = None,
    error: str | None = None,
) -> dict:
    """Assemble the final structured report dict.

    ``status`` is "completed", "completed_no_figures", or "failed".
    """
    return _json_safe({
        "schema_version": "scholarguard/stage6/1.0",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "paper": {
            "path": pdf_path,
            "filename": os.path.basename(pdf_path),
            "sections_found": sections_found or [],
            "n_figures": len(figures),
        },
        "status": status,
        "error": error,
        "overall_risk": paper_risk,
        "figures": figures,
        "pipeline_warnings": warnings,
        "disclaimer": ("All findings are leads for human review, not proof of "
                       "misconduct. The visual lane/panel count is an approximate "
                       "screening heuristic."),
    })


def render_markdown(report: dict) -> str:
    """Render a concise, human-readable Markdown summary of the report."""
    paper = report["paper"]
    risk = report["overall_risk"]
    lines: list[str] = []
    lines.append(f"# ScholarGuard Integrity Report — {paper['filename']}")
    lines.append("")
    lines.append(f"- **Generated:** {report['generated_at']}")
    lines.append(f"- **Status:** {report['status']}")
    if report.get("error"):
        lines.append(f"- **Error:** {report['error']}")

    if report["status"] != "failed":
        cat = str(risk.get("category", "n/a")).upper()
        lines.append(f"- **Overall paper risk:** **{cat}** "
                     f"(score {risk.get('score', 0)}/100, "
                     f"{paper['n_figures']} figure(s))")
    lines.append("")

    if report["pipeline_warnings"]:
        lines.append("## ⚠ Pipeline notes (degraded / skipped steps)")
        for w in report["pipeline_warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    if not report["figures"]:
        lines.append("_No figures were extracted from this PDF._")
        lines.append("")

    for fig in report["figures"]:
        risk_f = fig.get("risk", {})
        cat = str(risk_f.get("category", "n/a")).upper()
        lines.append(f"## {fig['figure']} — risk {cat} "
                     f"(score {risk_f.get('score', 0)}/100)")
        if fig.get("caption"):
            cap = fig["caption"]
            lines.append(f"> {cap[:200]}{'…' if len(cap) > 200 else ''}")
        lines.append("")
        lines.append("| Detector | Status | Points | Finding |")
        lines.append("|---|---|---:|---|")
        for row in risk_f.get("breakdown", []):
            note = row["note"].replace("|", "\\|")
            lines.append(f"| {row['detector']} | {row['status']} | "
                         f"{row['points']}/{row['max_points']} | {note} |")
        lines.append("")

    lines.append("---")
    lines.append(f"_{report['disclaimer']}_")
    return "\n".join(lines)


def save_report(report: dict, output_dir: str) -> dict:
    """Write ``<stem>_report.json`` and ``<stem>_report.md``; return their paths."""
    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(report["paper"]["filename"])[0]
    json_path = os.path.join(output_dir, f"{stem}_report.json")
    md_path = os.path.join(output_dir, f"{stem}_report.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    return {"json": json_path, "markdown": md_path}

"""The report JSON is the contract every consumer reads, and had no tests.

server/main.py rewrites it for the browser, web/lib/api.ts types it, and
src/evaluation reads it back for every metric. A silent change to its shape
breaks all three, so pin the shape, the numpy coercion, and the Markdown.
"""

import json
import os

import numpy as np
import pytest

from src.pipeline import report_builder


@pytest.fixture
def figure() -> dict:
    return {
        "figure": "Figure 1",
        "figure_num": 1,
        "image_path": "/tmp/fig1.png",
        "caption": "A caption with a | pipe in it",
        "detectors": {"copy_move": {"status": "ok", "forged": True,
                                    "confidence": 0.71}},
        "risk": {
            "score": 30.0, "category": "moderate",
            "n_corroborating_signals": 1, "fraud_probability": 0.4,
            "breakdown": [{"detector": "copy_move", "status": "ok",
                           "max_points": 25, "points": 17.75, "fired": True,
                           "note": "duplicated regions | within figure"}],
        },
    }


def _build(**kw):
    base = dict(pdf_path="/papers/paper.pdf", status="completed", figures=[],
                paper_risk={"score": 0.0, "category": "low"}, warnings=[])
    base.update(kw)
    return report_builder.build_report(**base)


# ----------------------------------------------------------------- structure
def test_report_has_the_documented_top_level_shape(figure):
    report = _build(figures=[figure],
                    paper_risk={"score": 30.0, "category": "moderate"},
                    sections_found=["Methods", "Results"])
    assert set(report) == {
        "schema_version", "generated_at", "paper", "status", "error",
        "overall_risk", "figures", "pipeline_warnings", "disclaimer"}
    assert report["schema_version"] == "scholarguard/stage6/1.0"
    assert report["paper"]["filename"] == "paper.pdf"
    assert report["paper"]["n_figures"] == 1
    assert report["paper"]["sections_found"] == ["Methods", "Results"]
    assert "leads for human review" in report["disclaimer"]


def test_error_and_sections_default_cleanly():
    report = _build(status="failed", error="could not read the PDF")
    assert report["error"] == "could not read the PDF"
    assert report["paper"]["sections_found"] == []
    assert report["paper"]["n_figures"] == 0


# ------------------------------------------------------------ numpy handling
def test_numpy_scalars_are_coerced_and_arrays_dropped():
    """Detectors return numpy types; json.dump cannot serialise them."""
    report = _build(figures=[{
        "figure": "Figure 1",
        "risk": {"score": np.float32(42.5), "category": "moderate",
                 "breakdown": []},
        "detectors": {"copy_move": {
            "status": "ok",
            "forged": np.bool_(True),
            "n_regions": np.int64(3),
            "confidence": np.float64(0.8),
            "mask": np.zeros((4, 4), np.uint8),   # must not reach the JSON
        }},
    }])
    detector = report["figures"][0]["detectors"]["copy_move"]
    assert detector["forged"] is True and isinstance(detector["forged"], bool)
    assert detector["n_regions"] == 3 and isinstance(detector["n_regions"], int)
    assert isinstance(detector["confidence"], float)
    assert "mask" not in detector, "a numpy array leaked into the report"
    assert isinstance(report["figures"][0]["risk"]["score"], float)
    json.dumps(report)          # the real requirement


def test_nested_arrays_inside_lists_are_handled():
    report = _build(figures=[{"figure": "F", "risk": {"breakdown": []},
                              "detectors": {},
                              "regions": [{"bbox": np.int32(4)}]}])
    json.dumps(report)


# ---------------------------------------------------------------- markdown
def test_markdown_reports_status_risk_and_every_detector_row(figure):
    report = _build(figures=[figure],
                    paper_risk={"score": 30.0, "category": "moderate"},
                    warnings=["claim-consistency skipped: no API key"])
    md = report_builder.render_markdown(report)

    assert "# ScholarGuard Integrity Report — paper.pdf" in md
    assert "MODERATE" in md
    assert "claim-consistency skipped: no API key" in md
    assert "| copy_move | ok | 17.75/25 |" in md
    # Pipes inside free text must be escaped or they break the table.
    assert r"duplicated regions \| within figure" in md
    assert report["disclaimer"] in md


def test_markdown_says_so_when_there_are_no_figures():
    md = report_builder.render_markdown(_build(status="completed_no_figures"))
    assert "_No figures were extracted from this PDF._" in md


def test_markdown_of_a_failed_report_shows_the_error_not_a_risk():
    md = report_builder.render_markdown(
        _build(status="failed", error="corrupt PDF"))
    assert "**Error:** corrupt PDF" in md
    assert "Overall paper risk" not in md


def test_long_captions_are_truncated_with_an_ellipsis():
    figure = {"figure": "Figure 1", "caption": "x" * 500,
              "risk": {"score": 0, "category": "low", "breakdown": []},
              "detectors": {}}
    md = report_builder.render_markdown(_build(figures=[figure]))
    assert "…" in md
    assert "x" * 201 not in md


# ------------------------------------------------------------------- saving
def test_save_report_writes_both_formats_and_returns_their_paths(tmp_path,
                                                                 figure):
    report = _build(figures=[figure],
                    paper_risk={"score": 30.0, "category": "moderate"})
    paths = report_builder.save_report(report, str(tmp_path / "nested" / "out"))

    assert os.path.basename(paths["json"]) == "paper_report.json"
    assert os.path.basename(paths["markdown"]) == "paper_report.md"
    with open(paths["json"], encoding="utf-8") as fh:
        assert json.load(fh)["paper"]["filename"] == "paper.pdf"
    assert "ScholarGuard Integrity Report" in \
        open(paths["markdown"], encoding="utf-8").read()


def test_save_report_handles_a_non_ascii_paper_name(tmp_path):
    report = _build(pdf_path="/papers/étude_Müller.pdf")
    paths = report_builder.save_report(report, str(tmp_path / "out"))
    assert os.path.isfile(paths["json"])
    with open(paths["json"], encoding="utf-8") as fh:
        assert json.load(fh)["paper"]["filename"] == "étude_Müller.pdf"

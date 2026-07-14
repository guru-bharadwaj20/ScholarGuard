"""End-to-end tests for the Stage 6 orchestrator.

The full pipeline runs on the synthetic sample paper. The LLM is mocked so CI
never spends API credits. Settings/config are loaded from the real config.yaml.
"""

import json
import os

import pytest

from src.pipeline.orchestrator import run_pipeline
from src.utils.sample_paper import generate_sample_paper


class FakeLLM:
    """Returns the (overstated) 12-lane claim from the sample paper's caption."""

    def extract_json(self, prompt, schema, system=None, max_tokens=2048):
        return {
            "claimed_description": "Western blot across 12 conditions",
            "claimed_n": 12, "claimed_panel_count": 12, "panel_count_kind": "lanes",
            "claimed_stats": [], "error_bar_description": "mean +/- SEM",
        }


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("papers") / "paper.pdf")
    return generate_sample_paper(path, seed=7)


@pytest.fixture(scope="module")
def report(sample_pdf, tmp_path_factory):
    out = str(tmp_path_factory.mktemp("stage6_out"))
    return run_pipeline(sample_pdf, output_dir=out, llm_client=FakeLLM())


def test_pipeline_produces_wellformed_report(report):
    assert report["status"] == "completed"
    assert report["schema_version"].startswith("scholarguard/stage6")
    assert report["paper"]["n_figures"] == 2
    assert "overall_risk" in report and "category" in report["overall_risk"]
    assert report["overall_risk"]["category"] in {"low", "moderate", "high", "critical"}


def test_every_figure_has_all_detector_slots(report):
    for fig in report["figures"]:
        assert set(fig["detectors"]) == {"copy_move", "cross_figure", "splice",
                                         "ai_generation", "claim_consistency"}
        assert "risk" in fig and "breakdown" in fig["risk"]
        # Each detector slot has a status.
        for det in fig["detectors"].values():
            assert "status" in det


def test_claim_mismatch_is_captured(report):
    """Figure 1's image (~4 lanes) vs the mocked 12-lane claim is flagged."""
    fig1 = report["figures"][0]
    cc = fig1["detectors"]["claim_consistency"]
    assert cc["status"] == "ok"
    assert cc["consistent"] is False
    assert any("12 lanes" in m for m in cc["mismatches"])
    # And it contributes points to the figure's risk breakdown.
    cc_row = next(b for b in fig1["risk"]["breakdown"]
                  if b["detector"] == "claim_consistency")
    assert cc_row["points"] > 0


def test_report_files_written(report):
    paths = report["report_paths"]
    assert os.path.isfile(paths["json"])
    assert os.path.isfile(paths["markdown"])
    # JSON round-trips and matches the returned report's headline fields.
    with open(paths["json"], encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk["status"] == "completed"
    assert on_disk["overall_risk"]["category"] == report["overall_risk"]["category"]
    # Markdown mentions the risk and at least one figure.
    md = open(paths["markdown"], encoding="utf-8").read()
    assert "Overall paper risk" in md
    assert "Figure 1" in md


def test_ai_weights_missing_is_reported_not_fatal(report):
    """With no classifier weights on disk, AI runs forensics-only and says so."""
    # Every figure's AI detector ran (forensics only).
    for fig in report["figures"]:
        ai = fig["detectors"]["ai_generation"]
        assert ai["status"] == "ok"
        assert ai["classifier_used"] is False
    assert any("FORENSICS-ONLY" in w for w in report["pipeline_warnings"])

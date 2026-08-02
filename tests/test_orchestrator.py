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


def test_ai_weights_state_is_reported_accurately(report):
    """The report's classifier claim must match what the detector actually did.

    This used to assert forensics-only unconditionally, which quietly depended
    on no one having trained a checkpoint into the configured path: the moment
    one existed the test failed, even though the pipeline was behaving
    correctly. What actually matters is that the two agree — the AI detector
    ran, and ``classifier_used`` plus the FORENSICS-ONLY warning both reflect
    whether the configured weights are really there. The inverse case (report
    says forensics-only while the default checkpoint drives the verdict) is a
    bug this pins down; ``test_missing_stage4_weights_degrades_gracefully``
    covers the missing-weights path explicitly.
    """
    from src.config.settings import load_settings

    weights_path = load_settings().ai_weights_path
    weights_present = bool(weights_path) and os.path.isfile(weights_path)

    for fig in report["figures"]:
        ai = fig["detectors"]["ai_generation"]
        assert ai["status"] == "ok"
        assert ai["classifier_used"] is weights_present
        # The score itself is recorded, not just that it ran — offline
        # recalibration reads it, and with weights loaded it is most of the
        # verdict (0.6*p_ai + 0.4*forensic).
        if weights_present:
            assert isinstance(ai["classifier_score"], float)
            assert 0.0 <= ai["classifier_score"] <= 1.0
        else:
            assert ai["classifier_score"] is None

    warned = any("FORENSICS-ONLY" in w for w in report["pipeline_warnings"])
    assert warned is not weights_present


def test_inert_ai_thresholds_are_reported_not_ignored(report):
    """Absolute forensic bands are overwritten by compression conditioning.

    config.yaml ships both `forensic_suspicious_threshold`/`forensic_ai_threshold`
    AND `condition_on_compression: true`, and the detector derives its bands from
    the per-stratum baseline in that case -- so editing those two keys changes
    nothing. That used to be silent. The pipeline must now say so.
    """
    from src.config.settings import load_settings

    settings = load_settings()
    conflict = settings.ai_threshold_conflict()
    assert conflict is not None, "shipped config has both set; expected a notice"
    assert conflict in report["pipeline_warnings"]


def test_no_inert_threshold_notice_when_conditioning_is_off():
    """With conditioning off the absolute bands DO apply, so there is no notice."""
    from src.config.settings import Settings

    off = Settings(raw={"detectors": {"ai_generation": {
        "condition_on_compression": False,
        "forensic_suspicious_threshold": 0.57,
    }}})
    assert off.ai_threshold_conflict() is None
    # ...and an empty dict is the detector's documented "conditioning disabled"
    # signal, which is NOT the same as None ("use the built-in defaults").
    assert off.ai_compression_baselines() == {}


def test_unconfigured_absolute_bands_produce_no_notice():
    """Only an operator who actually set the keys needs telling they are inert."""
    from src.config.settings import Settings

    settings = Settings(raw={"detectors": {"ai_generation": {}}})
    assert settings.ai_threshold_conflict() is None
    assert settings.ai_compression_baselines() is None

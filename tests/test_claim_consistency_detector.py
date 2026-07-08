"""Unit tests for the Stage 5 claim-consistency detector.

A synthetic paper PDF is generated once per session (offline, no network).
LLM calls are mocked so automated tests never spend API credits; the single
end-to-end test that can hit the real API is gated behind
``SCHOLARGUARD_LIVE_LLM=1``.
"""

import os

import pytest

from src.detectors.claim_consistency_detector import ClaimConsistencyDetector
from src.nlp.claim_extractor import EMPTY_CLAIMS, extract_claims
from src.nlp.consistency_checker import check_consistency
from src.nlp.pdf_parser import (
    extract_captions,
    get_results_context,
    parse_paper,
    split_sections,
)
from src.utils.sample_paper import generate_sample_paper


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    """A synthetic paper PDF with 2 figures; Fig 1 has a claim/image mismatch."""
    path = str(tmp_path_factory.mktemp("papers") / "paper.pdf")
    return generate_sample_paper(path, seed=7)


class FakeLLMClient:
    """Stand-in for LLMClient that returns canned claims — no API calls."""

    def __init__(self, claims: dict):
        self._claims = claims
        self.calls = 0

    def extract_json(self, prompt, schema, system=None, max_tokens=2048):
        self.calls += 1
        return self._claims


# ---------------------------------------------------------------- test 1
def test_pdf_parser_extracts_sections_and_figures(sample_pdf):
    parsed = parse_paper(sample_pdf)
    # Sections
    assert "Methods" in parsed["sections"]
    assert "Results" in parsed["sections"]
    assert "n = 6" in parsed["sections"]["Methods"] or "n = 6" in parsed["full_text"]
    # At least one figure with a caption and an extracted image on disk
    assert len(parsed["figures"]) >= 1
    fig1 = parsed["figures"][0]
    assert fig1["figure_num"] == 1
    assert "Protein X" in fig1["caption"]
    assert fig1["image_path"] and os.path.isfile(fig1["image_path"])
    # Results context for the figure should be non-empty (inline "Figure 1" refs)
    assert len(fig1["results_context"]) > 0


def test_section_and_caption_helpers():
    text = ("Methods\nWe did things with n = 3 replicates.\n\n"
            "Results\nAs shown in Figure 2, expression rose.\n\n"
            "Figure 2. A blot showing 5 lanes of protein.\n")
    sections = split_sections(text)
    assert "Methods" in sections and "Results" in sections
    caps = extract_captions(text)
    assert caps[2].startswith("A blot showing 5 lanes")
    ctx = get_results_context(text, 2)
    assert "expression rose" in ctx


# ---------------------------------------------------------------- test 2
def test_claim_extractor_returns_valid_structured_json():
    """With a mocked LLM, extract_claims returns the documented schema shape."""
    canned = {
        "claimed_description": "Western blot of Protein X across 12 conditions",
        "claimed_n": 12,
        "claimed_panel_count": 12,
        "panel_count_kind": "lanes",
        "claimed_stats": [{"kind": "p_value", "value": 0.001, "raw_text": "p < 0.001"}],
        "error_bar_description": "mean +/- SEM",
    }
    fake = FakeLLMClient(canned)
    claims = extract_claims("Figure 1. Western blot ... 12 lanes ...",
                            "Densitometry revealed a 2.5-fold increase (p<0.001).",
                            "Figure 1", client=fake)
    assert fake.calls == 1
    assert set(claims) >= set(EMPTY_CLAIMS)
    assert claims["claimed_n"] == 12
    assert claims["claimed_panel_count"] == 12
    assert claims["claimed_stats"][0]["kind"] == "p_value"


def test_claim_extractor_no_text_skips_llm():
    """Empty caption + context returns EMPTY_CLAIMS without calling the LLM."""
    fake = FakeLLMClient({})
    claims = extract_claims("", "", "Figure 9", client=fake)
    assert fake.calls == 0
    assert claims == EMPTY_CLAIMS


# ---------------------------------------------------------------- test 3
def test_consistency_checker_flags_count_mismatch(sample_pdf):
    """A claimed panel count far from the observed visual count is flagged."""
    parsed = parse_paper(sample_pdf)
    fig1 = parsed["figures"][0]  # image shows ~4 lanes
    claims = {**EMPTY_CLAIMS, "claimed_panel_count": 12, "panel_count_kind": "lanes"}

    result = check_consistency(claims, fig1["image_path"], prior_detector_flags={})
    assert result["consistent"] is False
    assert result["confidence"] > 0.0
    assert any("12 lanes" in m for m in result["mismatches"])


def test_consistency_checker_prior_flag_raises_confidence():
    """A Stage 2/3/4 flag alone makes the figure inconsistent (strong prior)."""
    claims = dict(EMPTY_CLAIMS)
    result = check_consistency(claims, None,
                               prior_detector_flags={"ai_generated": True})
    assert result["consistent"] is False
    assert result["confidence"] >= 0.8
    assert any("AI-generated" in m for m in result["mismatches"])


def test_consistency_checker_clean_case_is_consistent(sample_pdf):
    """Matching claim (4 lanes) vs a ~4-lane image reports consistent."""
    parsed = parse_paper(sample_pdf)
    fig1 = parsed["figures"][0]
    claims = {**EMPTY_CLAIMS, "claimed_panel_count": 4, "panel_count_kind": "lanes"}
    result = check_consistency(claims, fig1["image_path"], prior_detector_flags={})
    assert result["consistent"] is True
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------- test 4
def test_analyze_paper_end_to_end_mocked_llm(sample_pdf):
    """Full pipeline with a mocked LLM: well-formed report, mismatch caught."""
    # The mock returns the (overstated) 12-lane claim for every figure.
    fake = FakeLLMClient({
        "claimed_description": "Western blot across 12 conditions",
        "claimed_n": 12, "claimed_panel_count": 12, "panel_count_kind": "lanes",
        "claimed_stats": [], "error_bar_description": "mean +/- SEM",
    })
    detector = ClaimConsistencyDetector(llm_client=fake)
    report = detector.analyze_paper(sample_pdf)

    # Well-formed structure
    assert report["n_figures"] >= 1
    assert "paper_summary" in report
    assert report["paper_summary"]["overall_risk"] in {"low", "medium", "high"}
    for fig in report["figures"]:
        assert set(fig) >= {"figure", "claims", "image_forensics",
                            "consistency", "risk_level", "risk_reasons"}
        assert fig["risk_level"] in {"low", "medium", "high"}

    # Figure 1's image (~4 lanes) vs the mocked 12-lane claim => mismatch caught
    fig1 = report["figures"][0]
    assert fig1["consistency"]["consistent"] is False
    assert any("12 lanes" in m for m in fig1["consistency"]["mismatches"])
    # And that pushes it above low risk.
    assert fig1["risk_level"] in {"medium", "high"}


@pytest.mark.skipif(os.environ.get("SCHOLARGUARD_LIVE_LLM") != "1",
                    reason="set SCHOLARGUARD_LIVE_LLM=1 to run the real API call")
def test_analyze_paper_live_llm(sample_pdf):
    """Optional: real Claude API call (needs ANTHROPIC_API_KEY). Gated."""
    report = ClaimConsistencyDetector().analyze_paper(sample_pdf)
    assert report["n_figures"] >= 1
    fig1 = report["figures"][0]
    # The real model should extract the 12-lane claim from the caption.
    assert fig1["claims"]["claimed_panel_count"] in (12, None)

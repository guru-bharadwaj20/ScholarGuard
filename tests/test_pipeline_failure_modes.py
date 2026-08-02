"""Graceful-degradation tests for the Stage 6 pipeline.

Every failure mode must produce a well-formed report and a clear note — never
a crash or a raw stack trace, and never a silent omission.

To keep these fast, most use a temp config.yaml that disables the slow
Stage 3 cross-figure detector (it loads a CNN); the failure modes under test
are independent of it.
"""

import json
import os

import fitz  # PyMuPDF
import yaml

from src.pipeline.orchestrator import run_pipeline
from src.utils.sample_paper import generate_sample_paper


def _write_config(tmp_path, **overrides) -> str:
    """Write a minimal config.yaml (cross-figure off for speed) + overrides."""
    from src.config.settings import load_settings
    base = load_settings().raw  # start from the real defaults
    base["detectors"]["cross_figure"]["enabled"] = False
    for section, values in overrides.items():
        base.setdefault(section, {})
        base[section].update(values)
    path = str(tmp_path / "config.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(base, fh)
    return path


class FakeLLM:
    def extract_json(self, prompt, schema, system=None, max_tokens=2048):
        return {"claimed_description": None, "claimed_n": None,
                "claimed_panel_count": None, "panel_count_kind": None,
                "claimed_stats": [], "error_bar_description": None}


# ---------------------------------------------------------------- test 1
def test_missing_stage4_weights_degrades_gracefully(tmp_path):
    """No classifier weights -> pipeline completes, AI runs forensics-only."""
    pdf = generate_sample_paper(str(tmp_path / "paper.pdf"), seed=7)
    cfg = _write_config(tmp_path, detectors={
        **{},  # keep base detectors dict from _write_config
    })
    # Point weights at a nonexistent path explicitly.
    with open(cfg, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    raw["detectors"]["ai_generation"]["weights_path"] = "no/such/weights.pt"
    with open(cfg, "w", encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh)

    report = run_pipeline(pdf, config_path=cfg,
                          output_dir=str(tmp_path / "out"), llm_client=FakeLLM())
    assert report["status"] == "completed"
    assert any("FORENSICS-ONLY" in w for w in report["pipeline_warnings"])
    for fig in report["figures"]:
        ai = fig["detectors"]["ai_generation"]
        assert ai["status"] == "ok" and ai["classifier_used"] is False


# ---------------------------------------------------------------- test 2
def test_missing_api_key_skips_claim_consistency(tmp_path, monkeypatch):
    """No ANTHROPIC_API_KEY -> claim consistency skipped, clearly noted."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pdf = generate_sample_paper(str(tmp_path / "paper.pdf"), seed=7)
    cfg = _write_config(tmp_path)

    # llm_client defaults to "auto" -> LLMClient() raises (no key) -> skip.
    report = run_pipeline(pdf, config_path=cfg, output_dir=str(tmp_path / "out"))
    assert report["status"] == "completed"
    assert any("ANTHROPIC_API_KEY" in w for w in report["pipeline_warnings"])
    for fig in report["figures"]:
        assert fig["detectors"]["claim_consistency"]["status"] == "skipped"


# ---------------------------------------------------------------- test 3
def test_corrupt_pdf_fails_gracefully(tmp_path):
    """A corrupt/unreadable PDF -> status 'failed' with a clear message, no crash."""
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not really a pdf \x00\x01\x02 garbage")
    cfg = _write_config(tmp_path)

    report = run_pipeline(str(bad), config_path=cfg, output_dir=str(tmp_path / "out"))
    assert report["status"] == "failed"
    assert report["error"] and "parse" in report["error"].lower()
    # A report file is still written so the failure is auditable, and it
    # records the same failure the returned dict does.
    report_path = os.path.join(str(tmp_path / "out"), "corrupt_report.json")
    assert os.path.isfile(report_path)
    with open(report_path, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk["status"] == "failed"
    assert on_disk["error"] == report["error"]


def test_nonexistent_pdf_fails_gracefully(tmp_path):
    cfg = _write_config(tmp_path)
    report = run_pipeline(str(tmp_path / "does_not_exist.pdf"), config_path=cfg,
                          output_dir=str(tmp_path / "out"))
    assert report["status"] == "failed"
    assert "not found" in report["error"].lower()


# ---------------------------------------------------------------- test 4
def test_zero_figures_completes_with_note(tmp_path):
    """A text-only PDF (no figures) -> completes with a 'no figures' note."""
    text_pdf = tmp_path / "text_only.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(56, 56, 500, 700),
                        "Abstract\nThis paper has text but no figures at all.\n"
                        "Methods\nWe did things.\nResults\nNothing to show here.",
                        fontsize=11)
    doc.save(str(text_pdf))
    doc.close()
    cfg = _write_config(tmp_path)

    report = run_pipeline(str(text_pdf), config_path=cfg,
                          output_dir=str(tmp_path / "out"), llm_client=FakeLLM())
    assert report["status"] == "completed_no_figures"
    assert report["paper"]["n_figures"] == 0
    assert any("no figures" in w.lower() for w in report["pipeline_warnings"])
    # Overall risk is defined (low) even with nothing to score.
    assert report["overall_risk"]["category"] == "low"


# ---------------------------------------------------------------- extra
def test_one_detector_error_does_not_abort_others(tmp_path, monkeypatch):
    """If copy-move raises on a figure, other detectors still run and report."""
    pdf = generate_sample_paper(str(tmp_path / "paper.pdf"), seed=7)
    cfg = _write_config(tmp_path)

    # Force the Stage 2 detector to raise inside the pipeline.
    import src.pipeline.orchestrator as orch

    def boom(self, image_path, image_flags):
        try:
            raise RuntimeError("simulated copy-move failure")
        except Exception as exc:  # mimic the real isolation wrapper
            return {"status": "error", "error": str(exc)}

    monkeypatch.setattr(orch.Pipeline, "_run_copy_move", boom)

    report = run_pipeline(pdf, config_path=cfg, output_dir=str(tmp_path / "out"),
                          llm_client=FakeLLM())
    assert report["status"] == "completed"
    for fig in report["figures"]:
        assert fig["detectors"]["copy_move"]["status"] == "error"
        # AI-generation still ran despite copy-move erroring.
        assert fig["detectors"]["ai_generation"]["status"] == "ok"

"""Sanity tests for the Stage 7 evaluation scripts themselves.

These verify the *evaluation harness* (loading, metric math, resume) — not the
detectors. The metric tests use constructed confusion inputs so the math is
checked independently of any pipeline run.
"""

import json

import pytest

from src.evaluation import benchmark_runner, metrics
from src.evaluation.ground_truth_loader import (
    GroundTruthError,
    load_evaluation_set,
)


# ---------------------------------------------------------------- loader
def test_ground_truth_loader_parses_and_flags_missing_pdf(tmp_path):
    present = tmp_path / "real.pdf"
    present.write_bytes(b"%PDF-1.4 dummy")
    labels = {
        "dataset_name": "unit",
        "papers": [
            {"paper_id": "p_present", "pdf_path": str(present),
             "is_fraudulent": True, "label_confidence": "confirmed",
             "figures": [{"figure_num": 1, "fraud_type": "copy_move"}]},
            {"paper_id": "p_missing", "pdf_path": str(tmp_path / "gone.pdf"),
             "is_fraudulent": False,
             "figures": [{"figure_num": 1, "fraud_type": "none"}]},
        ],
    }
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(labels), encoding="utf-8")

    es = load_evaluation_set(str(labels_path))
    by_id = {p["paper_id"]: p for p in es["papers"]}
    assert by_id["p_present"]["pdf_exists"] is True
    assert by_id["p_missing"]["pdf_exists"] is False
    assert any("p_missing" in w for w in es["warnings"])
    # A missing PDF is a warning, not a crash — both papers are still loaded.
    assert len(es["papers"]) == 2


def test_ground_truth_loader_rejects_bad_fraud_type(tmp_path):
    labels = {"papers": [{"paper_id": "x", "pdf_path": "x.pdf",
                          "is_fraudulent": True,
                          "figures": [{"figure_num": 1, "fraud_type": "bogus"}]}]}
    p = tmp_path / "labels.json"
    p.write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(GroundTruthError):
        load_evaluation_set(str(p))


# ---------------------------------------------------------------- metrics
def test_confusion_and_binary_metrics_math():
    y_true = [True, True, False, False, True]
    y_pred = [True, False, False, True, True]
    counts = metrics.confusion_counts(y_true, y_pred)
    assert counts == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}

    m = metrics.binary_metrics(counts)
    assert m["precision"] == pytest.approx(2 / 3, abs=1e-3)   # 2/(2+1)
    assert m["recall"] == pytest.approx(2 / 3, abs=1e-3)      # 2/(2+1)
    assert m["f1"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["false_positive_rate"] == pytest.approx(0.5)     # 1/(1+1)
    assert m["accuracy"] == pytest.approx(3 / 5)


def test_binary_metrics_handles_undefined_ratios():
    # No positives predicted or present -> precision undefined (None), not 0.
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 5}
    m = metrics.binary_metrics(counts)
    assert m["precision"] is None
    assert m["false_positive_rate"] == 0.0  # 0/(0+5)


def test_threshold_sweep_monotonic_recall():
    y_true = [True, True, False, False]
    scores = [80.0, 40.0, 30.0, 10.0]
    sweep = metrics.score_threshold_sweep(y_true, scores, thresholds=[0, 35, 50, 90])
    recalls = [r["metrics"]["recall"] for r in sweep]
    # Raising the threshold can only lower (or hold) recall.
    clean = [x for x in recalls if x is not None]
    assert clean == sorted(clean, reverse=True)


# ---------------------------------------------------------------- resume
def test_benchmark_resume_skips_completed(tmp_path, monkeypatch):
    """A pre-seeded result must not be re-run; only the pending paper runs."""
    calls = []

    def fake_run_pipeline(pdf_path, config_path=None, output_dir=None, llm_client=None):
        calls.append(pdf_path)
        return {"status": "completed", "paper": {"filename": pdf_path},
                "figures": [], "overall_risk": {"score": 0.0, "category": "low"}}

    monkeypatch.setattr("src.pipeline.orchestrator.run_pipeline", fake_run_pipeline)

    # Two papers, both with "existing" PDFs (paths need not really exist because
    # our fake pipeline ignores them — but pdf_exists must be True to not skip).
    evaluation_set = {
        "dataset_name": "resume-test",
        "papers": [
            {"paper_id": "done_paper", "pdf_path": "a.pdf", "pdf_exists": True,
             "is_fraudulent": True, "figures": []},
            {"paper_id": "todo_paper", "pdf_path": "b.pdf", "pdf_exists": True,
             "is_fraudulent": False, "figures": []},
        ],
    }
    out = str(tmp_path / "out")
    import os
    os.makedirs(out, exist_ok=True)
    # Pre-seed benchmark_report.json with done_paper already completed.
    seed = {"results": {"done_paper": {"ground_truth":
            evaluation_set["papers"][0], "status": "ok",
            "pipeline_report": {"overall_risk": {"score": 0.0}}}}}
    with open(os.path.join(out, "benchmark_report.json"), "w", encoding="utf-8") as fh:
        json.dump(seed, fh)

    report = benchmark_runner.run_benchmark(
        evaluation_set, pipeline_config_path="src/config/config.yaml",
        output_dir=out, resume=True)

    # Only the pending paper's pipeline ran; the completed one was skipped.
    assert calls == ["b.pdf"]
    assert set(report["results"]) == {"done_paper", "todo_paper"}


def test_benchmark_no_resume_reruns_all(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("src.pipeline.orchestrator.run_pipeline",
                        lambda pdf_path, **kw: calls.append(pdf_path) or
                        {"status": "completed", "paper": {"filename": pdf_path},
                         "figures": [], "overall_risk": {"score": 0.0, "category": "low"}})
    evaluation_set = {"papers": [
        {"paper_id": "p1", "pdf_path": "a.pdf", "pdf_exists": True,
         "is_fraudulent": True, "figures": []}]}
    benchmark_runner.run_benchmark(evaluation_set, "src/config/config.yaml",
                                   output_dir=str(tmp_path / "o"), resume=False)
    assert calls == ["a.pdf"]

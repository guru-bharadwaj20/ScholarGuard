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


def test_f1_is_zero_not_undefined_when_a_rate_is_zero():
    """A measured 0.0 must not render as "not measurable".

    A detector that fires only on clean figures has precision 0.0 and F1 0.0 --
    a real, terrible measurement. `not precision` treated that as undefined, so
    metrics_summary.md showed the worst possible result identically to a
    missing one.
    """
    # Fires once, always wrongly; catches nothing. precision 0, recall 0.
    m = metrics.binary_metrics({"tp": 0, "fp": 3, "fn": 4, "tn": 5})
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1"] == 0.0

    # Catches everything but also floods false alarms: recall 1, precision 0.2.
    m = metrics.binary_metrics({"tp": 2, "fp": 8, "fn": 0, "tn": 5})
    assert m["recall"] == 1.0
    assert m["f1"] == pytest.approx(2 * 0.2 * 1.0 / 1.2, abs=1e-3)

    # Only a zero DENOMINATOR is undefined, and that still returns None.
    assert metrics.binary_metrics({"tp": 0, "fp": 0, "fn": 0, "tn": 5})["f1"] is None


def test_binary_metrics_handles_undefined_ratios():
    # No positives predicted or present -> precision undefined (None), not 0.
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 5}
    m = metrics.binary_metrics(counts)
    assert m["precision"] is None
    assert m["false_positive_rate"] == 0.0  # 0/(0+5)


def test_wilson_interval_matches_reference_values():
    """Verified against statsmodels' `proportion_confint(method='wilson')` and
    published tables; z(0.975)=1.959963985 matches scipy.stats.norm.ppf."""
    # 8 of 15 -> the canonical reference pair for this project's n=15 fraud set.
    low, high = metrics.wilson_confidence_interval(8, 15)
    assert low == pytest.approx(0.3012, abs=5e-4)
    assert high == pytest.approx(0.7519, abs=5e-4)

    # Zero successes: Wald would give a nonsensical zero-width (0, 0).
    low, high = metrics.wilson_confidence_interval(0, 10)
    assert low == pytest.approx(0.0, abs=1e-6)
    assert high == pytest.approx(0.2775, abs=5e-4)

    # Perfect score: upper bound pinned at 1, lower bound well below it.
    low, high = metrics.wilson_confidence_interval(15, 15)
    assert low == pytest.approx(0.7961, abs=5e-4)
    assert high == 1.0


def test_wilson_interval_edges_and_validation():
    # Undefined proportion -> maximally uncertain, not a fake point estimate.
    assert metrics.wilson_confidence_interval(0, 0) == (0.0, 1.0)
    # Wider confidence -> wider interval.
    lo95, hi95 = metrics.wilson_confidence_interval(8, 15, 0.95)
    lo99, hi99 = metrics.wilson_confidence_interval(8, 15, 0.99)
    assert lo99 < lo95 and hi99 > hi95
    # Bounds always inside [0, 1].
    for s in range(0, 11):
        lo, hi = metrics.wilson_confidence_interval(s, 10)
        assert 0.0 <= lo <= hi <= 1.0
    with pytest.raises(ValueError):
        metrics.wilson_confidence_interval(11, 10)
    with pytest.raises(ValueError):
        metrics.wilson_confidence_interval(1, 10, confidence=1.0)


def test_metrics_with_confidence_attaches_intervals():
    counts = {"tp": 8, "fp": 2, "fn": 7, "tn": 8}
    out = metrics.metrics_with_confidence(counts)
    # recall = 8/15 -> the reference interval above.
    assert out["recall"]["n"] == 15
    assert out["recall"]["value"] == pytest.approx(8 / 15, abs=1e-4)
    assert out["recall"]["ci_low"] == pytest.approx(0.3012, abs=5e-4)
    # F1 is explicitly given no interval.
    assert out["f1"]["ci_low"] is None
    assert "not a binomial proportion" in out["f1"]["note"]
    rendered = metrics.format_metric_with_ci(out["recall"])
    assert "95% CI" in rendered and "n=15" in rendered


def test_format_metric_handles_undefined():
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 5}
    out = metrics.metrics_with_confidence(counts)
    assert out["precision"]["value"] is None
    assert metrics.format_metric_with_ci(out["precision"]).startswith("n/a")


def _fake_benchmark(figure_num, is_fraudulent=True, fired=True):
    """One paper, one figure; copy_move fires. figure_num=None => unlabeled."""
    return {"results": {"P1": {
        "status": "ok",
        "ground_truth": {
            "paper_id": "P1", "is_fraudulent": is_fraudulent,
            "label_confidence": "confirmed",
            "figures": ([{"figure_num": figure_num, "fraud_type": "copy_move"}]
                        if is_fraudulent else []),
        },
        "pipeline_report": {
            "overall_risk": {"score": 40.0, "category": "moderate"},
            "figures": [{
                "figure": "Figure 1", "figure_num": figure_num, "image_path": None,
                "detectors": {
                    "copy_move": {"status": "ok", "forged": fired, "confidence": 0.9},
                    "cross_figure": {"status": "ok", "n_exact": 0,
                                     "n_region_reuse": 0, "n_visual_similar": 0},
                    "ai_generation": {"status": "ok", "verdict": "likely_real",
                                      "classifier_used": False},
                    "claim_consistency": {"status": "skipped"},
                }}]}}}}


def test_unannotated_fraud_figures_are_unlabeled_not_negative():
    """A confirmed-fraud paper with figure_num=null tells us the PAPER is
    fraudulent, not WHICH figure. Its figures must be excluded from the
    per-detector confusion matrix, never counted as ground-truth negatives
    (which would turn a correct detection into a false positive)."""
    from src.evaluation import error_analysis as ea

    figs, _ = ea.build_records(_fake_benchmark(figure_num=None))
    assert all(r["gt_known"] is False for r in figs)

    dm = ea.per_detector_metrics(figs)["copy_move"]
    assert dm["n_evaluated"] == 0            # nothing scoreable
    assert dm["n_unlabeled"] == 1
    assert dm["n_fired_on_unlabeled"] == 1
    assert dm["confusion"] == {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    errors = ea.categorize_errors(figs)
    assert errors["false_positives"] == []   # NOT a false positive
    assert len(errors["unlabeled_hits"]) == 1
    assert "not annotated" in errors["unlabeled_hits"][0]["reason"]


def test_annotated_fraud_figure_is_scored_normally():
    from src.evaluation import error_analysis as ea

    figs, _ = ea.build_records(_fake_benchmark(figure_num=1))
    dm = ea.per_detector_metrics(figs)["copy_move"]
    assert dm["n_unlabeled"] == 0
    assert dm["confusion"]["tp"] == 1        # correctly credited as a hit
    assert ea.categorize_errors(figs)["false_positives"] == []


def test_clean_paper_figure_is_a_true_negative_or_false_positive():
    from src.evaluation import error_analysis as ea

    figs, _ = ea.build_records(_fake_benchmark(figure_num=1, is_fraudulent=False))
    dm = ea.per_detector_metrics(figs)["copy_move"]
    assert dm["n_unlabeled"] == 0
    assert dm["confusion"]["fp"] == 1        # clean figure, detector fired
    assert len(ea.categorize_errors(figs)["false_positives"]) == 1


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


def test_evaluators_survive_an_empty_dataset(tmp_path):
    """An empty/misnamed data dir must give an empty report, not IndexError.

    All three evaluators built their CSV header from `rows[0].keys()`, so a
    directory with no images crashed with `IndexError: list index out of range`
    instead of reporting that nothing was found.
    """
    empty = tmp_path / "no_images"
    empty.mkdir()
    out = tmp_path / "out"

    summary = metrics.evaluate_dataset(str(empty), str(out),
                                       save_visualizations=False)
    assert summary["n_images"] == 0
    assert summary["detection_accuracy"] == 0.0
    header = open(summary["csv_path"], encoding="utf-8").readline().strip()
    assert header.split(",") == metrics._DATASET_CSV_FIELDS

    ai_summary = metrics.evaluate_ai_generation(str(empty), str(empty),
                                                output_dir=str(out / "ai"))
    assert ai_summary["n_real"] == 0 and ai_summary["n_ai"] == 0
    ai_header = open(ai_summary["csv_path"], encoding="utf-8").readline().strip()
    assert ai_header.split(",") == metrics._AI_GENERATION_CSV_FIELDS


def test_cross_figure_evaluator_survives_an_empty_ground_truth(tmp_path):
    import json as _json

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "ground_truth.json").write_text(
        _json.dumps({"pairs": [], "clean": []}), encoding="utf-8")

    class _NoDetector:
        def detect(self, path):    # never called: no pairs, no clean figures
            raise AssertionError("should not run on an empty ground truth")

    summary = metrics.evaluate_cross_figure(
        str(corpus), output_dir=str(tmp_path / "out"), detector=_NoDetector())
    assert summary["n_reuse_cases"] == 0
    header = open(summary["csv_path"], encoding="utf-8").readline().strip()
    assert header.split(",") == metrics._CROSS_FIGURE_CSV_FIELDS

"""Tests for the conformal + Benjamini-Yekutieli paper-inference layer.

The two properties worth protecting are the ones the layer exists for:

* conformal p-values give a **finite-sample** false-positive guarantee, so the
  paper cutoff cannot drift between held-out sets the way a tuned percentile
  did (0.280 -> 0.457), and
* BY makes the paper decision **count-corrected**, so a paper is not flagged
  merely for having many figures -- the confound that made figure count alone
  (ROC-AUC 0.681) as good a predictor as the whole pipeline (0.685).
"""

from __future__ import annotations

import random

import pytest

from src.pipeline.paper_inference import (
    ConformalCalibrator,
    by_adjusted_pvalues,
    conformal_pvalues,
    harmonic_sum,
    paper_evidence,
)


# --------------------------------------------------------------- conformal
def test_conformal_pvalue_formula():
    """p = (1 + |{c >= s}|) / (n + 1), counting ties as at-least-as-extreme."""
    calib = [1.0, 2.0, 3.0, 4.0]
    # 5.0 beats everything -> only itself counts.
    assert conformal_pvalues([5.0], calib) == [pytest.approx(1 / 5)]
    # 0.0 beats nothing -> all four calibration points are >= it.
    assert conformal_pvalues([0.0], calib) == [pytest.approx(5 / 5)]
    # A tie counts as extreme (conservative direction).
    assert conformal_pvalues([3.0], calib) == [pytest.approx(3 / 5)]


def test_conformal_pvalues_are_monotone_in_score():
    calib = [random.gauss(0, 1) for _ in range(200)]
    pvals = conformal_pvalues([-2.0, -0.5, 0.0, 0.5, 2.0], calib)
    assert pvals == sorted(pvals, reverse=True)


def test_empty_calibration_flags_nothing():
    """No reference distribution means no evidence -- fail safe, not open."""
    assert conformal_pvalues([99.0, 1e9], []) == [1.0, 1.0]


def test_conformal_coverage_guarantee_holds_empirically():
    """P(p <= alpha) <= alpha for a genuinely clean point, at finite n.

    This is the guarantee the project's tuned cutoff never had. Simulated over
    many draws, the realised type-I rate must not exceed alpha.
    """
    rng = random.Random(20260726)
    alpha = 0.10
    n_cal, n_trials = 99, 4000
    false_flags = 0
    for _ in range(n_trials):
        calib = [rng.gauss(0, 1) for _ in range(n_cal)]
        fresh_clean = rng.gauss(0, 1)          # same distribution => exchangeable
        if conformal_pvalues([fresh_clean], calib)[0] <= alpha:
            false_flags += 1
    rate = false_flags / n_trials
    # Exact bound is <= alpha; allow Monte-Carlo slack upward only.
    assert rate <= alpha + 0.015, f"conformal over-flagged: {rate:.4f} > {alpha}"


# --------------------------------------------------------------------- BY
def test_harmonic_sum():
    assert harmonic_sum(1) == pytest.approx(1.0)
    assert harmonic_sum(4) == pytest.approx(1 + 1 / 2 + 1 / 3 + 1 / 4)
    assert harmonic_sum(0) == 0.0


def test_by_adjusted_matches_hand_computation():
    pvals = [0.001, 0.30, 0.02]
    m = 3
    c = harmonic_sum(m)                      # 1 + 1/2 + 1/3
    adj = by_adjusted_pvalues(pvals)
    # sorted: 0.001 (k=1), 0.02 (k=2), 0.30 (k=3)
    expected_largest = min(1.0, 0.30 * m * c / 3)
    expected_middle = min(expected_largest, 0.02 * m * c / 2)
    expected_smallest = min(expected_middle, 0.001 * m * c / 1)
    assert adj[1] == pytest.approx(expected_largest)
    assert adj[2] == pytest.approx(expected_middle)
    assert adj[0] == pytest.approx(expected_smallest)


def test_by_adjusted_is_monotone_and_bounded():
    pvals = [0.9, 0.001, 0.4, 0.02, 0.7, 0.15]
    adj = by_adjusted_pvalues(pvals)
    assert all(0.0 <= a <= 1.0 for a in adj)
    # Order is preserved: a larger raw p never gets a smaller adjusted p.
    pairs = sorted(zip(pvals, adj))
    assert [a for _, a in pairs] == sorted(a for _, a in pairs)


def test_by_is_never_more_lenient_than_bonferroni_at_rank_one():
    """BY's smallest adjusted p is m*C(m) * p_min, harsher than Bonferroni."""
    pvals = [0.004, 0.5, 0.6, 0.7]
    adj = by_adjusted_pvalues(pvals)
    assert min(adj) >= min(1.0, 0.004 * len(pvals))


def test_by_empty():
    assert by_adjusted_pvalues([]) == []


# -------------------------------------------------------- count correction
def test_extra_clean_figures_do_not_raise_the_paper_statistic():
    """BY does correct for figure count — the property it was built for.

    Same single suspicious figure, once alone and once buried among many
    unremarkable ones. The shipped ``0.7*max + 0.3*mean`` aggregation rises with
    figure count on clean papers (corr 0.451); the BY statistic must not.

    Note this property is real but did not pay off: on set 1 the BY ranking
    measured WORSE than the uncorrected one (0.561 vs 0.685), so the shipped
    pipeline does not rank with it. See the module docstring.
    """
    calib = [float(i) / 100 for i in range(100)]      # clean figure scores 0..0.99
    small = paper_evidence([0.995], calib)
    large = paper_evidence([0.995] + [0.10] * 19, calib)
    assert large.statistic < small.statistic, (
        "adding unremarkable figures increased suspicion — the count confound "
        "is back")


def test_paper_with_no_figures_is_inert():
    ev = paper_evidence([], [0.1, 0.2, 0.3])
    assert ev.statistic == 0.0
    assert ev.n_figures == 0 and ev.n_flagged == 0
    assert ev.min_adjusted_pvalue == 1.0


def test_statistic_increases_with_stronger_evidence():
    calib = [float(i) / 100 for i in range(100)]
    weak = paper_evidence([0.5, 0.4, 0.3], calib)
    strong = paper_evidence([0.999, 0.4, 0.3], calib)
    assert strong.statistic > weak.statistic


def test_to_dict_is_json_safe_and_names_its_method():
    ev = paper_evidence([0.9, 0.1], [float(i) / 50 for i in range(50)])
    d = ev.to_dict()
    assert set(d) >= {"statistic", "min_adjusted_pvalue", "n_figures",
                      "n_flagged", "alpha", "method"}
    assert "Benjamini-Yekutieli" in d["method"]
    assert all(isinstance(v, (int, float, str, list)) for v in d.values())


# ------------------------------------------------------ paper-level cutoff
def test_calibrator_guarantees_its_false_positive_rate():
    rng = random.Random(11)
    clean = [rng.gauss(0, 1) for _ in range(199)]
    cal = ConformalCalibrator.fit(clean)
    fresh = [rng.gauss(0, 1) for _ in range(3000)]
    rate = sum(1 for s in fresh if cal.flag(s, alpha=0.10)) / len(fresh)
    assert rate <= 0.10 + 0.02, f"paper-level FPR exceeded alpha: {rate:.4f}"


def test_calibrator_ranks_monotonically():
    cal = ConformalCalibrator.fit([0.0, 1.0, 2.0, 3.0])
    assert cal.pvalue(4.0) < cal.pvalue(2.0) < cal.pvalue(-1.0)

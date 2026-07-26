"""Paper-level inference: conformal p-values + Benjamini-Yekutieli FDR control.

Why this exists (the measurement that forced it)
------------------------------------------------
The shipped paper score is ``0.7 * worst_figure + 0.3 * mean_figure``. On
held-out set 1 it reaches ROC-AUC 0.685. So does this predictor::

    len(paper.figures)

Figure count alone scores **0.681** — no image analysis whatsoever. Dividing the
paper score by the figure count collapses it to 0.505, i.e. chance. Among clean
papers, ``corr(n_figures, risk_score) = 0.451``: a clean paper with 8 figures
averages 24.1 risk, one with 4 averages 15.0.

The per-figure detectors are not the problem — copy-move has recall 0.57 against
a 0.14 clean-figure false-alarm rate, which is real signal. The *aggregation* is
the problem. Summing evidence over an unbounded number of figures means the
statistic grows with how many chances the pipeline was given to fire, and
retracted papers happen to have more figures (median 7.5 vs 5.0). That is
uncontrolled multiple testing, and it is what this module replaces.

What this module provides
-------------------------
**Per-figure conformal p-values.** Rather than asking "how many points did this
figure score", ask "how extreme is this figure's score against a reference set
of *clean* figures". With a clean calibration set of size ``n``::

    p = (1 + |{c in calibration : c >= s}|) / (n + 1)

Under exchangeability alone this satisfies ``P(p <= alpha) <= alpha`` for a
genuinely clean figure — finite-sample, distribution-free, no parametric null.
See :func:`conformal_pvalues`.

**Benjamini-Yekutieli across the figures of one paper.** Control the false
discovery rate rather than thresholding a sum. BY (not BH) because figures within
a paper are strongly dependent — same instrument, same compression, same authors
— and BY's ``C(m) = sum(1/i)`` factor is valid under *arbitrary* dependence,
which is the only assumption available here. The BY threshold for the k-th
smallest of m p-values scales as ``alpha * k / (m * C(m))``, so a 20-figure paper
demands proportionally stronger per-figure evidence than a 4-figure paper: the
count correction is not fitted or regressed out, it falls out of the procedure.

**Paper-level conformal calibration.** :class:`ConformalCalibrator` gives a
chosen ``alpha`` a *guaranteed* paper-level false-positive rate, aimed at the
finding that paper FPR moved 0.280 -> 0.457 between two held-out sets with no
code change, because the cutoff was an empirically tuned percentile. A conformal
cutoff cannot drift that way. It does **not** improve ranking — a conformal
transform is monotone, so ROC-AUC is unchanged by construction.

Measured outcome: BY is NOT used for ranking
--------------------------------------------
The count correction above was built to fix the confound, and on held-out set 1
it makes ranking **worse**, not better. Leave-one-paper-out calibrated, against
the shipped 0.685 and the noisy-OR posterior's 0.758:

===============================  ========  =====
statistic                        ROC-AUC   AP
===============================  ========  =====
BY min-adjusted p (this module)  0.561     0.412
count of BY-rejected figures     0.500     0.375
Simes                            0.602     0.455
Fisher                           0.650     0.597
Stouffer                         0.513     0.443
Higher criticism                 0.633     0.544
===============================  ========  =====

Every count-corrected combiner loses to simply accumulating evidence. Two
reasons, and both are about this data rather than about the theory:

1. **The per-figure statistic is too coarse for a rank-based method.** 42.5% of
   figures score exactly 0 and 48.6% of the clean calibration figures do too, so
   most conformal p-values collapse onto a handful of values and the ordering
   inside them is lost.
2. **``min`` uses one figure.** BY's headline is driven by the single best
   figure, and a max-type statistic was already the weaker choice here (max
   figure probability 0.723 vs noisy-OR 0.758). Correcting a weak statistic for
   count does not make it strong.

The honest conclusion is that figure count is not purely an artifact to be
removed — some of it is real signal (bigger papers do carry more opportunity),
and stripping it costs more than the confound does. So the count correction
belongs in *measurement*, where :func:`src.evaluation.metrics.count_matched_auc`
now reports it on every run, and not in the shipped ranking.

What is kept and why: the conformal machinery still delivers the FPR guarantee,
which is a theorem rather than a measurement and holds whichever statistic it
wraps. The BY functions are kept because they are the diagnostic that produced
the table above, and because a future per-figure statistic with fewer ties could
change the answer — but nothing in the shipped pipeline ranks papers with them.

Everything here is additive: it never mutates the point score.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

# Default target false-discovery / false-positive rate. Screening tools should
# tolerate a fairly generous FDR -- the output is a lead for human review, and
# missing fraud costs more than a reviewer glancing at a clean figure.
DEFAULT_ALPHA = 0.10


def harmonic_sum(m: int) -> float:
    """``C(m) = sum_{i=1..m} 1/i`` — the Benjamini-Yekutieli dependence factor.

    This is the price BY pays over BH for dropping the independence assumption.
    It grows like ``ln(m) + 0.577``, so it is mild: 1.0 at m=1, 2.93 at m=10,
    4.28 at m=40. That slow growth is the point — it corrects for figure count
    without flattening large papers into never-flaggable.
    """
    if m <= 0:
        return 0.0
    return sum(1.0 / i for i in range(1, m + 1))


def conformal_pvalues(scores: list[float],
                      calibration: list[float]) -> list[float]:
    """Split-conformal p-values for ``scores`` against a clean ``calibration`` set.

    Higher score == more suspicious, so the p-value counts calibration examples
    at least as extreme::

        p = (1 + |{c >= s}|) / (n + 1)

    The ``+1`` in both numerator and denominator is not a smoothing fudge; it is
    what makes the bound exact rather than asymptotic (the test point is treated
    as exchangeable with the calibration set, so it counts itself).

    With an empty calibration set every p-value is 1.0 — no reference, therefore
    no evidence. That is the safe direction: it flags nothing.
    """
    n = len(calibration)
    if n == 0:
        return [1.0] * len(scores)
    # Sort ascending once; |{c >= s}| = n - bisect_left(sorted_calib, s).
    ordered = sorted(float(c) for c in calibration)
    out = []
    for s in scores:
        n_ge = n - bisect_left(ordered, float(s))
        out.append((1.0 + n_ge) / (n + 1.0))
    return out


def by_adjusted_pvalues(pvalues: list[float]) -> list[float]:
    """Benjamini-Yekutieli adjusted p-values, in the input order.

    Step-up procedure: sort ascending, scale the k-th by ``m * C(m) / k``, then
    enforce monotonicity by taking a running minimum from the largest p-value
    downwards (an adjusted p-value must not decrease as the raw one increases).
    Clipped to 1.0.

    Rejecting every hypothesis whose adjusted p-value is ``<= alpha`` controls
    the FDR at ``alpha`` under arbitrary dependence between the p-values.
    """
    m = len(pvalues)
    if m == 0:
        return []
    factor = m * harmonic_sum(m)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running_min = 1.0
    # Walk from the largest p-value down so the running minimum enforces
    # monotonicity in one pass.
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        value = pvalues[idx] * factor / rank
        running_min = min(running_min, value)
        adjusted[idx] = min(1.0, running_min)
    return adjusted


@dataclass
class PaperEvidence:
    """Count-corrected paper-level evidence derived from figure scores."""

    figure_pvalues: list[float] = field(default_factory=list)
    adjusted_pvalues: list[float] = field(default_factory=list)
    min_adjusted_pvalue: float = 1.0
    n_figures: int = 0
    n_flagged: int = 0
    alpha: float = DEFAULT_ALPHA
    statistic: float = 0.0

    def to_dict(self) -> dict:
        return {
            "statistic": round(self.statistic, 4),
            "min_adjusted_pvalue": round(self.min_adjusted_pvalue, 6),
            "n_figures": self.n_figures,
            "n_flagged": self.n_flagged,
            "alpha": self.alpha,
            "figure_pvalues": [round(p, 6) for p in self.figure_pvalues],
            "adjusted_pvalues": [round(p, 6) for p in self.adjusted_pvalues],
            "method": "split-conformal p-values + Benjamini-Yekutieli FDR",
        }


def paper_evidence(figure_scores: list[float],
                   calibration: list[float],
                   alpha: float = DEFAULT_ALPHA) -> PaperEvidence:
    """Turn one paper's figure scores into count-corrected paper evidence.

    ``calibration`` is a set of figure scores drawn from **clean** papers; it
    defines the null against which this paper's figures are judged.

    The returned ``statistic`` is ``-log10(min adjusted p)``: 0 when nothing is
    unusual, growing as the best-corrected figure evidence strengthens. It is the
    value to rank papers by.
    """
    m = len(figure_scores)
    if m == 0:
        return PaperEvidence(alpha=alpha)
    pvals = conformal_pvalues(figure_scores, calibration)
    adjusted = by_adjusted_pvalues(pvals)
    min_adj = min(adjusted)
    return PaperEvidence(
        figure_pvalues=pvals,
        adjusted_pvalues=adjusted,
        min_adjusted_pvalue=min_adj,
        n_figures=m,
        n_flagged=sum(1 for a in adjusted if a <= alpha),
        alpha=alpha,
        # min_adj is bounded below by 1/(n_calib+1) > 0, so the log is safe.
        statistic=-math.log10(min_adj) if min_adj > 0 else 0.0,
    )


@dataclass
class ConformalCalibrator:
    """Distribution-free paper-level cutoff with a guaranteed false-positive rate.

    Fit on paper statistics from **clean** papers only (label-conditional, a.k.a.
    Mondrian, conformal). ``pvalue`` then satisfies ``P(pvalue <= alpha) <= alpha``
    for a fresh clean paper, whatever the score distribution — which is precisely
    the guarantee the project's tuned percentile cutoff lacked when its FPR moved
    0.280 -> 0.457 between held-out sets.
    """

    clean_statistics: list[float] = field(default_factory=list)

    @classmethod
    def fit(cls, clean_statistics: list[float]) -> "ConformalCalibrator":
        return cls(clean_statistics=sorted(float(s) for s in clean_statistics))

    def pvalue(self, statistic: float) -> float:
        return conformal_pvalues([statistic], self.clean_statistics)[0]

    def flag(self, statistic: float, alpha: float = DEFAULT_ALPHA) -> bool:
        """True when the paper should be surfaced, at guaranteed FPR <= alpha."""
        return self.pvalue(statistic) <= alpha

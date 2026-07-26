"""Combine all detector signals into per-figure and per-paper risk scores.

The combination logic is a **transparent, documented judgment call** — not a
black box. All weights/thresholds come from ``config.yaml`` (risk_scoring.*).

Per-figure score (0-100)
-------------------------
Each detector contributes up to its configured weight; the weights sum to 100,
so a figure that maxes every signal scores 100. A detector that was skipped or
errored contributes 0 **and** is recorded in the breakdown (never silently
dropped).

    copy_move          weight * confidence            (confidence in [0,1])
    cross_figure       weight * severity              (exact 1.0 / region 0.9 /
                                                        visual-only 0.0)
    ai_generation      weight * severity              (likely_ai 1.0 /
                                                        suspicious 0.5 / real 0.0)
    claim_consistency  weight * text_image_confidence (in [0,1])

Per-paper score (0-100)
-----------------------
NOT a plain mean — one clearly-forged figure must dominate five clean ones. We
use ``max_figure_weight * worst_figure + mean_figure_weight * mean_figure``
(default 0.7/0.3). The paper category is additionally floored at the worst
single figure's category, so a `critical` figure always makes the paper at
least `high`.
"""

from __future__ import annotations

from src.config.settings import RISK_CATEGORIES, Settings
from src.pipeline.evidence_fusion import FusionConfig, fuse_figure, fuse_paper


def _category_for(score: float, categories: dict) -> str:
    """Highest category whose score threshold ``score`` meets or exceeds."""
    chosen = RISK_CATEGORIES[0]
    for cat in RISK_CATEGORIES:
        if score >= categories.get(cat, 0):
            chosen = cat
    return chosen


def _cat_rank(category: str) -> int:
    return RISK_CATEGORIES.index(category) if category in RISK_CATEGORIES else 0


def score_figure(detectors: dict, settings: Settings) -> dict:
    """Score one figure from its detector-result dict.

    ``detectors`` maps detector name -> its result dict (each has a "status"
    of ok/skipped/error plus signal fields). Returns
    ``{"score", "category", "breakdown": [...]}`` where each breakdown entry
    explains one detector's contribution (including 0 for skipped/errored).
    """
    risk = settings.risk
    weights = risk.get("weights", {})
    cf_sev = risk.get("cross_figure_severity", {})
    ai_sev = risk.get("ai_generation_severity", {})

    breakdown: list[dict] = []

    def contribution(name: str, weight_key: str, severity: float, note: str,
                     status: str):
        weight = float(weights.get(weight_key, 0))
        points = round(weight * max(0.0, min(1.0, severity)), 2)
        breakdown.append({
            "detector": name,
            "status": status,
            "max_points": weight,
            "points": points if status == "ok" else 0.0,
            # Whether the detector FIRED, recorded separately from the points it
            # contributed. A lead-only detector (weight 0) still fired and still
            # corroborates its neighbours; inferring that from points > 0 would
            # silently drop it out of the corroboration count.
            "fired": bool(status == "ok" and severity > 0),
            "note": note,
        })
        return points if status == "ok" else 0.0

    total = 0.0

    # --- copy-move ---------------------------------------------------------
    cm = detectors.get("copy_move", {"status": "skipped"})
    if cm.get("status") == "ok":
        sev = float(cm.get("confidence", 0.0)) if cm.get("forged") else 0.0
        note = (f"duplicated regions within figure (conf {cm.get('confidence')})"
                if cm.get("forged") else "no in-figure duplication")
        total += contribution("copy_move", "copy_move", sev, note, "ok")
    else:
        contribution("copy_move", "copy_move", 0.0,
                     f"copy-move {cm.get('status')}", cm.get("status", "skipped"))

    # --- cross-figure reuse ------------------------------------------------
    cf = detectors.get("cross_figure", {"status": "skipped"})
    if cf.get("status") == "ok":
        if cf.get("n_exact", 0) > 0:
            sev, note = cf_sev.get("exact_duplicate", 1.0), \
                f"{cf['n_exact']} near-exact duplicate figure(s)"
        elif cf.get("n_region_reuse", 0) > 0:
            sev, note = cf_sev.get("region_reuse", 0.9), \
                f"{cf['n_region_reuse']} reused region(s) from another figure"
        else:
            sev, note = cf_sev.get("visual_similar_only", 0.0), \
                "only low-confidence visual-similarity leads"
        total += contribution("cross_figure", "cross_figure", sev, note, "ok")
    else:
        contribution("cross_figure", "cross_figure", 0.0,
                     f"cross-figure {cf.get('status')}", cf.get("status", "skipped"))

    # --- splice / foreign-region ------------------------------------------
    sp = detectors.get("splice", {"status": "skipped"})
    if sp.get("status") == "ok":
        sev = float(sp.get("confidence", 0.0)) if sp.get("spliced") else 0.0
        note = (f"spliced/foreign region(s) detected "
                f"({sp.get('n_flagged_blocks')} block(s), conf {sp.get('confidence')})"
                if sp.get("spliced") else "no spliced/foreign regions")
        total += contribution("splice", "splice", sev, note, "ok")
    else:
        contribution("splice", "splice", 0.0,
                     f"splice {sp.get('status')}", sp.get("status", "skipped"))

    # --- AI generation -----------------------------------------------------
    ai = detectors.get("ai_generation", {"status": "skipped"})
    if ai.get("status") == "ok":
        verdict = ai.get("verdict", "likely_real")
        sev = float(ai_sev.get(verdict, 0.0))
        note = f"AI-generation verdict: {verdict}"
        if not ai.get("classifier_used", False):
            note += " (forensics-only, no classifier)"
        total += contribution("ai_generation", "ai_generation", sev, note, "ok")
    else:
        contribution("ai_generation", "ai_generation", 0.0,
                     f"ai-generation {ai.get('status')}", ai.get("status", "skipped"))

    # --- claim consistency -------------------------------------------------
    cc = detectors.get("claim_consistency", {"status": "skipped"})
    if cc.get("status") == "ok":
        sev = float(cc.get("confidence", 0.0)) if not cc.get("consistent", True) else 0.0
        note = ("; ".join(cc.get("mismatches", [])) or "text and figure consistent")
        total += contribution("claim_consistency", "claim_consistency", sev,
                              note[:200], "ok")
    else:
        contribution("claim_consistency", "claim_consistency", 0.0,
                     f"claim-consistency {cc.get('status')}",
                     cc.get("status", "skipped"))

    score = round(min(100.0, total), 2)
    category = _category_for(score, risk.get("categories", {}))
    # Additive probabilistic layer: a calibrated posterior that discounts
    # detectors whose fire rate barely differs between fraud and clean (see
    # src.pipeline.evidence_fusion). Does NOT change the point score above —
    # it augments it, and drives the paper-level probability.
    fusion = fuse_figure(detectors, _fusion_config(settings))
    # Corroboration: how many INDEPENDENT detectors fire on THIS figure. On the
    # held-out benchmark, ranking papers by their most-corroborated figure lifted
    # average precision from ~0.45 to ~0.70 — a figure two detectors agree on is
    # real evidence; a paper full of lone single-detector fires (usually false
    # positives, which compound across many figures) is not. This is the honest
    # signal a screening tool should lead with.
    # Counts detectors that FIRED, not detectors that scored: a lead-only
    # detector (weight 0, e.g. splice since its recall was measured) contributes
    # no points but its agreement with another detector on the same figure is
    # still evidence, and that agreement is what this term exists to capture.
    n_signals = sum(1 for b in breakdown if b.get("fired"))
    return {"score": score, "category": category, "breakdown": breakdown,
            "n_corroborating_signals": n_signals,
            "fraud_probability": fusion["fraud_probability"],
            "evidence": fusion}


def _fusion_config(settings: Settings) -> FusionConfig:
    return FusionConfig.from_settings_dict(settings.raw.get("evidence_fusion"))


def score_paper(figure_scores: list[dict], settings: Settings) -> dict:
    """Aggregate per-figure scores into a paper-level risk score + category.

    Worst figure dominates (see module docstring). Returns
    ``{"score", "category", "n_figures", "worst_figure_category"}``.
    """
    risk = settings.risk
    agg = risk.get("paper_aggregation", {})
    categories = risk.get("categories", {})

    if not figure_scores:
        # A paper with no figures carries no image evidence either way. Return
        # the same KEYS as the populated branch, not a shorter dict: consumers
        # that read fraud_probability across a whole benchmark would otherwise
        # hit None on this one paper and drop the statistic for the entire run.
        return {"score": 0.0, "category": "low", "n_figures": 0,
                "max_corroboration": 0,
                "worst_figure_score": 0.0,
                "worst_figure_category": None,
                "fraud_probability": 0.0,
                "note": "no figures to score"}

    scores = [f["score"] for f in figure_scores]
    worst = max(scores)
    mean = sum(scores) / len(scores)
    paper_score = round(
        agg.get("max_figure_weight", 0.7) * worst
        + agg.get("mean_figure_weight", 0.3) * mean, 2)
    category = _category_for(paper_score, categories)

    # Probabilistic aggregate: noisy-OR over per-figure fraud probabilities
    # (additive; the point score/category above are unchanged).
    fig_probs = [f.get("fraud_probability", 0.0) for f in figure_scores]
    paper_fraud_probability = fuse_paper(fig_probs) if any(fig_probs) else 0.0

    # Corroboration: the most independent detectors that agree on any ONE figure
    # (the signal that lifted held-out average precision from ~0.45 to ~0.70).
    max_corroboration = max((f.get("n_corroborating_signals", 0)
                             for f in figure_scores), default=0)

    # Floor the paper category at the worst single figure's category — a
    # critical figure must never be diluted below "high" by clean figures.
    worst_cat = _category_for(worst, categories)
    if _cat_rank(worst_cat) > _cat_rank(category):
        # Bump to one below the worst figure at minimum (so a lone critical
        # figure -> at least high), but never above the worst figure itself.
        floored = RISK_CATEGORIES[max(0, _cat_rank(worst_cat) - 1)]
        if _cat_rank(floored) > _cat_rank(category):
            category = floored

    # Corroboration floor: a figure that two or more INDEPENDENT detectors flag
    # is far more likely real manipulation than any lone signal, so it lifts the
    # paper to at least "high"; three or more -> "critical". This is what makes
    # the paper decision lead with agreement rather than with a single (often
    # false-positive) detector that merely compounds across many figures.
    if max_corroboration >= 3 and _cat_rank(category) < _cat_rank("critical"):
        category = "critical"
    elif max_corroboration >= 2 and _cat_rank(category) < _cat_rank("high"):
        category = "high"

    return {
        "score": paper_score,
        "category": category,
        "n_figures": len(figure_scores),
        "max_corroboration": max_corroboration,
        "worst_figure_score": worst,
        "worst_figure_category": worst_cat,
        "fraud_probability": paper_fraud_probability,
    }

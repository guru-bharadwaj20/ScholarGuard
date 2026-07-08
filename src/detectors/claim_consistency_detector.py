"""Claim-consistency detector (Stage 5 orchestrator).

Reads a paper PDF and, for every figure, combines **all** ScholarGuard
signals into one per-figure integrity report:

  * **Text**   — LLM-extracted claims (sample size, panel count, stats) vs.
                 an approximate visual element count (:mod:`src.nlp`).
  * **Image**  — the existing Stage 2/3/4 detectors, run unchanged on each
                 extracted figure:
                   - Stage 2 copy-move (duplicated regions within a figure),
                   - Stage 3 cross-figure reuse (a figure duplicating another
                     figure *in the same paper* — the paper's own figures form
                     the corpus),
                   - Stage 4 AI-generation forensics.

Stage 5 does NOT reimplement any detector — it imports and calls their public
entry points (``detect_copy_move``, ``CrossFigureDetector``,
``detect_ai_generation``).

Main entry point:
    analyze_paper(pdf_path) -> {"paper", "figures": [...], "paper_summary": {...}}

CLI:
    python -m src.detectors.claim_consistency_detector \
        --pdf paper.pdf --output outputs/stage5_results/
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile

from src.detectors.ai_generation_detector import detect_ai_generation
from src.detectors.copy_move_detector import detect_copy_move
from src.detectors.cross_figure_detector import CrossFigureDetector
from src.nlp.claim_extractor import EMPTY_CLAIMS, extract_claims
from src.nlp.consistency_checker import check_consistency, count_visual_elements
from src.nlp.pdf_parser import parse_paper

# Per-figure risk banding from the combined evidence.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


class ClaimConsistencyDetector:
    """Runs the full text+image pipeline over one paper."""

    def __init__(self, llm_client=None, run_image_detectors: bool = True,
                 ai_weights_path: str | None = None):
        # llm_client is injectable so tests/CI can avoid real API calls.
        self._llm_client = llm_client
        self.run_image_detectors = run_image_detectors
        self.ai_weights_path = ai_weights_path

    # ------------------------------------------------------------------ API
    def analyze_paper(self, pdf_path: str, output_dir: str | None = None) -> dict:
        """Full pipeline: parse PDF → per-figure claims + forensics → report."""
        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = output_dir or os.path.join("outputs", "stage5_results")
        os.makedirs(output_dir, exist_ok=True)

        parsed = parse_paper(pdf_path,
                             output_dir=os.path.join(output_dir, f"{stem}_figures"))
        figures = parsed["figures"]

        # Stage 3 needs a corpus; use the paper's own figures so we can catch
        # a figure that reuses a panel from another figure in the SAME paper.
        cross_detector = self._build_cross_figure_detector(figures)

        reports = []
        for figure in figures:
            reports.append(self._analyze_figure(figure, cross_detector))

        paper_summary = self._summarize(reports)
        result = {
            "paper": pdf_path,
            "n_figures": len(reports),
            "figures": reports,
            "paper_summary": paper_summary,
            "sections_found": sorted(parsed["sections"].keys()),
        }
        return result

    # ------------------------------------------------------------- per figure
    def _analyze_figure(self, figure: dict, cross_detector) -> dict:
        image_path = figure.get("image_path")
        label = figure["label"]

        # --- 1. textual claims (LLM) ---------------------------------------
        claims, claim_error = self._extract_claims_safe(figure)

        # --- 2. image forensics (Stages 2/3/4) -----------------------------
        image_flags: dict = {}
        forensic_detail: dict = {}
        visual_elements = None
        if image_path and self.run_image_detectors:
            image_flags, forensic_detail = self._run_image_detectors(
                image_path, cross_detector
            )
            visual_elements = count_visual_elements(image_path)

        # --- 3. text vs. image consistency ---------------------------------
        consistency = check_consistency(
            claims, image_path, prior_detector_flags=image_flags,
            visual_elements=visual_elements,
        )

        risk, risk_reasons = self._score_figure(consistency, image_flags,
                                                claim_error)
        return {
            "figure": label,
            "figure_num": figure.get("figure_num"),
            "image_path": image_path,
            "caption": figure.get("caption", ""),
            "claims": claims,
            "claim_extraction_error": claim_error,
            "image_forensics": {
                "flags": image_flags,
                "detail": forensic_detail,
            },
            "consistency": {
                "consistent": consistency["consistent"],
                "mismatches": consistency["mismatches"],
                "text_image_confidence": consistency["confidence"],
            },
            "risk_level": risk,
            "risk_reasons": risk_reasons,
        }

    def _extract_claims_safe(self, figure: dict):
        """Extract claims, degrading gracefully if the LLM is unavailable."""
        caption = figure.get("caption", "")
        context = figure.get("results_context", "")
        if not (caption.strip() or context.strip()):
            return dict(EMPTY_CLAIMS), None
        try:
            claims = extract_claims(caption, context, figure["label"],
                                    client=self._llm_client)
            return claims, None
        except Exception as exc:  # LLMConfigError / LLMResponseError / etc.
            # No API key or a transient failure shouldn't abort the whole
            # paper — surface the error and continue with image forensics.
            return dict(EMPTY_CLAIMS), str(exc)

    def _run_image_detectors(self, image_path: str, cross_detector):
        """Run Stages 2/3/4 on one figure image; return (flags, detail)."""
        flags: dict = {}
        detail: dict = {}

        # Stage 2 — copy-move within the figure.
        try:
            cm = detect_copy_move(image_path)
            flags["copy_move_forged"] = bool(cm["forged"])
            detail["copy_move"] = {"forged": cm["forged"],
                                   "confidence": cm["confidence"],
                                   "n_regions": len(cm["regions"])}
        except Exception as exc:  # pragma: no cover - robustness
            detail["copy_move"] = {"error": str(exc)}

        # Stage 3 — reuse of another figure in the same paper. The corpus
        # holds a copy of every figure (including this one), so drop matches
        # against the query figure's own copy (same basename) — otherwise
        # each figure trivially "matches" itself.
        if cross_detector is not None:
            try:
                cf = cross_detector.detect(image_path)
                own = os.path.basename(image_path)

                def _others(matches):
                    return [m for m in matches
                            if os.path.basename(m["matched_image_path"]) != own]

                exact = _others(cf["exact_or_near_duplicate_matches"])
                region = _others(cf["suspected_region_reuse"])
                similar = _others(cf["visual_similarity_matches"])
                flags["cross_figure_reused"] = bool(exact or region)
                detail["cross_figure"] = {
                    "n_exact": len(exact),
                    "n_region_reuse": len(region),
                    "n_visual_similar": len(similar),
                }
            except Exception as exc:  # pragma: no cover
                detail["cross_figure"] = {"error": str(exc)}

        # Stage 4 — AI generation.
        try:
            ai = detect_ai_generation(image_path, weights_path=self.ai_weights_path)
            flags["ai_generated"] = ai["combined_verdict"] == "likely_ai_generated"
            detail["ai_generation"] = {"verdict": ai["combined_verdict"],
                                       "freq": ai["frequency_anomaly_score"],
                                       "noise": ai["noise_residual_anomaly_score"]}
        except Exception as exc:  # pragma: no cover
            detail["ai_generation"] = {"error": str(exc)}

        return flags, detail

    def _build_cross_figure_detector(self, figures: list[dict]):
        """Index the paper's own figures as the Stage 3 corpus.

        Returns a CrossFigureDetector over a temp dir of the paper's figures,
        or None if there are fewer than two images (nothing to cross-check).
        """
        if not self.run_image_detectors:
            return None
        image_paths = [f["image_path"] for f in figures if f.get("image_path")]
        if len(image_paths) < 2:
            return None
        corpus_dir = tempfile.mkdtemp(prefix="scholarguard_stage5_corpus_")
        try:
            import shutil
            for path in image_paths:
                shutil.copy(path, os.path.join(corpus_dir, os.path.basename(path)))
            return CrossFigureDetector(corpus_dir, show_progress=False)
        except Exception:  # pragma: no cover - torch/index issues
            return None

    # ----------------------------------------------------------- scoring
    @staticmethod
    def _score_figure(consistency: dict, image_flags: dict, claim_error):
        """Band a figure into low/medium/high risk from all signals."""
        reasons: list[str] = []
        text_conf = consistency["confidence"]
        reasons.extend(consistency["mismatches"])

        # High: an image forensic flag AND a textual mismatch corroborate each
        # other, or the text/image confidence is high on its own.
        image_flag_count = sum(1 for v in image_flags.values() if v)
        if (image_flag_count and not consistency["consistent"]) or text_conf >= 0.8:
            risk = RISK_HIGH
        elif image_flag_count or text_conf >= 0.5:
            risk = RISK_MEDIUM
        else:
            risk = RISK_LOW

        if not reasons and risk == RISK_LOW:
            reasons.append("no textual or image-forensic anomalies detected")
        if claim_error:
            reasons.append(f"note: claim extraction unavailable ({claim_error})")
        return risk, reasons

    @staticmethod
    def _summarize(reports: list[dict]) -> dict:
        """Aggregate per-figure risk into a paper-level summary."""
        counts = {RISK_LOW: 0, RISK_MEDIUM: 0, RISK_HIGH: 0}
        for r in reports:
            counts[r["risk_level"]] = counts.get(r["risk_level"], 0) + 1
        if counts[RISK_HIGH]:
            overall = RISK_HIGH
        elif counts[RISK_MEDIUM]:
            overall = RISK_MEDIUM
        else:
            overall = RISK_LOW
        flagged = [r["figure"] for r in reports if r["risk_level"] != RISK_LOW]
        return {
            "overall_risk": overall,
            "risk_counts": counts,
            "flagged_figures": flagged,
            "note": ("Flags are leads for human review, not proof of "
                     "misconduct. The lane/panel visual count is approximate."),
        }


def analyze_paper(pdf_path: str) -> dict:
    """Functional entry point: analyze one paper end-to-end.

    Uses a default LLMClient (needs ANTHROPIC_API_KEY); if the key is absent,
    claim extraction degrades gracefully and image forensics still run.
    """
    return ClaimConsistencyDetector().analyze_paper(pdf_path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _json_safe(obj):
    """Drop numpy arrays / non-serializable values from the report."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()
                if not isinstance(v, np.ndarray)}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return obj


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ScholarGuard claim-consistency detector")
    parser.add_argument("--pdf", required=True, help="paper PDF to analyze")
    parser.add_argument("--output", default="outputs/stage5_results")
    parser.add_argument("--no-image-detectors", action="store_true",
                        help="skip Stage 2/3/4 image forensics (text only)")
    parser.add_argument("--weights", default=None,
                        help="optional Stage 4 artifact_classifier.pt")
    args = parser.parse_args(argv)

    detector = ClaimConsistencyDetector(
        run_image_detectors=not args.no_image_detectors,
        ai_weights_path=args.weights,
    )
    result = detector.analyze_paper(args.pdf, output_dir=args.output)

    os.makedirs(args.output, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    report_path = os.path.join(args.output, f"{stem}_stage5_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(_json_safe(result), fh, indent=2)

    print(json.dumps(_json_safe({
        "paper": result["paper"],
        "n_figures": result["n_figures"],
        "paper_summary": result["paper_summary"],
        "per_figure_risk": [
            {"figure": r["figure"], "risk": r["risk_level"],
             "mismatches": r["consistency"]["mismatches"]}
            for r in result["figures"]
        ],
    }), indent=2))
    print(f"\nfull report saved to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

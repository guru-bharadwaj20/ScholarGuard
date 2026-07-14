"""The single unified ScholarGuard pipeline entry point (Stage 6).

``run_pipeline(pdf_path)`` takes one paper PDF and returns one comprehensive
integrity report covering every figure and every detection signal
(copy-move, cross-figure reuse, AI-generation, claim consistency), with a
paper-level risk score.

Design principles for this stage (integration + robustness, not new logic):

* **Never crash on one failure.** Each detector runs in its own try/except;
  a failing detector is recorded with status "error" and the rest continue.
  A corrupted PDF or missing figures produces a well-formed report, not a
  stack trace.
* **Degrade transparently.** Missing classifier weights -> AI detection runs
  forensics-only and the report says so. Missing API key -> claim consistency
  is skipped and the report says so. Nothing is silently omitted.
* **Config-driven.** All toggles/thresholds come from config.yaml via
  :class:`Settings`. Stage 2/3 thresholds are injected through their existing
  config dataclasses; no detector source is modified.
* **Efficient.** The Stage 3 corpus/embeddings are built once. The expensive
  LLM claim-extraction call is skipped for a figure already at/above the
  configured image-forensic risk category (documented + reported per figure,
  never silent).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile

from src.config.settings import RISK_CATEGORIES, Settings, load_settings
from src.pipeline import report_builder
from src.pipeline.risk_scorer import score_figure, score_paper

logger = logging.getLogger("scholarguard")
logger.addHandler(logging.NullHandler())  # caller/CLI attaches real handlers

# Sentinel so callers can pass llm_client=None to force "no LLM" while the
# default ("auto") builds one from settings.
_AUTO = object()


class Pipeline:
    """Stateful orchestrator: builds detectors once, analyzes one paper."""

    def __init__(self, settings: Settings, llm_client=_AUTO):
        self.settings = settings
        self.warnings: list[str] = []
        self._llm_client = self._resolve_llm_client(llm_client)
        # Built lazily/once per paper in analyze().
        self._copy_move = None
        self._cross_detector = None
        self._corpus_is_self = False

    # ------------------------------------------------------------------ API
    def analyze(self, pdf_path: str, output_dir: str | None = None) -> dict:
        """Run the full pipeline on one PDF and return the report dict."""
        output_dir = output_dir or self.settings.output_dir

        # --- 1. validate + parse (corrupt PDF -> graceful failure) ---------
        parsed = self._parse_pdf(pdf_path)
        if parsed is None:  # unreadable / corrupt
            report = report_builder.build_report(
                pdf_path, status="failed", figures=[],
                paper_risk={"score": 0.0, "category": "unknown"},
                warnings=self.warnings,
                error=self._parse_error or "could not read the PDF",
            )
            report_builder.save_report(report, output_dir)
            return report

        figures = parsed["figures"]
        logger.info("parsed '%s': %d section(s), %d figure(s)",
                    os.path.basename(pdf_path), len(parsed["sections"]),
                    len(figures))

        if not figures:
            self.warnings.append("no figures could be extracted from this PDF "
                                 "(nothing to analyze)")
            report = report_builder.build_report(
                pdf_path, status="completed_no_figures", figures=[],
                paper_risk=score_paper([], self.settings),
                warnings=self.warnings,
                sections_found=sorted(parsed["sections"]),
            )
            report_builder.save_report(report, output_dir)
            logger.warning("no figures found in %s", pdf_path)
            return report

        # --- 2. build shared detectors once --------------------------------
        self._build_detectors(figures)

        # --- 3. per-figure analysis ----------------------------------------
        figure_reports = []
        for figure in figures:
            figure_reports.append(self._analyze_figure(figure))

        # --- 4. score + assemble -------------------------------------------
        paper_risk = score_paper([f["risk"] for f in figure_reports], self.settings)
        logger.info("paper risk: %s (%.1f/100)", paper_risk["category"],
                    paper_risk["score"])

        report = report_builder.build_report(
            pdf_path, status="completed", figures=figure_reports,
            paper_risk=paper_risk, warnings=self.warnings,
            sections_found=sorted(parsed["sections"]),
        )
        paths = report_builder.save_report(report, output_dir)
        report["report_paths"] = paths
        logger.info("report written: %s", paths["json"])
        return report

    # --------------------------------------------------------- setup helpers
    def _resolve_llm_client(self, llm_client):
        """Return an LLM client, or None (with a warning) if unavailable."""
        if llm_client is not _AUTO:
            return llm_client  # explicit (incl. None or a test fake)
        if not self.settings.enabled("claim_consistency"):
            return None
        try:
            from src.llm.client import LLMClient
            return LLMClient(model=self.settings.llm_model,
                             max_retries=self.settings.llm_max_retries)
        except Exception as exc:  # LLMConfigError (no key), import error, etc.
            self.warnings.append(
                f"claim-consistency will be SKIPPED for all figures: {exc} "
                "(set ANTHROPIC_API_KEY to enable text/claim checking)")
            logger.warning("LLM client unavailable: %s", exc)
            return None

    def _parse_pdf(self, pdf_path: str):
        """Parse the input; return parsed dict, or None on unreadable/corrupt.

        Dispatches on source type: a PMC OA **package** (``.tar.gz`` or an
        extracted package directory) is parsed from its JATS XML + bundled
        native-resolution figure images; anything else is treated as a PDF.
        Both paths return the identical parsed-dict shape.
        """
        self._parse_error = None
        from src.nlp.pmc_package import is_package

        is_pkg = is_package(pdf_path)
        if not is_pkg and not os.path.isfile(pdf_path):
            self._parse_error = f"file not found: {pdf_path}"
            logger.error(self._parse_error)
            return None
        try:
            if is_pkg:
                from src.nlp.pmc_package import parse_pmc_package
                extract_dir = os.path.join(self.settings.output_dir, "_packages")
                os.makedirs(extract_dir, exist_ok=True)
                return parse_pmc_package(pdf_path, extract_dir=extract_dir)
            from src.nlp.pdf_parser import parse_paper
            return parse_paper(pdf_path,
                               output_dir=os.path.join(self.settings.output_dir,
                                                       "_figures"))
        except Exception as exc:  # corrupt PDF/package, unsupported format, etc.
            self._parse_error = f"failed to parse input: {exc}"
            logger.error(self._parse_error)
            return None

    def _build_detectors(self, figures: list[dict]) -> None:
        """Construct the Stage 2 detector and Stage 3 corpus once."""
        if self.settings.enabled("copy_move"):
            from src.detectors.copy_move_detector import CopyMoveDetector
            self._copy_move = CopyMoveDetector(self.settings.copy_move_config())

        # AI-generation weights degradation notice (once).
        if self.settings.enabled("ai_generation"):
            wp = self.settings.ai_weights_path
            if wp and not os.path.isfile(wp):
                self.warnings.append(
                    f"AI-generation running in FORENSICS-ONLY mode: classifier "
                    f"weights not found at '{wp}' (train via the Stage 4 Colab "
                    f"notebook to enable the learned signal)")
                logger.warning("AI classifier weights missing at %s", wp)

        if self.settings.enabled("cross_figure"):
            self._cross_detector = self._build_cross_detector(figures)

    def _build_cross_detector(self, figures: list[dict]):
        """Build the Stage 3 detector over an external corpus or the paper's own figures."""
        from src.detectors.cross_figure_detector import CrossFigureDetector

        external = self.settings.cross_figure_corpus_dir
        cfg = self.settings.cross_figure_config()
        try:
            if external and os.path.isdir(external):
                self._corpus_is_self = False
                logger.info("cross-figure corpus: external '%s'", external)
                return CrossFigureDetector(external, config=cfg, show_progress=False)

            # Default: the paper's own figures are the corpus (within-paper reuse).
            paths = [f["image_path"] for f in figures if f.get("image_path")]
            if len(paths) < 2:
                logger.info("cross-figure disabled: <2 figures to compare")
                return None
            self._corpus_is_self = True
            corpus_dir = tempfile.mkdtemp(prefix="scholarguard_stage6_corpus_")
            for p in paths:
                shutil.copy(p, os.path.join(corpus_dir, os.path.basename(p)))
            logger.info("cross-figure corpus: paper's own %d figure(s)", len(paths))
            return CrossFigureDetector(corpus_dir, config=cfg, show_progress=False)
        except Exception as exc:  # torch/index build failure -> degrade
            self.warnings.append(f"cross-figure detection unavailable: {exc}")
            logger.warning("cross-figure setup failed: %s", exc)
            return None

    # ------------------------------------------------------- per-figure logic
    def _analyze_figure(self, figure: dict) -> dict:
        label = figure["label"]
        image_path = figure.get("image_path")
        logger.info("analyzing %s", label)

        detectors: dict[str, dict] = {}
        image_flags: dict[str, bool] = {}

        # --- image detectors (Stages 2/3/4 + splice), each isolated --------
        if image_path:
            detectors["copy_move"] = self._run_copy_move(image_path, image_flags)
            detectors["cross_figure"] = self._run_cross_figure(image_path, image_flags)
            detectors["splice"] = self._run_splice(image_path, image_flags)
            detectors["ai_generation"] = self._run_ai_generation(image_path, image_flags)
        else:
            for name in ("copy_move", "cross_figure", "splice", "ai_generation"):
                detectors[name] = {"status": "skipped",
                                   "reason": "no image extracted for this figure"}

        # --- decide whether the (cheap) image risk lets us skip the LLM ----
        image_only_score = score_figure(detectors, self.settings)
        cc_result = self._run_claim_consistency(
            figure, image_path, image_flags, image_only_score["category"])
        detectors["claim_consistency"] = cc_result

        # --- final score with all four signals -----------------------------
        risk = score_figure(detectors, self.settings)
        return {
            "figure": label,
            "figure_num": figure.get("figure_num"),
            "image_path": image_path,
            "caption": figure.get("caption", ""),
            "detectors": detectors,
            "risk": risk,
        }

    def _run_copy_move(self, image_path: str, image_flags: dict) -> dict:
        if not self.settings.enabled("copy_move"):
            return {"status": "disabled"}
        try:
            r = self._copy_move.detect(_load(image_path))
            image_flags["copy_move_forged"] = bool(r["forged"])
            return {"status": "ok", "forged": bool(r["forged"]),
                    "confidence": r["confidence"], "n_regions": len(r["regions"])}
        except Exception as exc:  # noqa: BLE001 - isolate detector failure
            logger.warning("copy-move failed on %s: %s", image_path, exc)
            return {"status": "error", "error": str(exc)}

    def _run_cross_figure(self, image_path: str, image_flags: dict) -> dict:
        if not self.settings.enabled("cross_figure"):
            return {"status": "disabled"}
        if self._cross_detector is None:
            return {"status": "skipped",
                    "reason": "no corpus (need >=2 figures or an external corpus)"}
        try:
            cf = self._cross_detector.detect(image_path)
            own = os.path.basename(image_path)

            def others(matches):
                # When the corpus is the paper's own figures, a figure trivially
                # matches its own copy — exclude by basename.
                if not self._corpus_is_self:
                    return matches
                return [m for m in matches
                        if os.path.basename(m["matched_image_path"]) != own]

            exact = others(cf["exact_or_near_duplicate_matches"])
            region = others(cf["suspected_region_reuse"])
            similar = others(cf["visual_similarity_matches"])
            image_flags["cross_figure_reused"] = bool(exact or region)
            return {"status": "ok", "n_exact": len(exact),
                    "n_region_reuse": len(region), "n_visual_similar": len(similar)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("cross-figure failed on %s: %s", image_path, exc)
            return {"status": "error", "error": str(exc)}

    def _run_splice(self, image_path: str, image_flags: dict) -> dict:
        if not self.settings.enabled("splice"):
            return {"status": "disabled"}
        try:
            from src.forensics.splice_detection import detect_splice
            from src.preprocessing.panel_segmentation import build_analysis_mask
            image = _load(image_path)
            mask, _ = build_analysis_mask(image)
            r = detect_splice(image, config=self.settings.splice_config(),
                              analysis_mask=mask)
            image_flags["spliced"] = bool(r["spliced"])
            return {"status": "ok", "spliced": bool(r["spliced"]),
                    "confidence": r["confidence"],
                    "n_flagged_blocks": r["n_flagged_blocks"],
                    "cues": r["cues"]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("splice detection failed on %s: %s", image_path, exc)
            return {"status": "error", "error": str(exc)}

    def _run_ai_generation(self, image_path: str, image_flags: dict) -> dict:
        if not self.settings.enabled("ai_generation"):
            return {"status": "disabled"}
        try:
            from src.detectors.ai_generation_detector import (
                detect_ai_generation, FORENSIC_LOW, FORENSIC_HIGH)
            weights = self.settings.ai_weights_path
            weights = weights if (weights and os.path.isfile(weights)) else None
            low, high = self.settings.ai_forensic_bands(FORENSIC_LOW, FORENSIC_HIGH)
            r = detect_ai_generation(image_path, weights_path=weights,
                                     forensic_low=low, forensic_high=high,
                                     baselines=self.settings.ai_compression_baselines())
            image_flags["ai_generated"] = r["combined_verdict"] == "likely_ai_generated"
            return {"status": "ok", "verdict": r["combined_verdict"],
                    "freq_score": r["frequency_anomaly_score"],
                    "noise_score": r["noise_residual_anomaly_score"],
                    "classifier_used": r["classifier_score"] is not None}
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai-generation failed on %s: %s", image_path, exc)
            return {"status": "error", "error": str(exc)}

    def _run_claim_consistency(self, figure: dict, image_path, image_flags: dict,
                               image_category: str) -> dict:
        from src.nlp.claim_extractor import extract_claims
        from src.nlp.consistency_checker import check_consistency, count_visual_elements

        if not self.settings.enabled("claim_consistency"):
            return {"status": "disabled"}
        if self._llm_client is None:
            return {"status": "skipped",
                    "reason": "no LLM client (missing ANTHROPIC_API_KEY)"}

        # Documented efficiency short-circuit: if image forensics already put
        # this figure at/above the configured category, skip the paid LLM call.
        if self.settings.skip_llm_when_image_risk and _cat_ge(
                image_category, self.settings.skip_llm_at_category):
            logger.info("%s: skipping LLM (image risk already '%s')",
                        figure["label"], image_category)
            return {"status": "skipped_optimization",
                    "reason": (f"image forensics already at '{image_category}' "
                               f"risk; LLM claim-extraction skipped to save cost")}

        caption = figure.get("caption", "")
        context = figure.get("results_context", "")
        if not (caption.strip() or context.strip()):
            return {"status": "skipped", "reason": "no caption/text for this figure"}

        try:
            claims = extract_claims(caption, context, figure["label"],
                                    client=self._llm_client)
        except Exception as exc:  # noqa: BLE001 - LLM/network failure
            logger.warning("claim extraction failed on %s: %s",
                           figure["label"], exc)
            return {"status": "error", "error": str(exc)}

        # Multimodal observation: let the vision model actually look at the
        # figure. Far more reliable than the CV heuristic; degrade to it on
        # any failure so a vision hiccup never aborts the check.
        observations = None
        if image_path and self.settings.use_vision_observation:
            try:
                from src.nlp.claim_extractor import observe_figure
                observations = observe_figure(image_path, caption,
                                              figure["label"],
                                              client=self._llm_client)
            except Exception as exc:  # noqa: BLE001
                logger.warning("figure vision observation failed on %s: %s",
                               figure["label"], exc)

        ve = (count_visual_elements(image_path)
              if image_path and observations is None else None)
        result = check_consistency(
            claims, image_path, prior_detector_flags=image_flags,
            visual_elements=ve, vision_observations=observations,
            panel_count_tolerance=self.settings.panel_count_tolerance,
            fold_prior_flags=False)  # risk scorer already scores those detectors
        return {"status": "ok", "consistent": result["consistent"],
                "mismatches": result["mismatches"], "confidence": result["confidence"],
                "detector_context": result.get("detector_context", []),
                "observations": observations, "claims": claims}


def _load(image_path: str):
    from src.utils.image_io import load_image
    return load_image(image_path)


def _cat_ge(a: str, b: str) -> bool:
    """True if category a is at least as severe as category b."""
    order = RISK_CATEGORIES
    return order.index(a) >= order.index(b) if a in order and b in order else False


# --------------------------------------------------------------------------
# Public functional entry point
# --------------------------------------------------------------------------
def run_pipeline(pdf_path: str,
                 config_path: str | None = None,
                 output_dir: str | None = None,
                 llm_client=_AUTO) -> dict:
    """Run the unified ScholarGuard pipeline on one paper PDF.

    Args:
        pdf_path: path to the paper PDF.
        config_path: config.yaml path (defaults to src/config/config.yaml).
        output_dir: where to write the report (defaults to config's output_dir).
        llm_client: injectable for tests; default builds one from settings and
            degrades to skipping claim-consistency if no API key is present.

    Returns the full report dict (also written to disk as JSON + Markdown).
    Never raises for a bad/corrupt/empty PDF — those come back as a report
    with status "failed" / "completed_no_figures".
    """
    from src.config.settings import ConfigError
    try:
        settings = load_settings(config_path or _default_config_path())
    except ConfigError as exc:
        logger.error("configuration error: %s", exc)
        raise  # a broken config is a programmer error, surface it clearly

    pipeline = Pipeline(settings, llm_client=llm_client)
    return pipeline.analyze(pdf_path, output_dir=output_dir)


def _default_config_path() -> str:
    from src.config.settings import DEFAULT_CONFIG_PATH
    return DEFAULT_CONFIG_PATH

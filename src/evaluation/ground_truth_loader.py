"""Load and validate the labeled evaluation set (Stage 7).

``labels.json`` schema::

    {
      "dataset_name": "...",
      "note": "...",                       # provenance / caveats
      "papers": [
        {
          "paper_id": "fraud_copymove_01",
          "pdf_path": "data/evaluation_set/fraud_cases/fraud_copymove_01.pdf",
          "is_fraudulent": true,
          "label_confidence": "confirmed",  # confirmed | disputed
          "figures": [
            {"figure_num": 1, "fraud_type": "copy_move",
             "label_confidence": "confirmed"},
            {"figure_num": 2, "fraud_type": "none"}
          ]
        }
      ]
    }

``fraud_type`` is one of: copy_move, cross_figure, ai_generated,
claim_mismatch, none. Missing PDFs are **warned** about (and marked
``pdf_exists: false``), not fatal — a partial evaluation set still runs.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("scholarguard.eval")

VALID_FRAUD_TYPES = {"copy_move", "cross_figure", "ai_generated",
                     "claim_mismatch", "none"}
VALID_LABEL_CONFIDENCE = {"confirmed", "disputed"}


class GroundTruthError(RuntimeError):
    """Raised only for structurally invalid labels.json (not missing PDFs)."""


def load_evaluation_set(labels_path: str) -> dict:
    """Load, validate, and return the structured ground-truth evaluation set.

    Returns ``{"dataset_name", "note", "papers": [...], "warnings": [...]}``
    where each paper gains ``pdf_exists`` (bool). Papers whose PDF is missing
    are kept (so counts are honest) but flagged; the benchmark skips them.
    """
    if not os.path.isfile(labels_path):
        raise GroundTruthError(f"labels file not found: {labels_path}")
    with open(labels_path, encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise GroundTruthError(f"labels.json is not valid JSON: {exc}") from exc

    if "papers" not in raw or not isinstance(raw["papers"], list):
        raise GroundTruthError("labels.json must contain a 'papers' list")

    base_dir = os.path.dirname(os.path.abspath(labels_path))
    warnings: list[str] = []
    papers: list[dict] = []
    seen_ids: set[str] = set()

    for i, paper in enumerate(raw["papers"]):
        pid = paper.get("paper_id")
        if not pid:
            raise GroundTruthError(f"paper #{i} is missing 'paper_id'")
        if pid in seen_ids:
            raise GroundTruthError(f"duplicate paper_id: {pid}")
        seen_ids.add(pid)

        if "is_fraudulent" not in paper:
            raise GroundTruthError(f"paper '{pid}' missing 'is_fraudulent'")

        # Resolve pdf_path relative to the labels file if not absolute.
        pdf_path = paper.get("pdf_path", "")
        resolved = pdf_path if os.path.isabs(pdf_path) else \
            os.path.normpath(os.path.join(base_dir, "..", "..", pdf_path)) \
            if not os.path.isfile(pdf_path) else pdf_path
        # Prefer the path as given if it exists; else the resolved one.
        pdf_exists = os.path.isfile(pdf_path) or os.path.isfile(resolved)
        effective = pdf_path if os.path.isfile(pdf_path) else resolved
        if not pdf_exists:
            msg = f"PDF for '{pid}' not found: {pdf_path}"
            warnings.append(msg)
            logger.warning(msg)

        conf = paper.get("label_confidence", "confirmed")
        if conf not in VALID_LABEL_CONFIDENCE:
            raise GroundTruthError(
                f"paper '{pid}' has invalid label_confidence '{conf}'")

        figures = []
        for fig in paper.get("figures", []):
            ftype = fig.get("fraud_type", "none")
            if ftype not in VALID_FRAUD_TYPES:
                raise GroundTruthError(
                    f"paper '{pid}' figure {fig.get('figure_num')} has invalid "
                    f"fraud_type '{ftype}' (valid: {sorted(VALID_FRAUD_TYPES)})")
            figures.append({
                "figure_num": fig.get("figure_num"),
                "fraud_type": ftype,
                "label_confidence": fig.get("label_confidence", conf),
            })

        papers.append({
            "paper_id": pid,
            "pdf_path": effective,
            "pdf_exists": pdf_exists,
            "is_fraudulent": bool(paper["is_fraudulent"]),
            "label_confidence": conf,
            "figures": figures,
        })

    n_missing = sum(1 for p in papers if not p["pdf_exists"])
    logger.info("loaded %d paper(s) from %s (%d fraudulent, %d missing PDFs)",
                len(papers), labels_path,
                sum(p["is_fraudulent"] for p in papers), n_missing)

    return {
        "dataset_name": raw.get("dataset_name", "unnamed"),
        "note": raw.get("note", ""),
        "papers": papers,
        "warnings": warnings,
    }


def fraud_type_for_figure(paper: dict, figure_num) -> str:
    """Ground-truth fraud_type for a figure number (default 'none')."""
    for fig in paper.get("figures", []):
        if fig.get("figure_num") == figure_num:
            return fig["fraud_type"]
    return "none"

"""Assemble ``labels.json`` for Stage 7 from collected fraud + clean papers.

The schema is dictated by :mod:`src.evaluation.ground_truth_loader` — this
module matches it exactly rather than inventing a new one::

    {"dataset_name": str, "note": str,
     "papers": [{"paper_id", "pdf_path", "is_fraudulent",
                 "label_confidence", "figures": [...]}]}

Each figure entry is ``{"figure_num", "fraud_type", "label_confidence"}`` with
``fraud_type`` restricted to the loader's enum.

**Figure-level locations are NOT annotated.** Retraction Watch reports why a
*paper* was retracted, never which figure was manipulated. We therefore emit a
single figure entry with ``figure_num: null`` — we never guess a figure number.
Extra keys (``doi``, ``title``, ``retraction_reason``, ``subset``) are carried
for human review; the loader ignores unknown keys.
"""

from __future__ import annotations

import json
import os
import tempfile

# Mirrors ground_truth_loader.VALID_* so a malformed entry fails here, early.
VALID_FRAUD_TYPES = {"copy_move", "cross_figure", "ai_generated",
                     "claim_mismatch", "none"}
VALID_LABEL_CONFIDENCE = {"confirmed", "disputed"}

CATEGORY_FRAUD = "fraud"
CATEGORY_CLEAN = "clean"

# Provenance of a labels entry. Real entries (downloaded from PMC via
# fetch_evaluation_set.py) are expensive to rebuild and must never be silently
# clobbered by the synthetic generator — see has_real_entries().
SOURCE_REAL = "real"
SOURCE_SYNTHETIC = "synthetic"
VALID_SOURCES = {SOURCE_REAL, SOURCE_SYNTHETIC}

FIGURE_LEVEL_NOTE = ("paper-level label only; the specific manipulated "
                     "figure is NOT annotated and requires manual review")


def build_labels_entry(pmcid: str, doi: str, title: str, category: str,
                       fraud_type: str | None = None,
                       label_confidence: str | None = None,
                       *, pdf_path: str | None = None,
                       retraction_reason: str | None = None,
                       subset: str | None = None,
                       source: str = SOURCE_REAL) -> dict:
    """Build one schema-valid ``papers[]`` entry.

    ``category`` is ``"fraud"`` or ``"clean"``. For fraud papers a single
    figure entry with ``figure_num=None`` carries the coarse ``fraud_type``;
    clean papers carry no figure entries (the loader defaults them to "none").

    ``source`` records provenance (``"real"`` | ``"synthetic"``) so generated
    data can never be mistaken for — or silently overwrite — downloaded data.
    """
    if category not in (CATEGORY_FRAUD, CATEGORY_CLEAN):
        raise ValueError(f"category must be 'fraud' or 'clean', got {category!r}")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}, "
                         f"got {source!r}")

    is_fraud = category == CATEGORY_FRAUD
    confidence = label_confidence or ("confirmed" if is_fraud else "confirmed")
    if confidence not in VALID_LABEL_CONFIDENCE:
        raise ValueError(f"invalid label_confidence: {confidence!r}")

    figures: list[dict] = []
    if is_fraud:
        ftype = fraud_type or "copy_move"
        if ftype not in VALID_FRAUD_TYPES:
            raise ValueError(f"invalid fraud_type: {ftype!r}")
        figures = [{
            "figure_num": None,          # never guessed — see module docstring
            "fraud_type": ftype,
            "label_confidence": confidence,
            "note": FIGURE_LEVEL_NOTE,
        }]

    entry = {
        "paper_id": pmcid,
        "pdf_path": (pdf_path or "").replace("\\", "/"),
        "is_fraudulent": is_fraud,
        "label_confidence": confidence,
        "figures": figures,
        # Extra provenance (ignored by the loader, kept for reviewers):
        "source": source,
        "doi": doi,
        "title": title,
    }
    if retraction_reason:
        entry["retraction_reason"] = retraction_reason
    if subset:
        entry["subset"] = subset
    return entry


class RealDataOverwriteError(RuntimeError):
    """Raised when a write would destroy real (downloaded) evaluation labels."""


def count_real_entries(labels_path: str) -> int:
    """How many ``source: "real"`` papers an existing labels.json holds.

    Returns 0 if the file is absent or unreadable. Entries written before the
    ``source`` field existed are treated as NOT real (the only pre-``source``
    labels.json in this project was synthetic), so the guard never blocks on
    ambiguity it cannot resolve.
    """
    if not os.path.isfile(labels_path):
        return 0
    try:
        with open(labels_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return 0
    papers = data.get("papers", []) if isinstance(data, dict) else []
    return sum(1 for p in papers if p.get("source") == SOURCE_REAL)


def assert_safe_to_overwrite(labels_path: str, force: bool = False) -> None:
    """Refuse to clobber a labels.json that contains real downloaded entries.

    Real entries cost thousands of rate-limited NCBI requests to rebuild, so a
    stray ``make_eval_set.py`` run must not silently destroy them.
    """
    n_real = count_real_entries(labels_path)
    if n_real == 0 or force:
        return
    raise RealDataOverwriteError(
        f"refusing to overwrite '{labels_path}': it contains {n_real} REAL "
        f"evaluation entr{'y' if n_real == 1 else 'ies'} downloaded from PMC.\n"
        f"Overwriting would destroy data that takes thousands of rate-limited "
        f"NCBI requests to rebuild (retracted papers have ~0.7% OA PDF "
        f"availability).\n"
        f"If you really mean to replace it with synthetic data, re-run with "
        f"--force.")


def write_labels_json(entries: list[dict], output_path: str,
                      dataset_name: str = "scholarguard_real_eval_v1",
                      note: str | None = None) -> None:
    """Write the full labels.json atomically (temp file + rename)."""
    n_fraud = sum(1 for e in entries if e.get("is_fraudulent"))
    default_note = (
        "REAL evaluation set. Fraud cases are formal retractions from the "
        "Retraction Watch database (Crossref) whose stated reason concerns "
        "image integrity; PDFs fetched from the PMC Open Access subset. Clean "
        "controls are PMC OA papers cross-checked against the FULL Retraction "
        "Watch DOI list (all retractions, not just image-related). "
        "IMPORTANT: labels are PAPER-LEVEL only — figure_num is null for every "
        "fraud case because Retraction Watch does not identify which figure was "
        "manipulated. Per-detector, figure-level metrics therefore require "
        "manual figure annotation first; paper-level metrics are valid as-is."
    )
    payload = {
        "dataset_name": dataset_name,
        "note": note or default_note,
        "n_fraud": n_fraud,
        "n_clean": len(entries) - n_fraud,
        "papers": entries,
    }

    directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, output_path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

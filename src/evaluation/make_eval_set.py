"""Generate a *synthetic stand-in* evaluation set for Stage 7 + its labels.json.

IMPORTANT HONESTY NOTE: these are synthetic papers, NOT real documented fraud.
Stage 1's genuine held-out fraud cases were never present in this repo, so this
generator builds a labeled stand-in set that (a) exercises the full pipeline
end-to-end and (b) includes realistic false-positive traps (dose-response
series of legitimately-similar figures). Metrics computed on it are REAL
pipeline metrics on synthetic data — to evaluate on real fraud, drop genuine
PDFs into data/evaluation_set/{fraud_cases,clean_control_papers}/ and label
them in labels.json (this file is not needed once real data is present).

Fraud types covered: copy_move, cross_figure, ai_generated, claim_mismatch.
"""

from __future__ import annotations

import json
import os
import tempfile

import cv2
import fitz  # PyMuPDF
import numpy as np

from src.utils.synth import (
    apply_copy_move,
    apply_generative_artifacts,
    make_base_figure,
)

FRAUD_DIR = "data/evaluation_set/fraud_cases"
CLEAN_DIR = "data/evaluation_set/clean_control_papers"
LABELS_PATH = "data/evaluation_set/labels.json"

_LOREM = ("Cells were cultured under standard conditions and processed for "
          "analysis. Protein was extracted and separated by electrophoresis. "
          "Quantification was performed with standard densitometry software. "
          "Error bars represent mean +/- SEM across independent replicates.")


def _distinct_blot(rng, n_lanes, size=(300, 420)):
    """A blot with a unique textured background + n clear dark lanes."""
    h, w = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    gray = np.full((h, w), 216.0, np.float32)
    gray += rng.uniform(4, 9) * np.sin(xx / w * np.pi * rng.uniform(0.5, 2.5)
                                       + rng.uniform(0, 6))
    gray += rng.uniform(3, 7) * np.cos(yy / h * np.pi * rng.uniform(0.5, 2.5)
                                       + rng.uniform(0, 6))
    gray += 6.0 * cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32),
                                   (0, 0), 2.0)
    margin, usable = int(w * 0.08), int(w * 0.84)
    for i in range(n_lanes):
        cx = margin + int((i + 0.5) * usable / n_lanes)
        cy = int(h * rng.uniform(0.4, 0.6))
        band = np.zeros((h, w), np.float32)
        cv2.ellipse(band, (cx, cy), (max(6, usable // (n_lanes * 3)), 13),
                    0, 0, 360, float(rng.uniform(120, 170)), -1)
        gray -= cv2.GaussianBlur(band, (0, 0), 2.0)
    gray += rng.normal(0, 3, (h, w)).astype(np.float32)
    return cv2.cvtColor(np.clip(gray, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def _dose_response_series(rng, n, size=(300, 420)):
    """A LEGITIMATE dose-response series: same layout, increasing band intensity.

    These figures are genuinely similar by design (same assay, rising dose) —
    the classic false-positive trap for a cross-figure reuse detector. They are
    NOT fraud.
    """
    base = _distinct_blot(rng, n_lanes=4, size=size)
    series = []
    for i in range(n):
        img = base.copy().astype(np.float32)
        # Darken the bands progressively (higher dose -> stronger signal).
        darker = img - i * 12.0
        # Add fresh per-figure sensor noise so they're not pixel-identical.
        darker += rng.normal(0, 3, img.shape[:2])[..., None]
        series.append(np.clip(darker, 0, 255).astype(np.uint8))
    return series


def _crop_panel(img, rng):
    """Crop a content-rich sub-panel (for within-paper reuse forgery)."""
    h, w = img.shape[:2]
    ph, pw = int(h * 0.4), int(w * 0.4)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    best, sy, sx = -1, 0, 0
    for _ in range(30):
        cy, cx = int(rng.integers(0, h - ph)), int(rng.integers(0, w - pw))
        s = float(gray[cy:cy + ph, cx:cx + pw].std())
        if s > best:
            best, sy, sx = s, cy, cx
    return img[sy:sy + ph, sx:sx + pw].copy()


def _build_pdf(pdf_path, title, figures):
    """Write a paper PDF: title + text sections + embedded figures/captions.

    ``figures`` is a list of ``(caption_text, image_bgr)``. Captions start with
    'Figure N.' so the Stage 5 parser extracts them; an inline reference to
    each figure is added to the Results text.
    """
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="eval_fig_")
    img_paths = []
    for i, (_, img) in enumerate(figures):
        p = os.path.join(scratch, f"f{i}.png")
        cv2.imwrite(p, img)
        img_paths.append(p)

    doc = fitz.open()
    page = doc.new_page()
    margin, y = 56, 56
    width = page.rect.width - 2 * margin

    def write(text, size, gap, bold=False):
        nonlocal y, page
        font = "hebo" if bold else "helv"
        bottom = page.rect.height - margin
        while True:
            # Start a fresh page if there isn't room for even one line.
            if bottom - y < size * 2:
                page = doc.new_page()
                y, bottom = margin, page.rect.height - margin
            box = fitz.Rect(margin, y, margin + width, bottom)
            rc = page.insert_textbox(box, text, fontsize=size, fontname=font)
            if rc < 0:  # text didn't fit in the remaining box -> new page, retry
                page = doc.new_page()
                y, bottom = margin, page.rect.height - margin
                continue
            consumed = (bottom - y) - rc  # box height minus unused space
            y += max(consumed, size * 1.4) + gap
            return

    refs = " ".join(f"Figure {i + 1}" for i in range(len(figures)))
    write(title, 15, 6, bold=True)
    write("A. Author, B. Author (ScholarGuard synthetic evaluation set)", 9, 12)
    write("Abstract", 12, 3, bold=True)
    write(f"We present analyses summarized in {refs}. {_LOREM}", 10, 8)
    write("Methods", 12, 3, bold=True)
    write(_LOREM, 10, 8)
    write("Results", 12, 3, bold=True)
    write(f"Key findings are shown in {refs}. Band intensities were quantified "
          f"and compared across conditions. {_LOREM}", 10, 8)

    for i, (caption, _) in enumerate(figures):
        if y > page.rect.height - 260:
            page = doc.new_page()
            y = margin
        rect = fitz.Rect(margin, y, margin + 210, y + 150)
        page.insert_image(rect, filename=img_paths[i])
        y += 158
        write(caption, 9, 12)

    doc.save(pdf_path)
    doc.close()
    for p in img_paths:
        os.remove(p)
    os.rmdir(scratch)


def generate_evaluation_set(seed: int = 2026, force: bool = False) -> dict:
    """Generate all fraud + clean papers and write labels.json. Returns labels.

    Refuses to run if ``LABELS_PATH`` already holds REAL downloaded entries
    (see labels_builder.assert_safe_to_overwrite) unless ``force`` is set —
    real data costs thousands of rate-limited NCBI requests to rebuild.
    """
    from src.data_acquisition.labels_builder import assert_safe_to_overwrite

    # Check BEFORE generating anything, so we never write stray PDFs either.
    assert_safe_to_overwrite(LABELS_PATH, force=force)

    rng = np.random.default_rng(seed)
    os.makedirs(FRAUD_DIR, exist_ok=True)
    os.makedirs(CLEAN_DIR, exist_ok=True)
    papers = []

    def add(paper_id, folder, title, figures, is_fraud, fig_labels, conf="confirmed"):
        path = os.path.join(folder, f"{paper_id}.pdf")
        _build_pdf(path, title, figures)
        papers.append({
            "source": "synthetic",   # never mistaken for downloaded data
            "paper_id": paper_id, "pdf_path": path.replace("\\", "/"),
            "is_fraudulent": is_fraud, "label_confidence": conf,
            "figures": [{"figure_num": n, "fraud_type": t,
                         "label_confidence": conf} for n, t in fig_labels],
        })

    cap = lambda n, txt: f"Figure {n}. {txt}"

    # -------- FRAUD: copy-move (duplicated region within one figure) --------
    for k in (1, 2):
        forged, _ = apply_copy_move(make_base_figure(rng, size=(300, 420)), rng,
                                    patch_size=(70, 90))
        clean = _distinct_blot(rng, n_lanes=5)
        add(f"fraud_copymove_{k:02d}", FRAUD_DIR,
            "Expression of Marker Protein After Treatment",
            [(cap(1, "Microscopy field of treated cells (n = 6)."), forged),
             (cap(2, "Control field (n = 6)."), clean)],
            True, [(1, "copy_move"), (2, "none")])

    # -------- FRAUD: cross-figure reuse (panel of Fig1 pasted into Fig2) ----
    for k in (1, 2):
        fig1 = _distinct_blot(rng, n_lanes=4)
        panel = _crop_panel(fig1, rng)
        # Slight brightness change, as a fraudster disguising a reused panel.
        panel = np.clip(panel.astype(np.float32) * 1.05 - 4, 0, 255).astype(np.uint8)
        fig2 = _distinct_blot(rng, n_lanes=4)
        py, px = 40, 40
        fig2[py:py + panel.shape[0], px:px + panel.shape[1]] = panel
        add(f"fraud_crossfig_{k:02d}", FRAUD_DIR,
            "Comparative Blot Analysis Across Conditions",
            [(cap(1, "Blot under condition A (n = 4)."), fig1),
             (cap(2, "Blot under condition B (n = 4)."), fig2)],
            True, [(1, "none"), (2, "cross_figure")])

    # -------- FRAUD: AI-generated figure ----------------------------------
    for k in (1, 2):
        ai = apply_generative_artifacts(make_base_figure(rng, size=(300, 420)), rng)
        clean = _distinct_blot(rng, n_lanes=5)
        add(f"fraud_aigen_{k:02d}", FRAUD_DIR,
            "Representative Micrographs of Cellular Structures",
            [(cap(1, "Representative micrograph (n = 6)."), ai),
             (cap(2, "Quantification blot (n = 6)."), clean)],
            True, [(1, "ai_generated"), (2, "none")])

    # -------- FRAUD: claim mismatch (caption overstates lane count) --------
    for k, (lanes, claimed) in enumerate([(4, 12), (3, 9)], start=1):
        blot = _distinct_blot(rng, n_lanes=lanes)
        clean = _distinct_blot(rng, n_lanes=4)
        add(f"fraud_claim_{k:02d}", FRAUD_DIR,
            "Quantitative Western Blot of Protein Expression",
            [(cap(1, f"Western blot across {claimed} treatment conditions "
                    f"(n = {claimed} lanes)."), blot),
             (cap(2, "Loading control (n = 4)."), clean)],
            True, [(1, "claim_mismatch"), (2, "none")],
            conf="disputed")  # a text/image count gap is weaker evidence

    # -------- CLEAN: ordinary legitimate papers ---------------------------
    for k in range(1, 4):
        figs = [(cap(1, "Blot for assay one (n = 5)."), _distinct_blot(rng, 5)),
                (cap(2, "Blot for assay two (n = 5)."), _distinct_blot(rng, 3))]
        add(f"clean_normal_{k:02d}", CLEAN_DIR,
            "Standard Characterization of Protein Complexes", figs,
            False, [(1, "none"), (2, "none")])

    # -------- CLEAN: dose-response series (FALSE-POSITIVE TRAP) ------------
    # Legitimately similar figures (same assay, increasing dose) that a naive
    # cross-figure detector may wrongly flag as reuse. These are NOT fraud.
    for k in range(1, 4):
        series = _dose_response_series(rng, n=3)
        figs = [(cap(i + 1, f"Dose-response at {d} uM (n = 4)."), series[i])
                for i, d in enumerate([1, 10, 100])]
        add(f"clean_doseresponse_{k:02d}", CLEAN_DIR,
            "Dose-Dependent Response of Marker Expression", figs,
            False, [(1, "none"), (2, "none"), (3, "none")])

    labels = {
        "dataset_name": "scholarguard_synthetic_eval_v1",
        "note": ("SYNTHETIC stand-in evaluation set (NOT real documented "
                 "fraud). Generated by src/evaluation/make_eval_set.py. Includes "
                 "dose-response series as legitimate-similarity false-positive "
                 "traps. Replace with real held-out PDFs for real-fraud metrics."),
        "papers": papers,
    }
    with open(LABELS_PATH, "w", encoding="utf-8") as fh:
        json.dump(labels, fh, indent=2)
    return labels


def main(argv=None) -> int:
    import argparse
    import sys

    from src.data_acquisition.labels_builder import RealDataOverwriteError

    parser = argparse.ArgumentParser(
        description="generate the SYNTHETIC stand-in evaluation set")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--force", action="store_true",
                        help="overwrite labels.json even if it holds REAL "
                             "downloaded evaluation entries (destructive)")
    args = parser.parse_args(argv)

    try:
        lab = generate_evaluation_set(seed=args.seed, force=args.force)
    except RealDataOverwriteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    n_fraud = sum(p["is_fraudulent"] for p in lab["papers"])
    print(f"wrote {len(lab['papers'])} papers "
          f"({n_fraud} fraud, {len(lab['papers']) - n_fraud} clean) + {LABELS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _legacy_entrypoint():  # pragma: no cover - retained for reference
    lab = generate_evaluation_set()
    n_fraud = sum(p["is_fraudulent"] for p in lab["papers"])
    print(f"wrote {len(lab['papers'])} papers "
          f"({n_fraud} fraud, {len(lab['papers']) - n_fraud} clean) + {LABELS_PATH}")

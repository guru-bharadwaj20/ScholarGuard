"""Generate a synthetic scientific-paper PDF for Stage 5 testing.

Produces a small PDF with real section structure (Abstract, Methods,
Results, Discussion), inline figure references, figure captions, and
*embedded raster figure images* (blot/microscopy-style, from the Stage 1
synth generator). One figure carries a deliberate claim/image mismatch (the
caption claims more lanes than the image shows) so the consistency checker
has something to catch end-to-end.

This is a **stand-in** for real open-access papers so the pipeline can be
tested offline. Drop genuine PDFs into ``data/sample_papers/`` to run on real
papers — nothing here is required at runtime.
"""

from __future__ import annotations

import os

import cv2
import fitz  # PyMuPDF
import numpy as np

from src.utils.synth import make_base_figure


def _blot_with_lanes(rng: np.random.Generator, n_lanes: int,
                     size: tuple[int, int] = (240, 420)) -> np.ndarray:
    """A blot-style figure with a controllable number of dark vertical lanes.

    Each figure gets a distinct low-frequency background shading + grain so
    that two different figures in the same paper are NOT near-duplicates (a
    flat identical background would spuriously trip the Stage 3 cross-figure
    detector). The lanes remain the dominant, clearly-countable feature.
    """
    h, w = size
    # Unique low-frequency background per figure (different phase/amplitude).
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    gray = np.full((h, w), 218.0, np.float32)
    gray += rng.uniform(4, 9) * np.sin(xx / w * np.pi * rng.uniform(0.5, 2.5)
                                       + rng.uniform(0, 6))
    gray += rng.uniform(3, 7) * np.cos(yy / h * np.pi * rng.uniform(0.5, 2.5)
                                       + rng.uniform(0, 6))
    gray += 6.0 * cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32),
                                   (0, 0), 2.0)  # unique medium-freq grain

    margin = int(w * 0.08)
    usable = w - 2 * margin
    for i in range(n_lanes):
        cx = margin + int((i + 0.5) * usable / n_lanes)
        cy = int(h * rng.uniform(0.4, 0.6))
        band = np.zeros((h, w), np.float32)
        cv2.ellipse(band, (cx, cy), (max(6, usable // (n_lanes * 3)), 12),
                    0, 0, 360, float(rng.uniform(120, 170)), -1)
        band = cv2.GaussianBlur(band, (0, 0), 2.0)
        gray -= band
    gray += rng.normal(0, 3, (h, w)).astype(np.float32)
    out = np.clip(gray, 0, 255).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)


# Paper text. {figN} placeholders are where images get inserted. The Figure 1
# caption deliberately overstates the lane count (says 12, image has 4).
_PAPER = {
    "title": "Synthetic Expression Analysis of Protein X Under Stress Conditions",
    "authors": "A. Researcher, B. Coauthor  (ScholarGuard synthetic test corpus)",
    "sections": [
        ("Abstract",
         "We report the expression of Protein X across multiple stress "
         "conditions. Western blot and microscopy analyses (Figure 1, Figure 2) "
         "demonstrate condition-dependent modulation. Quantification indicates a "
         "2.5-fold increase relative to control (p < 0.001, n = 6 independent "
         "replicates)."),
        ("Methods",
         "Cells were cultured under standard conditions. Protein was extracted "
         "and separated by SDS-PAGE. Western blots were performed with n = 6 "
         "independent biological replicates per condition. Band intensities were "
         "quantified with ImageJ. Error bars in all figures represent mean +/- "
         "SEM. Statistical significance was assessed by two-tailed t-test."),
        ("Results",
         "Protein X expression increased markedly under stress. As shown in "
         "Figure 1, we resolved 12 independent lanes corresponding to 12 "
         "treatment conditions, each showing distinct band intensity. "
         "Densitometry revealed a 2.5-fold increase over control (p < 0.001). "
         "Figure 2 shows representative microscopy fields with consistent "
         "sub-cellular localization across all n = 6 replicates."),
        ("Discussion",
         "These findings suggest Protein X is stress-responsive. The magnitude "
         "of the effect (2.5-fold, p < 0.001) is consistent with prior reports. "
         "Limitations include the synthetic nature of this test dataset."),
    ],
    "figures": [
        {"num": 1, "lanes": 4,   # image shows 4 lanes...
         "caption": "Figure 1. Western blot of Protein X across 12 treatment "
                    "conditions (n = 12 lanes). Band intensity increases with "
                    "stress severity. Error bars represent mean +/- SEM."},
        {"num": 2, "lanes": 3,
         "caption": "Figure 2. Representative microscopy fields showing "
                    "sub-cellular localization of Protein X (n = 6 replicates, "
                    "3 conditions shown)."},
    ],
}


def generate_sample_paper(
    pdf_path: str = "data/sample_papers/synthetic_paper_01.pdf",
    seed: int = 7,
) -> str:
    """Write a synthetic paper PDF (text sections + embedded figures) to disk.

    Returns the PDF path. Figure 1 has a built-in claim/image mismatch
    (caption says 12 lanes; image shows 4).
    """
    rng = np.random.default_rng(seed)
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)

    # Render the figure images to a temp dir for embedding.
    scratch = os.path.join(os.path.dirname(os.path.abspath(pdf_path)), "_fig_tmp")
    os.makedirs(scratch, exist_ok=True)
    fig_images: dict[int, str] = {}
    for fig in _PAPER["figures"]:
        img = _blot_with_lanes(rng, fig["lanes"])
        img_path = os.path.join(scratch, f"fig{fig['num']}.png")
        cv2.imwrite(img_path, img)
        fig_images[fig["num"]] = img_path

    doc = fitz.open()
    page = doc.new_page()  # default A4
    margin = 56
    width = page.rect.width - 2 * margin
    y = margin

    def write(text: str, size: int, gap: int, bold: bool = False):
        nonlocal y, page
        font = "helv" if not bold else "hebo"
        rc = -1
        while rc < 0:  # insert_textbox returns <0 if it didn't fit
            box = fitz.Rect(margin, y, margin + width, page.rect.height - margin)
            rc = page.insert_textbox(box, text, fontsize=size, fontname=font,
                                     align=0)
            if rc < 0:
                page = doc.new_page()
                y = margin
        # Estimate consumed height from returned remaining space.
        used = (page.rect.height - margin) - (box.y1 - rc)
        y += max(used, size * 1.4) + gap

    write(_PAPER["title"], 15, 6, bold=True)
    write(_PAPER["authors"], 9, 14)

    for name, body in _PAPER["sections"]:
        write(name, 12, 4, bold=True)
        write(body, 10, 10)
        # After Results, embed the figures with their captions.
        if name == "Results":
            for fig in _PAPER["figures"]:
                if y > page.rect.height - 260:
                    page = doc.new_page()
                    y = margin
                img_w = 220
                rect = fitz.Rect(margin, y, margin + img_w, y + 130)
                page.insert_image(rect, filename=fig_images[fig["num"]])
                y += 138
                write(fig["caption"], 9, 12)

    doc.save(pdf_path)
    doc.close()

    # Clean up temp figure images (they're embedded in the PDF now).
    for path in fig_images.values():
        try:
            os.remove(path)
        except OSError:  # pragma: no cover
            pass
    try:
        os.rmdir(scratch)
    except OSError:  # pragma: no cover - not empty
        pass
    return pdf_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="generate a synthetic test paper PDF")
    parser.add_argument("--output", default="data/sample_papers/synthetic_paper_01.pdf")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    path = generate_sample_paper(args.output, seed=args.seed)
    print(f"wrote synthetic paper -> {path}")

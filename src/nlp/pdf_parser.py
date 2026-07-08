"""Extract text sections, figure captions, and figure images from a paper PDF.

Built on **PyMuPDF** (``fitz``) — chosen over pdfplumber because it extracts
embedded raster images as well as text, which the downstream detectors need.

What :func:`parse_paper` returns:

    {
        "sections": {"Abstract": "...", "Methods": "...", ...},
        "full_text": "...",
        "figures": [
            {"figure_num": 1, "label": "Figure 1", "caption": "...",
             "image_path": "outputs/.../paperX_fig1.png"},
            ...
        ],
    }

Caption/figure association is heuristic (regex on "Figure N" / "Fig. N" plus
nearest-image matching) and documented as approximate — real journal layouts
vary wildly. The parser degrades gracefully: a caption with no matching image
still appears (``image_path=None``), and vice-versa.
"""

from __future__ import annotations

import os
import re

import fitz  # PyMuPDF

# Section headers we try to split on (case-insensitive, line-leading).
SECTION_HEADERS = [
    "Abstract", "Introduction", "Background", "Related Work",
    "Methods", "Materials and Methods", "Methodology", "Experimental",
    "Results", "Results and Discussion", "Discussion",
    "Conclusion", "Conclusions", "References", "Acknowledgments",
]
# Matches "Figure 1", "Fig. 2", "Figure 3:" etc. at a caption start.
_FIG_CAPTION_RE = re.compile(
    r"(?im)^\s*(fig(?:ure)?\.?\s*(\d+))\s*[.:|)]?\s+(.+)"
)
# Inline figure reference like "(Figure 2)" or "Fig 2 shows".
_FIG_REF_RE = re.compile(r"(?i)\bfig(?:ure)?\.?\s*(\d+)\b")


def _extract_full_text(doc: "fitz.Document") -> str:
    """Concatenate the plain text of every page."""
    return "\n".join(page.get_text("text") for page in doc)


def split_sections(full_text: str) -> dict[str, str]:
    """Split a paper's text into a {section_name: body} dict (best-effort).

    Uses line-leading header matching. Everything before the first recognized
    header is stored under ``"_preamble"`` (title/authors/abstract lead-in).
    """
    # Build one regex that matches any known header on its own line.
    header_alt = "|".join(re.escape(h) for h in sorted(SECTION_HEADERS,
                                                        key=len, reverse=True))
    pattern = re.compile(rf"(?im)^\s*(?:\d+\.?\s*)?({header_alt})\s*:?\s*$")

    matches = list(pattern.finditer(full_text))
    if not matches:
        return {"_preamble": full_text.strip()}

    sections: dict[str, str] = {}
    if matches[0].start() > 0:
        sections["_preamble"] = full_text[: matches[0].start()].strip()
    for i, match in enumerate(matches):
        name = match.group(1).title()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        # Merge duplicate/aliased headers (e.g. two "Results" blocks).
        sections[name] = (sections.get(name, "") + "\n" + body).strip()
    return sections


def extract_captions(full_text: str) -> dict[int, str]:
    """Find figure captions in the text, keyed by figure number.

    A caption is a line starting with 'Figure N' / 'Fig. N' followed by
    descriptive text. The caption body runs until the next blank line or the
    next figure caption (whichever comes first).
    """
    captions: dict[int, str] = {}
    lines = full_text.splitlines()
    for idx, line in enumerate(lines):
        m = _FIG_CAPTION_RE.match(line)
        if not m:
            continue
        fig_num = int(m.group(2))
        body = [m.group(3).strip()]
        # Greedily absorb continuation lines until a blank or a new caption.
        for cont in lines[idx + 1:]:
            if not cont.strip() or _FIG_CAPTION_RE.match(cont):
                break
            body.append(cont.strip())
        caption = " ".join(body).strip()
        # Keep the longest caption if the same number appears twice.
        if len(caption) > len(captions.get(fig_num, "")):
            captions[fig_num] = caption
    return captions


def get_results_context(full_text: str, figure_num: int,
                        window: int = 600) -> str:
    """Return text near every in-body mention of ``Figure N``.

    Concatenates a character window around each inline reference (excluding
    the caption itself), giving the claim extractor the sentences that
    actually discuss the figure's data.
    """
    chunks: list[str] = []
    for m in _FIG_REF_RE.finditer(full_text):
        if int(m.group(1)) != figure_num:
            continue
        start = max(0, m.start() - window // 2)
        end = min(len(full_text), m.end() + window // 2)
        snippet = full_text[start:end].strip()
        # Skip snippets that are just the caption (start-of-line "Figure N …").
        if _FIG_CAPTION_RE.match(snippet):
            continue
        chunks.append(snippet)
    # De-duplicate overlapping windows while preserving order.
    seen: set[str] = set()
    unique = [c for c in chunks if not (c in seen or seen.add(c))]
    return "\n[...]\n".join(unique[:6])


def _extract_images(doc: "fitz.Document", output_dir: str, stem: str,
                    min_dim: int = 80) -> list[dict]:
    """Save embedded raster images and record page + vertical position.

    Returns [{"image_path", "page", "y"}] sorted in reading order. Tiny
    images (icons, logos, math glyphs) below ``min_dim`` are skipped.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved: list[dict] = []
    counter = 0
    for page_index, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:  # pragma: no cover - malformed xref
                rects = []
            y = rects[0].y0 if rects else 0.0
            pix = fitz.Pixmap(doc, xref)
            if pix.width < min_dim or pix.height < min_dim:
                continue
            if pix.n >= 5:  # CMYK/alpha -> convert to RGB
                pix = fitz.Pixmap(fitz.csRGB, pix)
            path = os.path.join(output_dir, f"{stem}_img{counter:02d}.png")
            pix.save(path)
            saved.append({"image_path": path, "page": page_index, "y": float(y)})
            counter += 1
    saved.sort(key=lambda d: (d["page"], d["y"]))
    return saved


def parse_paper(pdf_path: str, output_dir: str | None = None) -> dict:
    """Parse a paper PDF into sections + figures (text, caption, image).

    ``output_dir`` receives the extracted figure images (defaults to
    ``outputs/stage5_results/<paper_stem>_figures``).
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir = output_dir or os.path.join("outputs", "stage5_results",
                                             f"{stem}_figures")

    doc = fitz.open(pdf_path)
    try:
        full_text = _extract_full_text(doc)
        sections = split_sections(full_text)
        captions = extract_captions(full_text)
        images = _extract_images(doc, output_dir, stem)
    finally:
        doc.close()

    # Associate captions with images in reading order. Both lists are already
    # ordered top-to-bottom; we pair the k-th figure caption with the k-th
    # extracted image, which holds for the common one-image-per-figure layout.
    fig_nums = sorted(captions)
    figures: list[dict] = []
    for i, fig_num in enumerate(fig_nums):
        image_path = images[i]["image_path"] if i < len(images) else None
        figures.append({
            "figure_num": fig_num,
            "label": f"Figure {fig_num}",
            "caption": captions[fig_num],
            "image_path": image_path,
            "results_context": get_results_context(full_text, fig_num),
        })
    # If there are images with no caption at all, still surface them so the
    # forensic detectors can run on every figure in the paper.
    for extra in images[len(fig_nums):]:
        figures.append({
            "figure_num": None,
            "label": f"(uncaptioned figure, page {extra['page'] + 1})",
            "caption": "",
            "image_path": extra["image_path"],
            "results_context": "",
        })

    return {"sections": sections, "full_text": full_text, "figures": figures}

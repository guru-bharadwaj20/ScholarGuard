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

import hashlib
import os
import re

import fitz  # PyMuPDF
import numpy as np

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


# Publisher furniture (logos, license badges, decorative rules) recurs on
# many pages; a real data figure does not. Images whose bytes appear on more
# than this many pages are dropped.
_FURNITURE_MAX_PAGES = 2
# Intensity-histogram entropy (bits) below which an image is treated as
# decoration (solid bars, simple logos) rather than figure content.
_MIN_CONTENT_ENTROPY = 1.0
# Aspect ratios beyond this are decorative rules/borders, not figures.
_MAX_ASPECT = 20.0


def _pix_entropy(pix: "fitz.Pixmap") -> float:
    """Shannon entropy (bits) of a Pixmap's gray histogram."""
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    try:
        arr = arr.reshape(pix.height, pix.width, pix.n)[:, :, : min(pix.n, 3)]
    except ValueError:  # unexpected stride; fall back to flat samples
        pass
    gray = arr.mean(axis=-1) if arr.ndim == 3 else arr.astype(np.float64)
    hist = np.bincount(np.clip(gray, 0, 255).astype(np.uint8).ravel(),
                       minlength=256).astype(np.float64)
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _save_figure_pixmap(doc: "fitz.Document", xref: int, output_dir: str,
                        stem: str, counter: int, min_dim: int) -> str | None:
    """Save one embedded image if it survives the junk filters, else None.

    Owns the Pixmap's lifetime: it is released before returning on every path,
    including the rejections, so decoded rasters do not accumulate across a
    long document.
    """
    pix = fitz.Pixmap(doc, xref)
    try:
        if pix.width < min_dim or pix.height < min_dim:
            return None
        aspect = max(pix.width, pix.height) / max(min(pix.width, pix.height), 1)
        if aspect > _MAX_ASPECT:
            return None
        if pix.n >= 5:  # CMYK/alpha -> convert to RGB
            converted = fitz.Pixmap(fitz.csRGB, pix)
            del pix            # release the source before rebinding the name
            pix = converted
        if _pix_entropy(pix) < _MIN_CONTENT_ENTROPY:
            return None
        path = os.path.join(output_dir, f"{stem}_img{counter:02d}.png")
        pix.save(path)
        return path
    finally:
        del pix


def _extract_images(doc: "fitz.Document", output_dir: str, stem: str,
                    min_dim: int = 80) -> list[dict]:
    """Save embedded raster images with their page + placement rect.

    Returns [{"image_path", "page", "y", "rect"}] sorted in reading order.
    Skipped as non-figure content: tiny images (icons, math glyphs),
    extreme-aspect strips (decorative rules), low-entropy images (logos,
    badges), and any image whose identical bytes recur on more than
    ``_FURNITURE_MAX_PAGES`` pages (running headers/footers, watermarks) —
    previously those matched each other *exactly* in the cross-figure
    detector and produced guaranteed false duplicate flags.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Pass 1: how many pages does each distinct image appear on?
    digest_pages: dict[str, set[int]] = {}
    digest_of: dict[int, str] = {}
    for page_index, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            if xref not in digest_of:
                try:
                    raw = doc.extract_image(xref)["image"]
                except Exception:  # pragma: no cover - malformed xref
                    continue
                digest_of[xref] = hashlib.md5(raw).hexdigest()
            digest_pages.setdefault(digest_of[xref], set()).add(page_index)

    # Pass 2: save what survives the junk filters.
    saved: list[dict] = []
    counter = 0
    seen_digests: set[str] = set()
    for page_index, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            digest = digest_of.get(xref)
            if digest is None or len(digest_pages.get(digest, ())) > _FURNITURE_MAX_PAGES:
                continue
            if digest in seen_digests:
                continue  # same bytes already saved once
            try:
                rects = page.get_image_rects(xref)
            except Exception:  # pragma: no cover - malformed xref
                rects = []
            rect = rects[0] if rects else None
            # Each Pixmap holds a fully decoded raster. A long PDF built one
            # per embedded image and left every one of them to the collector,
            # so peak memory scaled with the whole document rather than with
            # the largest figure. Released explicitly on every exit path.
            path = _save_figure_pixmap(doc, xref, output_dir, stem, counter,
                                       min_dim)
            if path is None:
                continue
            seen_digests.add(digest)
            saved.append({
                "image_path": path, "page": page_index,
                "y": float(rect.y0) if rect else 0.0,
                "rect": (tuple(rect) if rect else None),
            })
            counter += 1
    saved.sort(key=lambda d: (d["page"], d["y"]))
    return saved


def _caption_positions(doc: "fitz.Document") -> list[dict]:
    """Locate caption text blocks on each page: [{"page", "y", "fig_num"}].

    Uses the text-block bounding boxes so images can be paired with the
    caption physically nearest to them, instead of the fragile
    "k-th caption <-> k-th image" reading-order assumption (which breaks
    whenever a figure is stored as several image streams, or a stray
    graphic slips in).
    """
    found: list[dict] = []
    for page_index, page in enumerate(doc):
        try:
            blocks = page.get_text("blocks")
        except Exception:  # pragma: no cover
            continue
        for block in blocks:
            if len(block) < 7 or block[6] != 0:  # not a text block
                continue
            text = (block[4] or "").strip()
            m = _FIG_CAPTION_RE.match(text)
            if m:
                found.append({"page": page_index, "y": float(block[1]),
                              "fig_num": int(m.group(2))})
    return found


def _associate_images_to_captions(images: list[dict],
                                  captions_pos: list[dict]) -> None:
    """Assign each image the fig_num of the nearest same-page caption.

    Journal convention places the caption *below* its figure, so a caption
    starting at/after the image's top edge is preferred; otherwise the
    vertically nearest caption on the page wins. Images on caption-less
    pages keep ``fig_num=None``.
    """
    by_page: dict[int, list[dict]] = {}
    for cap in captions_pos:
        by_page.setdefault(cap["page"], []).append(cap)

    for img in images:
        candidates = by_page.get(img["page"], [])
        if not candidates:
            img["fig_num"] = None
            continue
        below = [c for c in candidates if c["y"] >= img["y"]]
        pool = below or candidates
        img["fig_num"] = min(pool, key=lambda c: abs(c["y"] - img["y"]))["fig_num"]


def _composite_figure(doc: "fitz.Document", page_index: int,
                      rects: list, out_path: str, zoom: float = 2.0) -> bool:
    """Render the union of image rects on a page into one composite PNG.

    Multi-panel figures are frequently stored as one image stream per
    panel; analyzing each stream as a separate 'figure' both breaks the
    caption pairing and lets the cross-figure detector compare sibling
    panels as if they were independent figures. Rendering the union
    rectangle reassembles the figure as the reader sees it.
    """
    valid = [fitz.Rect(r) for r in rects if r is not None]
    if not valid:
        return False
    union = valid[0]
    for r in valid[1:]:
        union |= r
    if union.is_empty or union.width < 8 or union.height < 8:
        return False
    try:
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                                         clip=union)
        pix.save(out_path)
        return True
    except Exception:  # pragma: no cover - render failure
        return False


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
        captions_pos = _caption_positions(doc)

        if captions_pos:
            figures = _figures_by_position(doc, images, captions, captions_pos,
                                           full_text, output_dir, stem)
        else:
            # No locatable caption blocks (scanned PDF, odd encoding):
            # fall back to reading-order pairing.
            figures = _figures_by_reading_order(images, captions, full_text)
    finally:
        doc.close()

    return {"sections": sections, "full_text": full_text, "figures": figures}


def _figures_by_position(doc, images: list[dict], captions: dict[int, str],
                         captions_pos: list[dict], full_text: str,
                         output_dir: str, stem: str) -> list[dict]:
    """Pair images with captions by physical page position (preferred path).

    Images assigned to the same caption are re-rendered as one composite
    (multi-panel figures stored as several image streams); images with no
    same-page caption surface as uncaptioned figures; captions with no
    image still appear with ``image_path=None``.
    """
    _associate_images_to_captions(images, captions_pos)

    by_fig: dict[int, list[dict]] = {}
    uncaptioned: list[dict] = []
    for img in images:
        if img.get("fig_num") is None:
            uncaptioned.append(img)
        else:
            by_fig.setdefault(img["fig_num"], []).append(img)

    figures: list[dict] = []
    for fig_num in sorted(set(captions) | set(by_fig)):
        group = by_fig.get(fig_num, [])
        image_path = None
        if len(group) == 1:
            image_path = group[0]["image_path"]
        elif len(group) > 1:
            # Reassemble panels stored as separate streams into one figure.
            composite = os.path.join(output_dir, f"{stem}_fig{fig_num}.png")
            same_page = {g["page"] for g in group}
            if len(same_page) == 1 and _composite_figure(
                    doc, group[0]["page"], [g.get("rect") for g in group],
                    composite):
                image_path = composite
                # The individual panel PNGs are now superseded by the
                # composite; nothing references them again, and leaving them
                # meant every multi-panel figure wrote its panels twice to the
                # output directory.
                _discard_files(g["image_path"] for g in group)
            else:  # panels across pages or render failure: keep the largest
                image_path = max(group, key=_image_area)["image_path"]
                _discard_files(g["image_path"] for g in group
                               if g["image_path"] != image_path)
        figures.append({
            "figure_num": fig_num,
            "label": f"Figure {fig_num}",
            "caption": captions.get(fig_num, ""),
            "image_path": image_path,
            "results_context": get_results_context(full_text, fig_num),
        })
    for extra in uncaptioned:
        figures.append({
            "figure_num": None,
            "label": f"(uncaptioned figure, page {extra['page'] + 1})",
            "caption": "",
            "image_path": extra["image_path"],
            "results_context": "",
        })
    return figures


def _discard_files(paths) -> None:
    """Delete superseded panel images; never fatal if one is already gone."""
    for path in paths:
        if not path:
            continue
        try:
            os.remove(path)
        except OSError:
            pass


def _image_area(img: dict) -> float:
    rect = img.get("rect")
    if not rect:
        return 0.0
    x0, y0, x1, y1 = rect
    return abs((x1 - x0) * (y1 - y0))


def _figures_by_reading_order(images: list[dict], captions: dict[int, str],
                              full_text: str) -> list[dict]:
    """Legacy fallback: pair the k-th caption with the k-th image."""
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
    return figures

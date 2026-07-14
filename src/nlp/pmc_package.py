"""Ingest a PMC Open Access *package* (.tar.gz) as pipeline input.

Why this exists
---------------
The vast majority of retracted, image-integrity papers are NOT distributed
as a main-article PDF in PMC — only ~1 in 150 fresh fraud cases had a
downloadable PDF. They ARE distributed as PMC OA **packages**: a
``.tar.gz`` holding the article's JATS XML (``.nxml`` — full text +
figure captions) and the **native-resolution figure images** directly.
Ingesting packages therefore (a) unlocks the fraud data the PDF path
cannot reach, and (b) gives the forensic detectors the original figure
rasters instead of images re-extracted from a PDF, which is strictly
better input.

Crucially, the SAME ingestion is used for fraud and clean papers, so the
two classes are format-identical — the detectors cannot separate them by a
PDF-vs-native artifact rather than by manipulation.

:func:`parse_pmc_package` returns the exact dict shape
:func:`src.nlp.pdf_parser.parse_paper` returns, so the orchestrator is
agnostic to the source::

    {"sections": {...}, "full_text": "...", "figures": [
        {"figure_num", "label", "caption", "image_path", "results_context"}]}
"""

from __future__ import annotations

import os
import re
import tarfile
import xml.etree.ElementTree as ET

from src.nlp.pdf_parser import get_results_context, split_sections

# Prefer full-resolution rasters; .gif in PMC packages is usually a
# low-res thumbnail, so it is the last resort.
_IMAGE_EXT_PREFERENCE = (".tif", ".tiff", ".jpg", ".jpeg", ".png", ".gif")


def _strip_ns(tag: str) -> str:
    """Return an element's local tag name, dropping any ``{namespace}``."""
    return tag.rsplit("}", 1)[-1]


def _text_of(elem: ET.Element) -> str:
    """All descendant text of an element, whitespace-normalized."""
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def _href_of(graphic: ET.Element) -> str | None:
    """The xlink:href of a <graphic>, namespace-agnostic."""
    for key, val in graphic.attrib.items():
        if _strip_ns(key) == "href":
            return val
    return None


def extract_package(tgz_path: str, dest_dir: str | None = None) -> str:
    """Extract a package .tar.gz and return the directory holding its files.

    PMC packages contain a single top-level ``PMCxxxxxxx/`` directory; the
    returned path is that directory (so ``.nxml`` + images sit directly in
    it). Extraction is guarded against path traversal.
    """
    dest_dir = dest_dir or os.path.dirname(os.path.abspath(tgz_path))
    with tarfile.open(tgz_path, "r:gz") as tf:
        members = tf.getmembers()
        base = os.path.abspath(dest_dir)
        for m in members:
            target = os.path.abspath(os.path.join(dest_dir, m.name))
            if not target.startswith(base + os.sep) and target != base:
                raise ValueError(f"unsafe path in archive: {m.name}")
        # filter="data" (Python 3.12+) rejects absolute/traversal members and
        # unsafe metadata — the sanctioned safe extraction. Fall back for
        # older interpreters, where the manual check above is the guard.
        try:
            tf.extractall(dest_dir, filter="data")
        except TypeError:  # pragma: no cover - Python < 3.12
            tf.extractall(dest_dir)
        tops = {m.name.split("/", 1)[0] for m in members if m.name}
    # A well-formed package has one PMCxxx/ root.
    if len(tops) == 1:
        rooted = os.path.join(dest_dir, next(iter(tops)))
        if os.path.isdir(rooted):
            return rooted
    return dest_dir


def _find_nxml(package_dir: str) -> str | None:
    for name in sorted(os.listdir(package_dir)):
        if name.lower().endswith(".nxml"):
            return os.path.join(package_dir, name)
    return None


def _resolve_graphic(href: str, package_dir: str) -> str | None:
    """Map a JATS graphic href to an actual image file in the package.

    Hrefs are usually stored WITHOUT an extension (``JO2021-5572402.001``);
    the package holds one or more raster files with that stem. Return the
    highest-resolution available (see ``_IMAGE_EXT_PREFERENCE``).
    """
    stem = os.path.basename(href)
    candidates: list[str] = []
    for name in os.listdir(package_dir):
        base, ext = os.path.splitext(name)
        if base == stem and ext.lower() in _IMAGE_EXT_PREFERENCE:
            candidates.append(name)
    if not candidates:
        # Some packages already include the extension in the href.
        if os.path.isfile(os.path.join(package_dir, stem)):
            return os.path.join(package_dir, stem)
        return None
    candidates.sort(key=lambda n: _IMAGE_EXT_PREFERENCE.index(
        os.path.splitext(n)[1].lower()))
    return os.path.join(package_dir, candidates[0])


def _figure_number(label: str, fig_id: str, ordinal: int) -> int | None:
    """Best-effort integer figure number from the label / id."""
    for source in (label, fig_id):
        m = re.search(r"(\d+)", source or "")
        if m:
            return int(m.group(1))
    return ordinal


def _collect_sections(body: ET.Element) -> dict[str, str]:
    """Top-level JATS <sec> titles -> concatenated text."""
    sections: dict[str, str] = {}
    for sec in body:
        if _strip_ns(sec.tag) != "sec":
            continue
        title_elem = next((c for c in sec if _strip_ns(c.tag) == "title"), None)
        title = _text_of(title_elem) if title_elem is not None else "Section"
        sections[title] = _text_of(sec)
    return sections


def parse_pmc_package(source: str, extract_dir: str | None = None) -> dict:
    """Parse a PMC OA package (.tar.gz or an already-extracted dir).

    Returns the same structure as :func:`src.nlp.pdf_parser.parse_paper`.
    Raises ``FileNotFoundError`` if no JATS ``.nxml`` is found.
    """
    if source.endswith((".tar.gz", ".tgz")):
        package_dir = extract_package(source, extract_dir)
    elif os.path.isdir(source):
        package_dir = source
    else:
        raise ValueError(f"expected a .tar.gz package or a directory: {source}")

    nxml_path = _find_nxml(package_dir)
    if not nxml_path:
        raise FileNotFoundError(f"no .nxml (JATS XML) found in {package_dir}")

    tree = ET.parse(nxml_path)
    root = tree.getroot()
    body = next((e for e in root.iter() if _strip_ns(e.tag) == "body"), root)
    abstract = next((e for e in root.iter() if _strip_ns(e.tag) == "abstract"), None)

    full_text_parts = []
    if abstract is not None:
        full_text_parts.append(_text_of(abstract))
    full_text_parts.append(_text_of(body))
    full_text = "\n".join(p for p in full_text_parts if p)

    sections = _collect_sections(body)
    if abstract is not None:
        sections.setdefault("Abstract", _text_of(abstract))
    if not sections:  # fall back to the header-splitting heuristic
        sections = split_sections(full_text)

    figures: list[dict] = []
    for ordinal, fig in enumerate(
            (e for e in root.iter() if _strip_ns(e.tag) == "fig"), start=1):
        label_elem = next((c for c in fig if _strip_ns(c.tag) == "label"), None)
        caption_elem = next((c for c in fig if _strip_ns(c.tag) == "caption"), None)
        graphic = next((e for e in fig.iter()
                        if _strip_ns(e.tag) == "graphic"), None)
        label = _text_of(label_elem) if label_elem is not None else f"Figure {ordinal}"
        caption = _text_of(caption_elem) if caption_elem is not None else ""
        href = _href_of(graphic) if graphic is not None else None
        image_path = _resolve_graphic(href, package_dir) if href else None
        fig_num = _figure_number(label, fig.get("id", ""), ordinal)
        figures.append({
            "figure_num": fig_num,
            "label": label or f"Figure {fig_num}",
            "caption": caption,
            "image_path": image_path,
            "results_context": get_results_context(full_text, fig_num)
            if fig_num is not None else "",
        })

    return {"sections": sections, "full_text": full_text, "figures": figures}


def is_package(source: str) -> bool:
    """True if ``source`` looks like a PMC package (tarball or extracted dir)."""
    if source.endswith((".tar.gz", ".tgz")):
        return True
    return os.path.isdir(source) and _find_nxml(source) is not None

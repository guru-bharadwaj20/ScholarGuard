"""Extract and dimension-filter figure images from a downloaded PMC package.

A PMC OA ``.tar.gz`` contains the article XML (``.nxml``) plus figure image
files. :func:`extract_figures` untars to a temp dir, keeps images whose
shorter side is at least ``min_dim`` px (dropping icons/logos/thumbnails),
copies survivors to ``output_dir`` as ``<pmcid>_<original>``, and cleans up.
:func:`extract_article_metadata` pulls title + DOI from the ``.nxml`` for the
manifest without any extra network call.

A ``.pdf`` fallback (when no tgz exists) is supported via PyMuPDF if available.
"""

from __future__ import annotations

import logging
import os
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image

logger = logging.getLogger("scholarguard.data")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif"}


def _safe_extract(tar: tarfile.TarFile, path: str) -> None:
    """Extract a tarball, refusing members that escape the target dir."""
    dest = os.path.abspath(path)
    for member in tar.getmembers():
        target = os.path.abspath(os.path.join(path, member.name))
        if not (target == dest or target.startswith(dest + os.sep)):
            raise ValueError(f"unsafe path in archive: {member.name}")
    try:
        tar.extractall(path, filter="data")  # Python 3.12+ hardened filter
    except TypeError:  # pragma: no cover - older Python without filter kw
        tar.extractall(path)


def _unique_dest(output_dir: str, base_name: str) -> str:
    """Return a non-colliding path in output_dir for base_name."""
    candidate = os.path.join(output_dir, base_name)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(base_name)
    i = 1
    while os.path.exists(os.path.join(output_dir, f"{stem}_{i}{ext}")):
        i += 1
    return os.path.join(output_dir, f"{stem}_{i}{ext}")


def extract_figures(package_path: str, output_dir: str, pmcid: str,
                    min_dim: int = 200) -> list[str]:
    """Extract qualifying figure images from a package; return saved paths.

    Images whose shorter side < ``min_dim`` px are skipped (icons/logos).
    Temp extraction files are always cleaned up. Never raises — logs and
    returns [] on a bad/corrupt package.
    """
    os.makedirs(output_dir, exist_ok=True)

    if package_path.lower().endswith(".pdf"):
        return _extract_from_pdf(package_path, output_dir, pmcid, min_dim)

    if not tarfile.is_tarfile(package_path):
        logger.warning("%s: not a tar archive, skipping extraction", package_path)
        return []

    tmp_dir = tempfile.mkdtemp(prefix=f"sg_{pmcid}_")
    saved: list[str] = []
    try:
        with tarfile.open(package_path, "r:*") as tar:
            _safe_extract(tar, tmp_dir)
        for root, _dirs, files in os.walk(tmp_dir):
            for fname in files:
                if os.path.splitext(fname)[1].lower() not in IMAGE_EXTENSIONS:
                    continue
                src = os.path.join(root, fname)
                if not _passes_min_dim(src, min_dim):
                    continue
                dest = _unique_dest(output_dir, f"{pmcid}_{fname}")
                shutil.copy2(src, dest)
                saved.append(dest)
    except (tarfile.TarError, ValueError, OSError) as exc:
        logger.warning("%s: extraction failed: %s", pmcid, exc)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info("%s: saved %d qualifying image(s)", pmcid, len(saved))
    return saved


def _passes_min_dim(image_path: str, min_dim: int) -> bool:
    """True if the image opens and its shorter side is >= min_dim."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
        return min(w, h) >= min_dim
    except (OSError, Image.DecompressionBombError) as exc:
        logger.debug("skip unreadable image %s: %s", image_path, exc)
        return False


def extract_article_metadata(package_path: str) -> dict:
    """Best-effort {title, doi} from the package's .nxml (no network call)."""
    meta = {"title": None, "doi": None}
    if not (os.path.isfile(package_path) and tarfile.is_tarfile(package_path)):
        return meta
    try:
        with tarfile.open(package_path, "r:*") as tar:
            nxml = next((m for m in tar.getmembers()
                         if m.name.lower().endswith(".nxml")), None)
            if nxml is None:
                return meta
            fobj = tar.extractfile(nxml)
            if fobj is None:
                return meta
            root = ET.fromstring(fobj.read())
    except (tarfile.TarError, ET.ParseError, OSError):
        return meta

    title_el = root.find(".//article-meta//article-title")
    if title_el is not None:
        meta["title"] = "".join(title_el.itertext()).strip() or None
    for aid in root.findall(".//article-meta//article-id"):
        if (aid.get("pub-id-type") or "").lower() == "doi" and aid.text:
            meta["doi"] = aid.text.strip()
            break
    return meta


def _extract_from_pdf(pdf_path: str, output_dir: str, pmcid: str,
                      min_dim: int) -> list[str]:
    """Fallback: extract embedded raster images from a PDF via PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:  # pragma: no cover
        logger.warning("%s: PDF fallback needs PyMuPDF; skipping", pmcid)
        return []
    saved: list[str] = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001 - corrupt PDF
        logger.warning("%s: could not open PDF: %s", pmcid, exc)
        return []
    try:
        counter = 0
        for page in doc:
            for img in page.get_images(full=True):
                pix = fitz.Pixmap(doc, img[0])
                if min(pix.width, pix.height) < min_dim:
                    continue
                if pix.n >= 5:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                dest = _unique_dest(output_dir, f"{pmcid}_pdfimg{counter:03d}.png")
                pix.save(dest)
                saved.append(dest)
                counter += 1
    finally:
        doc.close()
    logger.info("%s: saved %d image(s) from PDF", pmcid, len(saved))
    return saved

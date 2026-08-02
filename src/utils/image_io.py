"""Image and mask I/O helpers used across all ScholarGuard stages.

Conventions:
  * Images are BGR uint8 arrays (OpenCV convention).
  * Masks are single-channel uint8 arrays with values {0, 255}.
  * A ground-truth mask for ``figure.png`` lives next to it as
    ``figure_mask.png`` (Stage 1 output convention).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import cv2
import numpy as np

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
MASK_SUFFIXES = ("_mask", "_gt")  # recognised ground-truth naming suffixes


def imread_unicode(path: str, flag: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """``cv2.imread`` that survives non-ASCII paths. None if unreadable.

    ``cv2.imread`` passes the filename to the C++ layer as bytes in the system
    locale encoding, so on Windows it silently returns None for any path
    containing a character outside the active code page. That is not exotic
    here: inputs are user-uploaded PDFs and PMC filenames, and the project's
    primary environment is Windows. Reading the bytes ourselves and decoding
    from memory sidesteps the filename entirely.
    """
    try:
        buffer = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buffer.size == 0:
        return None
    return cv2.imdecode(buffer, flag)


def imwrite_unicode(path: str, image: np.ndarray) -> bool:
    """``cv2.imwrite`` that survives non-ASCII paths. See :func:`imread_unicode`."""
    extension = os.path.splitext(path)[1] or ".png"
    ok, encoded = cv2.imencode(extension, image)
    if not ok:
        return False
    try:
        encoded.tofile(path)
    except OSError:
        return False
    return True


def load_image(path: str, grayscale: bool = False) -> np.ndarray:
    """Load an image as BGR (or grayscale) uint8. Raises on failure."""
    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    image = imread_unicode(path, flag)
    if image is None:
        raise FileNotFoundError(f"could not read image: {path}")
    return image


def save_image(image: np.ndarray, path: str) -> None:
    """Save a BGR/grayscale image, creating parent directories as needed."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not imwrite_unicode(path, image):
        raise IOError(f"could not write image: {path}")


def load_mask(path: str) -> np.ndarray:
    """Load a binary mask as uint8 {0, 255} regardless of how it was saved."""
    mask = imread_unicode(path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"could not read mask: {path}")
    return ((mask > 127) * 255).astype(np.uint8)


def save_mask(mask: np.ndarray, path: str) -> None:
    """Save a binary mask as a {0, 255} PNG."""
    binary = ((np.asarray(mask) > 0) * 255).astype(np.uint8)
    save_image(binary, path)


def is_mask_file(path: str) -> bool:
    """True if the filename follows the ground-truth mask convention."""
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.endswith(MASK_SUFFIXES)


def find_ground_truth_mask(image_path: str) -> str | None:
    """Locate the ground-truth mask for an image, if one exists.

    Looks for ``<stem>_mask.<ext>`` / ``<stem>_gt.<ext>`` next to the image,
    then in a sibling ``masks/`` directory.
    """
    folder, filename = os.path.split(image_path)
    stem, _ = os.path.splitext(filename)
    candidates = [
        os.path.join(folder, f"{stem}{suffix}{ext}")
        for suffix in MASK_SUFFIXES
        for ext in (".png", ".bmp", ".tif")
    ]
    candidates += [os.path.join(folder, "masks", filename)]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def list_images(folder: str, include_masks: bool = False) -> list[str]:
    """Sorted list of image paths in a folder (masks excluded by default)."""
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() not in IMAGE_EXTENSIONS:
            continue
        if not include_masks and is_mask_file(path):
            continue
        paths.append(path)
    return paths


def iter_image_folder(
    folder: str, grayscale: bool = False
) -> Iterator[tuple[str, np.ndarray]]:
    """Yield (path, image) for every non-mask image in a folder.

    A generator so large datasets never have to fit in RAM at once.
    """
    for path in list_images(folder):
        yield path, load_image(path, grayscale=grayscale)

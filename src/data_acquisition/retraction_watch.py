"""Load and filter the Retraction Watch database for image-fraud cases.

The database is distributed by Crossref as a single CSV in a public GitLab
repo. We clone it shallowly (via ``git``, no extra Python dependency) and
filter to formal retractions whose stated reason concerns image integrity.

Verified against the live data (2026-07): the CSV is
``retraction_watch.csv`` (~63 MB, ~71k rows) with columns including
``Record ID, Title, Journal, RetractionDate, RetractionDOI,
OriginalPaperDate, OriginalPaperDOI, RetractionNature, Reason``.

**The reason strings differ from what is commonly assumed.** The actual
image-related values are ``Duplication of/in Image``, ``Manipulation of
Images`` and ``Falsification/Fabrication of Image`` (not "Duplication of
Image" / "Image Manipulation"), so we match on those verified variants.
"""

from __future__ import annotations

import glob
import logging
import os
import subprocess

import pandas as pd

logger = logging.getLogger("scholarguard.data")

REPO_URL = "https://gitlab.com/crossref/retraction-watch-data.git"
DEFAULT_REPO_PATH = "retraction-watch-data"

# Verified reason substrings that denote manipulated/duplicated/fabricated
# image content. Deliberately EXCLUDES weaker signals that are not evidence of
# manipulation: "Concerns/Issues about Image", "Error in Image",
# "Unreliable Image", "Plagiarism of Image", and "Original Data and/or Images
# not Provided".
IMAGE_REASON_PATTERNS = (
    "Duplication of/in Image",
    "Manipulation of Images",
    "Falsification/Fabrication of Image",
)

# Only formal retractions count as "confirmed"; Expressions of Concern and
# Corrections are weaker and are excluded from the fraud set entirely.
FORMAL_RETRACTION = "Retraction"

# Coarse mapping from a paper-level retraction reason onto Stage 7's
# figure-level detector taxonomy (see ground_truth_loader.VALID_FRAUD_TYPES).
#
# HONESTY NOTE: Retraction Watch states *why a paper was retracted*, not which
# figure was manipulated nor by which mechanism. The detector taxonomy has no
# "generic image manipulation" member, so all three image reasons map to
# ``copy_move`` — the category that means "image content was duplicated or
# altered". We deliberately do NOT map "Falsification/Fabrication of Image" to
# ``ai_generated``: fabrication long predates generative models and asserting a
# generative origin would be a fabrication of our own. The verbatim reason is
# preserved in each label as ``retraction_reason`` for human review.
REASON_TO_FRAUD_TYPE = {
    "Duplication of/in Image": "copy_move",
    "Manipulation of Images": "copy_move",
    "Falsification/Fabrication of Image": "copy_move",
}


def clone_or_update(repo_path: str = DEFAULT_REPO_PATH) -> str:
    """Shallow-clone the Retraction Watch repo if it isn't already present."""
    if os.path.isdir(os.path.join(repo_path, ".git")):
        logger.info("retraction-watch repo already present at %s", repo_path)
        return repo_path
    logger.info("cloning %s -> %s (shallow)", REPO_URL, repo_path)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, repo_path],
                   check=True, capture_output=True, text=True, timeout=900)
    return repo_path


def find_csv(repo_path: str) -> str:
    """Locate the database CSV inside the cloned repo."""
    matches = sorted(glob.glob(os.path.join(repo_path, "*.csv")))
    if not matches:
        raise FileNotFoundError(f"no CSV found in {repo_path}")
    if len(matches) > 1:
        logger.warning("multiple CSVs in %s, using %s", repo_path, matches[0])
    return matches[0]


def load_retraction_watch(repo_path: str = DEFAULT_REPO_PATH) -> pd.DataFrame:
    """Clone (if needed) and load the Retraction Watch database as a DataFrame."""
    clone_or_update(repo_path)
    csv_path = find_csv(repo_path)
    logger.info("loading Retraction Watch CSV: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("loaded %d retraction record(s), %d column(s)", len(df), len(df.columns))
    return df


def filter_image_related(df: pd.DataFrame) -> pd.DataFrame:
    """Return formal retractions whose reason concerns image integrity.

    Prints/logs the total vs. image-related counts. Rows without an
    ``OriginalPaperDOI`` are dropped (we cannot resolve them to PMC).
    """
    reasons = df["Reason"].fillna("")
    pattern = "|".join(_escape(p) for p in IMAGE_REASON_PATTERNS)
    image_mask = reasons.str.contains(pattern, case=False, regex=True, na=False)

    image_rows = df[image_mask]
    formal = image_rows[image_rows["RetractionNature"] == FORMAL_RETRACTION]
    usable = formal[formal["OriginalPaperDOI"].notna()].copy()

    logger.info("Retraction Watch: %d total records; %d image-related; "
                "%d formal retractions; %d with an OriginalPaperDOI",
                len(df), len(image_rows), len(formal), len(usable))

    # Newest first — recent papers are far likelier to be in the PMC OA subset.
    if "OriginalPaperDate" in usable.columns:
        usable = usable.sort_values("OriginalPaperDate", ascending=False)
    return usable


def _escape(text: str) -> str:
    """Escape regex metacharacters ('/' is safe, but '.' and '(' are not)."""
    import re
    return re.escape(text)


def matched_image_reasons(reason_text: str) -> list[str]:
    """The image-related reason substrings present in a row's Reason field."""
    lowered = (reason_text or "").lower()
    return [p for p in IMAGE_REASON_PATTERNS if p.lower() in lowered]


def reason_to_fraud_type(reason_text: str) -> str:
    """Map a Reason field onto Stage 7's fraud_type enum (see module note)."""
    for pattern in matched_image_reasons(reason_text):
        mapped = REASON_TO_FRAUD_TYPE.get(pattern)
        if mapped:
            return mapped
    return "copy_move"  # only called on rows already known to be image-related


def normalize_doi(doi) -> str:
    """Canonical form for DOI comparison (lowercase, trimmed, no URL prefix)."""
    if not isinstance(doi, str):
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip()


def retracted_doi_set(df: pd.DataFrame) -> set[str]:
    """Every DOI touched by ANY retraction record (original + notice).

    Used to guarantee no retracted paper leaks into the clean control set —
    not just the image-related subset.
    """
    dois: set[str] = set()
    for column in ("OriginalPaperDOI", "RetractionDOI"):
        if column in df.columns:
            dois.update(normalize_doi(d) for d in df[column].dropna())
    dois.discard("")
    logger.info("built exclusion set of %d retracted DOI(s)", len(dois))
    return dois

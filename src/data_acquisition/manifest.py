"""Resumable, atomic processing manifest for corpus acquisition.

The manifest is a JSON list of per-paper records. :func:`is_processed` lets a
re-run skip any PMCID already handled (success OR terminal skip), so nothing
is ever re-downloaded or re-processed. :func:`add_entry` appends and writes
atomically (temp file + rename) so a crash mid-write can't corrupt the file.
"""

from __future__ import annotations

import json
import os
import tempfile


def load_manifest(manifest_path: str) -> list[dict]:
    """Return the manifest as a list (empty if absent/corrupt)."""
    if not os.path.isfile(manifest_path):
        return []
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def is_retryable(entry: dict) -> bool:
    """True if this entry recorded a *transient* failure worth retrying.

    A download error or an unexpected exception says nothing about the paper —
    it may be a network blip, a rate-limit, or (as happened once) a stale URL
    on NCBI's side. Treating those as permanently "processed" would silently
    exclude the paper from every future run, so they are retried. Terminal
    outcomes (ok / no_images / retracted / not open-access) are never retried.
    """
    if entry.get("retryable"):
        return True
    return entry.get("status") in {"download_failed", "error"}


def is_processed(pmcid: str, manifest_path: str, *, retry_failed: bool = True) -> bool:
    """True if ``pmcid`` is already handled and should be skipped.

    With ``retry_failed`` (the default), entries recording a transient failure
    report False so the paper is attempted again. Pass ``retry_failed=False``
    to treat any recorded PMCID as done.
    """
    for entry in load_manifest(manifest_path):
        if entry.get("pmcid") == pmcid:
            if retry_failed and is_retryable(entry):
                return False
            return True
    return False


def add_entry(entry: dict, manifest_path: str) -> None:
    """Append ``entry`` to the manifest and persist it atomically.

    If a record for the same ``pmcid`` already exists (e.g. a retried
    download failure), it is replaced rather than duplicated.
    """
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    manifest = load_manifest(manifest_path)
    pmcid = entry.get("pmcid")
    if pmcid:
        manifest = [e for e in manifest if e.get("pmcid") != pmcid]
    manifest.append(entry)
    directory = os.path.dirname(os.path.abspath(manifest_path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        os.replace(tmp, manifest_path)  # atomic on the same filesystem
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

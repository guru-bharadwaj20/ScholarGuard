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


def is_processed(pmcid: str, manifest_path: str) -> bool:
    """True if ``pmcid`` already has a manifest entry (any status)."""
    return any(entry.get("pmcid") == pmcid for entry in load_manifest(manifest_path))


def add_entry(entry: dict, manifest_path: str) -> None:
    """Append ``entry`` to the manifest and persist it atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    manifest = load_manifest(manifest_path)
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

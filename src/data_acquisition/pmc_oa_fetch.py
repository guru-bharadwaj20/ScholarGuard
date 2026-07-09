"""PMC Open Access resolution + package download.

* :func:`resolve_oa_package` calls the OA service (oa.fcgi) and parses the XML
  record: license, retracted flag, and tgz / pdf download URLs.
* :func:`download_package` streams a URL to disk with a size cap and retries,
  returning ``False`` (never raising) on ultimate failure.

``ftp://ftp.ncbi.nlm.nih.gov`` hrefs are rewritten to the HTTPS mirror
``https://ftp.ncbi.nlm.nih.gov`` so downloads work over plain HTTPS.
"""

from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET

import requests

from src.data_acquisition.pmc_search import ncbi_common_params
from src.data_acquisition.rate_limiter import RateLimiter

logger = logging.getLogger("scholarguard.data")

OA_SERVICE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
_FTP_PREFIX = "ftp://ftp.ncbi.nlm.nih.gov"
_HTTPS_MIRROR = "https://ftp.ncbi.nlm.nih.gov"
_PMC_ROOT = f"{_HTTPS_MIRROR}/pub/pmc/"

# As of NCBI's April 2026 restructure, the legacy PMC article-dataset files
# (oa_package/, oa_pdf/, ...) were moved under /pub/pmc/deprecated/, but the
# OA service (oa.fcgi) still hands out the OLD /pub/pmc/<...> hrefs, which now
# 404. NCBI has said the deprecated tree will be removed in August 2026. So we
# try the canonical path first (future-proof, and correct again if NCBI
# restores it) and fall back to the deprecated tree.
_DEPRECATED_SEGMENT = "deprecated/"

# Once the canonical path is observed to 404, skip it for the rest of the run
# rather than burning a rate-limited request per package. Reset via
# reset_url_probe_cache() (tests).
_canonical_path_works: bool | None = None


def reset_url_probe_cache() -> None:
    """Forget whether the canonical (non-deprecated) PMC path works."""
    global _canonical_path_works
    _canonical_path_works = None


def _to_https(href: str | None) -> str | None:
    """Rewrite an ftp:// NCBI href to the HTTPS mirror."""
    if not href:
        return None
    if href.startswith(_FTP_PREFIX):
        return _HTTPS_MIRROR + href[len(_FTP_PREFIX):]
    return href


def candidate_urls(url: str) -> list[str]:
    """Ordered download URLs to try for a PMC package href.

    For a canonical ``/pub/pmc/<path>`` URL this yields the canonical URL and
    then the ``/pub/pmc/deprecated/<path>`` fallback (see module notes). Once
    the canonical form is known to 404, it is omitted.
    """
    if not url.startswith(_PMC_ROOT) or _DEPRECATED_SEGMENT in url:
        return [url]
    rest = url[len(_PMC_ROOT):]
    deprecated = f"{_PMC_ROOT}{_DEPRECATED_SEGMENT}{rest}"
    if _canonical_path_works is False:
        return [deprecated]
    return [url, deprecated]


def resolve_oa_package(pmcid: str, *, session: requests.Session | None = None,
                       rate_limiter: RateLimiter | None = None) -> dict:
    """Resolve a PMCID to its OA package metadata.

    Returns ``{"license": str|None, "retracted": bool, "tgz_url": str|None,
    "pdf_url": str|None, "error": str|None}``. On any failure (network, XML,
    or an OA-service ``<error>`` such as not-open-access) returns a dict with
    ``error`` set and no URLs — the caller logs and skips.
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    empty = {"license": None, "retracted": False, "tgz_url": None,
             "pdf_url": None, "error": None}

    rate_limiter.wait()
    try:
        resp = session.get(OA_SERVICE,
                           params={**ncbi_common_params(), "id": pmcid}, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except requests.RequestException as exc:
        return {**empty, "error": f"request_failed: {exc}"}
    except ET.ParseError as exc:
        return {**empty, "error": f"xml_parse_error: {exc}"}

    # The OA service reports "no package" via an <error code="..."> element.
    err = root.find(".//error")
    if err is not None:
        return {**empty, "error": err.get("code") or (err.text or "oa_error")}

    record = root.find(".//record")
    if record is None:
        return {**empty, "error": "no_record"}

    result = {
        "license": record.get("license"),
        "retracted": (record.get("retracted") or "no").lower() == "yes",
        "tgz_url": None,
        "pdf_url": None,
        "error": None,
    }
    for link in record.findall("link"):
        fmt = (link.get("format") or "").lower()
        href = _to_https(link.get("href"))
        if fmt == "tgz" and not result["tgz_url"]:
            result["tgz_url"] = href
        elif fmt == "pdf" and not result["pdf_url"]:
            result["pdf_url"] = href
    return result


class _NotFound(Exception):
    """A candidate URL returned 404/410 — try the next candidate, don't retry."""


# Outcome codes from :func:`download_package_ex`.
DOWNLOAD_OK = "ok"
DOWNLOAD_SIZE_CAP = "size_cap"      # deterministic — never worth retrying
DOWNLOAD_FAILED = "failed"          # transient — a later run may succeed


def download_package_ex(url: str, dest_path: str, max_size_mb: int = 50, *,
                        session: requests.Session | None = None,
                        rate_limiter: RateLimiter | None = None,
                        max_attempts: int = 3) -> tuple[bool, str]:
    """Like :func:`download_package` but also reports *why* it failed.

    Returns ``(ok, outcome)`` where outcome is one of ``DOWNLOAD_OK``,
    ``DOWNLOAD_SIZE_CAP`` (package larger than the cap — a permanent skip) or
    ``DOWNLOAD_FAILED`` (transient; safe to retry on a later run).
    """
    global _canonical_path_works
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    max_bytes = max_size_mb * 1024 * 1024
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    candidates = candidate_urls(url)
    for candidate in candidates:
        is_canonical = candidate == url and len(candidates) > 1
        try:
            if _try_download(candidate, dest_path, max_bytes, max_size_mb,
                             session, rate_limiter, max_attempts):
                if is_canonical:
                    _canonical_path_works = True
                return True, DOWNLOAD_OK
            # Server reached, but the package is over the cap: deterministic.
            return False, DOWNLOAD_SIZE_CAP
        except _NotFound:
            if is_canonical:
                # Remember, so the rest of the run skips this dead path.
                if _canonical_path_works is None:
                    logger.info("canonical PMC path 404s; using the "
                                "'deprecated/' tree for this run")
                _canonical_path_works = False
            continue
        except _Transient:
            continue  # exhausted retries on this candidate; try the next

    logger.warning("all download candidates failed for %s", url)
    return False, DOWNLOAD_FAILED


def download_package(url: str, dest_path: str, max_size_mb: int = 50, *,
                     session: requests.Session | None = None,
                     rate_limiter: RateLimiter | None = None,
                     max_attempts: int = 3) -> bool:
    """Stream a PMC package to ``dest_path`` with a size cap and retries.

    Tries each URL from :func:`candidate_urls` (canonical, then the
    ``deprecated/`` fallback). Transient errors are retried with exponential
    backoff; a 404 moves straight to the next candidate. Returns True on
    success, False if every candidate failed or the package exceeds
    ``max_size_mb``. Never raises. Use :func:`download_package_ex` when the
    caller needs to distinguish a size-cap skip from a transient failure.
    """
    ok, _outcome = download_package_ex(
        url, dest_path, max_size_mb, session=session,
        rate_limiter=rate_limiter, max_attempts=max_attempts)
    return ok


class _Transient(Exception):
    """Retries exhausted for a candidate URL."""


def _try_download(url, dest_path, max_bytes, max_size_mb, session,
                  rate_limiter, max_attempts) -> bool:
    """Download one candidate URL. Raises _NotFound / _Transient on failure."""
    for attempt in range(1, max_attempts + 1):
        rate_limiter.wait()
        try:
            with session.get(url, stream=True, timeout=60) as resp:
                if resp.status_code in (404, 410):
                    raise _NotFound(url)
                resp.raise_for_status()

                # Pre-check Content-Length where the server provides it.
                clen = resp.headers.get("Content-Length")
                if clen and int(clen) > max_bytes:
                    logger.warning("skipping %s: Content-Length %.1f MB > %d MB cap",
                                   url, int(clen) / 1e6, max_size_mb)
                    return False

                tmp = dest_path + ".part"
                written = 0
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > max_bytes:  # enforce cap even without header
                            fh.close()
                            os.remove(tmp)
                            logger.warning("skipping %s: exceeded %d MB during "
                                           "download", url, max_size_mb)
                            return False
                        fh.write(chunk)
                os.replace(tmp, dest_path)
                logger.info("downloaded %s (%.1f MB)", os.path.basename(dest_path),
                            written / 1e6)
                return True
        except _NotFound:
            _cleanup(dest_path + ".part")
            raise
        except (requests.RequestException, OSError) as exc:
            _cleanup(dest_path + ".part")
            # Other 4xx are permanent for this URL — don't burn retries.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status and 400 <= status < 500 and status != 429:
                logger.warning("%s: HTTP %s, not retrying", url, status)
                raise _Transient(url) from exc
            wait = 2 ** (attempt - 1)
            logger.warning("download attempt %d/%d failed for %s: %s%s",
                           attempt, max_attempts, url, exc,
                           f" - retrying in {wait}s" if attempt < max_attempts else "")
            if attempt < max_attempts:
                time.sleep(wait)
    raise _Transient(url)


def _cleanup(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:  # pragma: no cover
        pass

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


def _to_https(href: str | None) -> str | None:
    """Rewrite an ftp:// NCBI href to the HTTPS mirror."""
    if not href:
        return None
    if href.startswith(_FTP_PREFIX):
        return _HTTPS_MIRROR + href[len(_FTP_PREFIX):]
    return href


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


def download_package(url: str, dest_path: str, max_size_mb: int = 50, *,
                     session: requests.Session | None = None,
                     rate_limiter: RateLimiter | None = None,
                     max_attempts: int = 3) -> bool:
    """Stream ``url`` to ``dest_path`` with a size cap and retries.

    Returns True on success, False on ultimate failure or if the package
    exceeds ``max_size_mb`` (checked via Content-Length when available, and
    enforced during streaming regardless). Never raises.
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    max_bytes = max_size_mb * 1024 * 1024
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    for attempt in range(1, max_attempts + 1):
        rate_limiter.wait()
        try:
            with session.get(url, stream=True, timeout=60) as resp:
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
                            logger.warning("skipping %s: exceeded %d MB during "
                                           "download", url, max_size_mb)
                            fh.close()
                            os.remove(tmp)
                            return False
                        fh.write(chunk)
                os.replace(tmp, dest_path)
                logger.info("downloaded %s (%.1f MB)", os.path.basename(dest_path),
                            written / 1e6)
                return True
        except (requests.RequestException, OSError) as exc:
            wait = 2 ** (attempt - 1)
            logger.warning("download attempt %d/%d failed for %s: %s%s",
                           attempt, max_attempts, url, exc,
                           f" — retrying in {wait}s" if attempt < max_attempts else "")
            _cleanup(dest_path + ".part")
            if attempt < max_attempts:
                time.sleep(wait)
    logger.warning("giving up on %s after %d attempts", url, max_attempts)
    return False


def _cleanup(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:  # pragma: no cover
        pass

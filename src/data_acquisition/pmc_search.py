"""PubMed Central esearch wrapper — search terms -> list of PMCIDs.

Restricts every search to the open-access subset and includes the NCBI-
required ``tool`` and ``email`` parameters (email read from the
``NCBI_CONTACT_EMAIL`` env var; an ``NCBI_API_KEY`` is added when present).
"""

from __future__ import annotations

import logging
import os

import requests

from src.data_acquisition.rate_limiter import RateLimiter

logger = logging.getLogger("scholarguard.data")

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "ScholarGuard"


def get_contact_email() -> str:
    """Return the NCBI contact email from the environment, or raise clearly."""
    email = os.environ.get("NCBI_CONTACT_EMAIL")
    if not email:
        raise RuntimeError(
            "NCBI_CONTACT_EMAIL is not set. NCBI's usage policy requires a "
            "contact email on every request. Set it, e.g.\n"
            "  export NCBI_CONTACT_EMAIL=you@institution.edu    (bash)\n"
            "  $env:NCBI_CONTACT_EMAIL = 'you@institution.edu'  (PowerShell)")
    return email


def ncbi_common_params() -> dict:
    """The tool/email (+ optional api_key) params required on NCBI requests."""
    params = {"tool": TOOL_NAME, "email": get_contact_email()}
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return params


def search_pmc(term: str, retmax: int = 200, *, session: requests.Session | None = None,
               rate_limiter: RateLimiter | None = None) -> list[str]:
    """Search PMC's open-access subset for ``term``; return PMCIDs ("PMC...").

    Never raises on network/parse errors — logs a warning and returns [] so a
    corpus run can continue with the next term.
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    params = {
        **ncbi_common_params(),
        "db": "pmc",
        "term": f"{term} AND open access[filter]",
        "retmax": int(retmax),
        "retmode": "json",
    }

    rate_limiter.wait()
    try:
        resp = session.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("esearch request failed for %r: %s", term, exc)
        return []
    except ValueError as exc:  # invalid JSON
        logger.warning("esearch returned non-JSON for %r: %s", term, exc)
        return []

    idlist = (data.get("esearchresult", {}) or {}).get("idlist", []) or []
    pmcids = [f"PMC{i}" for i in idlist if str(i).strip()]
    logger.info("esearch %r -> %d PMCID(s)", term, len(pmcids))
    return pmcids

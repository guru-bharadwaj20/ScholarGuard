"""Batched DOI <-> PMCID resolution via NCBI's ID Converter (idconv).

The documented endpoint ``.../pmc/utils/idconv/v1.0/`` now 301-redirects to
``https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/`` (verified
2026-07); we call the new URL directly. It accepts comma-separated ids (up to
~200 per request), so resolution is batched to keep request counts low.

Reuses :class:`RateLimiter` and the shared NCBI tool/email/api_key params.
"""

from __future__ import annotations

import logging

import requests

from src.data_acquisition.pmc_search import ncbi_common_params
from src.data_acquisition.rate_limiter import RateLimiter

logger = logging.getLogger("scholarguard.data")

IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
MAX_BATCH = 200


def _idconv_batch(ids: list[str], session: requests.Session,
                  rate_limiter: RateLimiter) -> list[dict]:
    """One idconv call; returns the ``records`` list ([] on failure)."""
    rate_limiter.wait()
    params = {**ncbi_common_params(), "ids": ",".join(ids), "format": "json"}
    try:
        resp = session.get(IDCONV_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("idconv request failed for %d id(s): %s", len(ids), exc)
        return []
    except ValueError as exc:
        logger.warning("idconv returned non-JSON: %s", exc)
        return []
    return data.get("records", []) or []


def _resolve(ids: list[str], from_key: str, to_key: str, batch_size: int,
             session: requests.Session | None,
             rate_limiter: RateLimiter | None) -> dict[str, str | None]:
    """Shared batched resolution: {requested_id: target_id or None}."""
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    batch_size = max(1, min(batch_size, MAX_BATCH))

    unique = [i for i in dict.fromkeys(x for x in ids if x)]
    out: dict[str, str | None] = {i: None for i in unique}

    for start in range(0, len(unique), batch_size):
        chunk = unique[start:start + batch_size]
        for record in _idconv_batch(chunk, session, rate_limiter):
            # idconv echoes the input as "requested-id"; fall back to from_key.
            requested = record.get("requested-id") or record.get(from_key)
            if not requested:
                continue
            if record.get("status") == "error":
                continue  # e.g. "Identifier not found in PMC"
            target = record.get(to_key)
            if requested in out and target:
                out[requested] = str(target)

    resolved = sum(1 for v in out.values() if v)
    logger.info("idconv: resolved %d/%d %s -> %s (%d unresolved)",
                resolved, len(unique), from_key, to_key, len(unique) - resolved)
    return out


def resolve_dois_to_pmcids(dois: list[str], batch_size: int = 200, *,
                           session: requests.Session | None = None,
                           rate_limiter: RateLimiter | None = None
                           ) -> dict[str, str | None]:
    """Map DOIs to PMCIDs. Unresolved DOIs map to None.

    Many retracted papers are simply not in PMC (or were pulled from it), so a
    large unresolved fraction is expected and is logged, not an error.
    """
    return _resolve(dois, "doi", "pmcid", batch_size, session, rate_limiter)


def resolve_pmcids_to_dois(pmcids: list[str], batch_size: int = 200, *,
                           session: requests.Session | None = None,
                           rate_limiter: RateLimiter | None = None
                           ) -> dict[str, str | None]:
    """Map PMCIDs to DOIs — needed to screen search hits against the
    Retraction Watch exclusion set before accepting them as clean controls."""
    return _resolve(pmcids, "pmcid", "doi", batch_size, session, rate_limiter)

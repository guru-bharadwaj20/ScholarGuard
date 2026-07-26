"""Batched DOI <-> PMCID resolution via NCBI's ID Converter (idconv).

The documented endpoint ``.../pmc/utils/idconv/v1.0/`` now 301-redirects to
``https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/`` (verified
2026-07); we call the new URL directly. It accepts comma-separated ids (up to
~200 per request), so resolution is batched to keep request counts low.

Reuses :class:`RateLimiter` and the shared NCBI tool/email/api_key params.
"""

from __future__ import annotations

import logging
import re
import time

import requests

from src.data_acquisition.pmc_search import ncbi_common_params
from src.data_acquisition.rate_limiter import RateLimiter

logger = logging.getLogger("scholarguard.data")

IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
MAX_BATCH = 200
# idconv answers 429 under sustained batching even inside the documented rate
# limit. An unretried 429 is not a harmless gap: callers that screen a clean
# control class against Retraction Watch need the DOI to *decide*, so a dropped
# batch turns into papers admitted without ever being screened. Retry, and let
# the caller distinguish "not in PMC" from "we never got an answer".
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_PMCID_RE = re.compile(r"^PMC\d+$", re.IGNORECASE)


def _idconv_batch(ids: list[str], session: requests.Session,
                  rate_limiter: RateLimiter,
                  *, sleep=time.sleep) -> list[dict]:
    """One idconv call, retried through transient errors.

    Returns the ``records`` list, or ``[]`` when every attempt failed.
    """
    params = {**ncbi_common_params(), "ids": ",".join(ids), "format": "json"}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        rate_limiter.wait()
        try:
            resp = session.get(IDCONV_URL, params=params, timeout=60)
            status = resp.status_code
            if status in _RETRY_STATUS and attempt < MAX_ATTEMPTS:
                # Honour Retry-After when the server sends one; otherwise back
                # off exponentially (2s, 4s, 8s).
                delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                try:
                    delay = max(delay, float(resp.headers.get("Retry-After", 0)))
                except (TypeError, ValueError):
                    pass
                logger.warning("idconv %s for %d id(s); retry %d/%d in %.0fs",
                               status, len(ids), attempt, MAX_ATTEMPTS - 1, delay)
                sleep(delay)
                continue
            if status >= 400:
                # Permanent (4xx that we do not retry): retrying cannot help and
                # just burns the rate limit. A 400 here usually means one
                # malformed id poisoned the whole batch -- see _valid_id.
                logger.warning("idconv %s for %d id(s); not retryable", status,
                               len(ids))
                return []
            resp.raise_for_status()
            return resp.json().get("records", []) or []
        except requests.RequestException as exc:
            if attempt < MAX_ATTEMPTS:
                delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning("idconv request failed for %d id(s): %s; "
                               "retry %d/%d in %.0fs", len(ids), exc, attempt,
                               MAX_ATTEMPTS - 1, delay)
                sleep(delay)
                continue
            logger.warning("idconv request failed for %d id(s): %s", len(ids), exc)
            return []
        except ValueError as exc:
            logger.warning("idconv returned non-JSON: %s", exc)
            return []
    return []


def _valid_id(value: str, kind: str) -> bool:
    """Is ``value`` well-formed enough to send to idconv?

    idconv rejects an ENTIRE batch with 400 if any single id is malformed, so
    one junk value loses 200 good ones. Retraction Watch ships placeholders like
    ``unavailable`` in its DOI column, which is exactly how that happens.
    """
    value = value.strip()
    if not value:
        return False
    if kind == "doi":
        return value.lower().startswith("10.") and "/" in value
    return bool(_PMCID_RE.match(value))


def _resolve(ids: list[str], from_key: str, to_key: str, batch_size: int,
             session: requests.Session | None,
             rate_limiter: RateLimiter | None) -> dict[str, str | None]:
    """Shared batched resolution: {requested_id: target_id or None}."""
    session = session or requests.Session()
    rate_limiter = rate_limiter or RateLimiter()
    batch_size = max(1, min(batch_size, MAX_BATCH))

    unique = [i for i in dict.fromkeys(x for x in ids if x)]
    out: dict[str, str | None] = {i: None for i in unique}
    sendable = [i for i in unique if _valid_id(i, from_key)]
    if len(sendable) < len(unique):
        logger.info("idconv: %d/%d %s(s) are malformed and were not sent",
                    len(unique) - len(sendable), len(unique), from_key)

    for start in range(0, len(sendable), batch_size):
        chunk = sendable[start:start + batch_size]
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

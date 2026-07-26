"""Tests for idconv batching, retry, and malformed-id rejection.

These are not cosmetic. The clean control class is screened against Retraction
Watch by DOI, so a resolver that quietly returns nothing turns into *unscreened*
papers entering the clean class. Two real failures motivated these tests:

* a sustained run drew ``429 Too Many Requests`` and lost 245 of 245 DOIs, and
* a Retraction Watch placeholder DOI of the literal string ``unavailable``
  drew ``400 Bad Request`` for the whole 200-id batch, losing 199 good ids
  with it.
"""

from __future__ import annotations

import pytest
import requests

from src.data_acquisition import doi_resolver as dr


@pytest.fixture(autouse=True)
def _contact_email(monkeypatch):
    """NCBI policy requires a contact email on every request; these tests never
    reach the network, but ncbi_common_params() still (correctly) insists."""
    monkeypatch.setenv("NCBI_CONTACT_EMAIL", "tests@example.org")


class _Resp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _Session:
    """Session stub returning a scripted sequence of responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self._responses.pop(0)


class _NoWaitLimiter:
    def wait(self):
        pass


def _records(pmcid, doi):
    return {"records": [{"requested-id": pmcid, "pmcid": pmcid, "doi": doi}]}


def test_retries_429_then_succeeds():
    session = _Session([
        _Resp(429),
        _Resp(200, _records("PMC1", "10.1/a")),
    ])
    slept = []
    out = dr._idconv_batch(["PMC1"], session, _NoWaitLimiter(),
                           sleep=slept.append)
    assert out == [{"requested-id": "PMC1", "pmcid": "PMC1", "doi": "10.1/a"}]
    assert session.calls == 2
    assert slept, "expected a backoff sleep between attempts"


def test_honours_retry_after_header():
    session = _Session([_Resp(429, headers={"Retry-After": "30"}),
                        _Resp(200, _records("PMC1", "10.1/a"))])
    slept = []
    dr._idconv_batch(["PMC1"], session, _NoWaitLimiter(), sleep=slept.append)
    assert slept[0] >= 30


def test_gives_up_after_max_attempts():
    session = _Session([_Resp(503)] * dr.MAX_ATTEMPTS)
    assert dr._idconv_batch(["PMC1"], session, _NoWaitLimiter(),
                            sleep=lambda _s: None) == []
    assert session.calls == dr.MAX_ATTEMPTS


def test_does_not_retry_a_permanent_400():
    """A 400 means the request is malformed; retrying only burns rate limit."""
    session = _Session([_Resp(400)])
    assert dr._idconv_batch(["junk"], session, _NoWaitLimiter(),
                            sleep=lambda _s: None) == []
    assert session.calls == 1


def test_valid_id_screens_placeholders():
    assert dr._valid_id("10.1234/abc", "doi")
    assert not dr._valid_id("unavailable", "doi")
    assert not dr._valid_id("10.1234", "doi")      # no slash
    assert not dr._valid_id("", "doi")
    assert dr._valid_id("PMC12345", "pmcid")
    assert not dr._valid_id("12345", "pmcid")
    assert not dr._valid_id("unavailable", "pmcid")


def test_malformed_ids_are_dropped_before_the_request():
    """One junk DOI must not cost the whole batch (the real 400 we hit)."""
    session = _Session([_Resp(200, _records("PMC1", "10.1/a"))])
    out = dr.resolve_dois_to_pmcids(
        ["10.1/a", "unavailable"], session=session,
        rate_limiter=_NoWaitLimiter())
    # Still one request, containing only the well-formed id.
    assert session.calls == 1
    # The junk id is reported as unresolved rather than silently vanishing.
    assert out["unavailable"] is None


def test_unresolved_ids_map_to_none_not_missing():
    session = _Session([_Resp(200, _records("PMC1", "10.1/a"))])
    out = dr.resolve_pmcids_to_dois(["PMC1", "PMC2"], session=session,
                                    rate_limiter=_NoWaitLimiter())
    assert out == {"PMC1": "10.1/a", "PMC2": None}


def test_error_status_records_are_skipped():
    session = _Session([_Resp(200, {"records": [
        {"requested-id": "PMC9", "status": "error",
         "errmsg": "Identifier not found in PMC"}]})])
    out = dr.resolve_pmcids_to_dois(["PMC9"], session=session,
                                    rate_limiter=_NoWaitLimiter())
    assert out == {"PMC9": None}

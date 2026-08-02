"""Tests for the PMC data-acquisition components (all HTTP mocked).

No test hits the real NCBI API — search/resolve use injected fake sessions,
and extraction/manifest/rate-limiter are exercised on local fixtures.
"""

import os
import tarfile
import time
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.data_acquisition import manifest as manifest_mod
from src.data_acquisition.figure_extractor import extract_figures
from src.data_acquisition.pmc_oa_fetch import (
    DOWNLOAD_OK,
    DOWNLOAD_SIZE_CAP,
    candidate_urls,
    download_package_ex,
    reset_url_probe_cache,
    resolve_oa_package,
)
from src.data_acquisition.pmc_search import search_pmc
from src.data_acquisition.rate_limiter import RateLimiter


@pytest.fixture
def fast_limiter():
    return RateLimiter(requests_per_second=1000)


@pytest.fixture(autouse=True)
def _contact_email(monkeypatch):
    # search/resolve require NCBI_CONTACT_EMAIL; set a test value.
    monkeypatch.setenv("NCBI_CONTACT_EMAIL", "test@example.org")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)


def _fake_session(json_body=None, content=None):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    if json_body is not None:
        resp.json.return_value = json_body
    if content is not None:
        resp.content = content
    session = MagicMock()
    session.get.return_value = resp
    return session


# ---------------------------------------------------------------- test 1
def test_search_pmc_parses_idlist(fast_limiter):
    body = {"esearchresult": {"count": "2", "idlist": ["13901", "555000"]}}
    session = _fake_session(json_body=body)
    pmcids = search_pmc("western blot", retmax=10,
                        session=session, rate_limiter=fast_limiter)
    assert pmcids == ["PMC13901", "PMC555000"]
    # The open-access filter and required NCBI params were sent.
    _, kwargs = session.get.call_args
    params = kwargs["params"]
    assert "open access[filter]" in params["term"]
    assert params["tool"] == "ScholarGuard"
    assert params["email"] == "test@example.org"


def test_search_pmc_handles_empty_and_malformed(fast_limiter):
    assert search_pmc("nothing", session=_fake_session(json_body={}),
                      rate_limiter=fast_limiter) == []
    # Malformed JSON -> [] (no crash).
    bad = _fake_session()
    bad.get.return_value.json.side_effect = ValueError("bad json")
    assert search_pmc("x", session=bad, rate_limiter=fast_limiter) == []


# ---------------------------------------------------------------- test 2
def test_resolve_oa_package_parses_links(fast_limiter):
    xml = b"""<?xml version="1.0"?>
    <OA><records><record id="PMC13901" license="CC BY" retracted="no">
      <link format="tgz" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa/PMC13901.tar.gz"/>
      <link format="pdf" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa/PMC13901.pdf"/>
    </record></records></OA>"""
    out = resolve_oa_package("PMC13901", session=_fake_session(content=xml),
                             rate_limiter=fast_limiter)
    assert out["license"] == "CC BY"
    assert out["retracted"] is False
    # ftp:// rewritten to the https mirror.
    assert out["tgz_url"] == \
        "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa/PMC13901.tar.gz"
    assert out["pdf_url"].startswith("https://ftp.ncbi.nlm.nih.gov")
    assert out["error"] is None


def test_resolve_oa_package_detects_retracted(fast_limiter):
    xml = b"""<OA><records><record id="PMC9" license="CC BY-NC" retracted="yes">
      <link format="tgz" href="https://ftp.ncbi.nlm.nih.gov/x.tar.gz"/>
    </record></records></OA>"""
    out = resolve_oa_package("PMC9", session=_fake_session(content=xml),
                             rate_limiter=fast_limiter)
    assert out["retracted"] is True
    assert out["license"] == "CC BY-NC"


def test_resolve_oa_package_handles_error_element(fast_limiter):
    xml = b'<OA><error code="idIsNotOpenAccess">not OA</error></OA>'
    out = resolve_oa_package("PMC0", session=_fake_session(content=xml),
                             rate_limiter=fast_limiter)
    assert out["error"] == "idIsNotOpenAccess"
    assert out["tgz_url"] is None


def test_candidate_urls_falls_back_to_deprecated_tree():
    """oa.fcgi hands out pre-2026 hrefs; the packages now live under
    /pub/pmc/deprecated/. Both are tried, canonical first."""
    reset_url_probe_cache()
    url = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/54/be/PMC1.tar.gz"
    assert candidate_urls(url) == [
        url,
        "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/54/be/PMC1.tar.gz",
    ]
    # A non-PMC URL is passed through untouched.
    assert candidate_urls("https://example.org/x.tar.gz") == \
        ["https://example.org/x.tar.gz"]
    # An already-deprecated URL isn't double-prefixed.
    dep = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/x.tar.gz"
    assert candidate_urls(dep) == [dep]
    reset_url_probe_cache()


def _streaming_session(status=200, headers=None, chunks=(b"data",)):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.raise_for_status.return_value = None
    resp.iter_content.return_value = iter(chunks)
    resp.__enter__ = lambda s: resp
    resp.__exit__ = lambda s, *a: False
    session = MagicMock()
    session.get.return_value = resp
    return session


def test_download_size_cap_is_distinguished_from_failure(tmp_path, fast_limiter):
    """An oversized package is a permanent skip, not a retryable failure."""
    reset_url_probe_cache()
    big = _streaming_session(headers={"Content-Length": str(400 * 1024 * 1024)})
    ok, outcome = download_package_ex(
        "https://example.org/big.tar.gz", str(tmp_path / "p.tar.gz"),
        max_size_mb=50, session=big, rate_limiter=fast_limiter)
    assert ok is False and outcome == DOWNLOAD_SIZE_CAP
    assert not (tmp_path / "p.tar.gz").exists()


def test_download_success_reports_ok(tmp_path, fast_limiter):
    reset_url_probe_cache()
    sess = _streaming_session(headers={"Content-Length": "8"}, chunks=(b"abcdefgh",))
    dest = str(tmp_path / "p.tar.gz")
    ok, outcome = download_package_ex("https://example.org/p.tar.gz", dest,
                                      session=sess, rate_limiter=fast_limiter)
    assert ok is True and outcome == DOWNLOAD_OK
    assert open(dest, "rb").read() == b"abcdefgh"


# ---------------------------------------------------------------- test 3
def _make_targz(path, images):
    """images: list of (filename, (w, h)). Build a .tar.gz of PNGs."""
    src_dir = os.path.join(os.path.dirname(path), "_src")
    os.makedirs(src_dir, exist_ok=True)
    paths = []
    for name, (w, h) in images:
        p = os.path.join(src_dir, name)
        Image.new("RGB", (w, h), (120, 120, 120)).save(p)
        paths.append(p)
    with tarfile.open(path, "w:gz") as tar:
        for p in paths:
            tar.add(p, arcname=os.path.join("PMC1", os.path.basename(p)))
    return path


def test_extract_figures_filters_by_dimension(tmp_path):
    pkg = _make_targz(str(tmp_path / "pkg.tar.gz"), [
        ("big1.png", (300, 300)),      # keep
        ("big2.png", (250, 220)),      # keep (shorter side 220 >= 200)
        ("tiny_icon.png", (40, 40)),   # drop (below 200)
    ])
    out_dir = str(tmp_path / "out")
    saved = extract_figures(pkg, out_dir, "PMC1", min_dim=200)

    assert len(saved) == 2
    names = sorted(os.path.basename(p) for p in saved)
    assert names == ["PMC1_big1.png", "PMC1_big2.png"]
    assert all(os.path.isfile(p) for p in saved)
    # Temp extraction dir was cleaned up (only the output images remain).
    assert not any(d.startswith("sg_PMC1") for d in os.listdir(tmp_path))


def test_extract_figures_bad_package_returns_empty(tmp_path):
    bad = tmp_path / "not_a_tar.tar.gz"
    bad.write_bytes(b"this is not a tarball")
    assert extract_figures(str(bad), str(tmp_path / "o"), "PMCX") == []


# ---------------------------------------------------------------- test 4
def test_manifest_resumability(tmp_path):
    mpath = str(tmp_path / "manifest.json")
    assert manifest_mod.is_processed("PMC13901", mpath) is False

    manifest_mod.add_entry(
        {"pmcid": "PMC13901", "license": "CC BY", "retracted": False,
         "images": ["a.png"], "status": "ok"}, mpath)

    assert manifest_mod.is_processed("PMC13901", mpath) is True
    assert manifest_mod.is_processed("PMC999", mpath) is False
    # A second entry doesn't clobber the first (append + atomic write).
    manifest_mod.add_entry({"pmcid": "PMC999", "status": "ok"}, mpath)
    ids = {e["pmcid"] for e in manifest_mod.load_manifest(mpath)}
    assert ids == {"PMC13901", "PMC999"}


def test_manifest_transient_failures_are_retried(tmp_path):
    """A download failure must NOT permanently exclude a paper from re-runs."""
    mpath = str(tmp_path / "m.json")
    manifest_mod.add_entry({"pmcid": "PMC7", "status": "download_failed",
                            "retryable": True}, mpath)
    # Default: retried (reported as not-processed) ...
    assert manifest_mod.is_processed("PMC7", mpath) is False
    # ... unless the caller explicitly opts out.
    assert manifest_mod.is_processed("PMC7", mpath, retry_failed=False) is True

    # Terminal outcomes are never retried.
    for status in ("ok", "no_images", "skipped_retracted"):
        manifest_mod.add_entry({"pmcid": f"PMC_{status}", "status": status}, mpath)
        assert manifest_mod.is_processed(f"PMC_{status}", mpath) is True


def test_manifest_add_entry_upserts_on_retry(tmp_path):
    """Re-processing a PMCID replaces its old record instead of duplicating."""
    mpath = str(tmp_path / "m.json")
    manifest_mod.add_entry({"pmcid": "PMC7", "status": "download_failed",
                            "retryable": True}, mpath)
    manifest_mod.add_entry({"pmcid": "PMC7", "status": "ok", "n_images": 3}, mpath)
    entries = manifest_mod.load_manifest(mpath)
    assert len(entries) == 1
    assert entries[0]["status"] == "ok" and entries[0]["n_images"] == 3


# ---------------------------------------------------------------- test 5
def test_rate_limiter_respects_rate():
    limiter = RateLimiter(requests_per_second=5)
    start = time.monotonic()
    for _ in range(10):  # 10 calls at 5/s -> the 6th onward must wait ~1s
        limiter.wait()
    elapsed = time.monotonic() - start
    # First 5 are ~instant; the next 5 are gated into the following window.
    assert elapsed >= 0.8, f"limiter too fast: {elapsed:.2f}s"
    assert elapsed < 4.0, f"limiter too slow: {elapsed:.2f}s"


def test_rate_limiter_auto_detects_api_key(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    assert RateLimiter().requests_per_second == 3.0
    monkeypatch.setenv("NCBI_API_KEY", "abc123")
    assert RateLimiter().requests_per_second == 10.0


def test_rate_limiter_does_not_hold_its_lock_while_sleeping():
    """Threads must block on the RATE, not on the mutex.

    wait() used to sleep inside `with self._lock`, so a limiter shared between
    threads serialised them through the sleep even when the window had room.
    Six threads against a 3/s limit should take about one window, not six.
    """
    import threading
    import time as _time

    from src.data_acquisition.rate_limiter import RateLimiter

    limiter = RateLimiter(requests_per_second=3)
    start = _time.monotonic()
    threads = [threading.Thread(target=limiter.wait) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = _time.monotonic() - start

    # 6 requests at 3/s needs one full window of waiting, and no more.
    assert 0.9 <= elapsed < 2.0, f"took {elapsed:.2f}s"


def test_rate_limiter_never_exceeds_its_budget_under_contention():
    import threading

    from src.data_acquisition.rate_limiter import RateLimiter

    limiter = RateLimiter(requests_per_second=4)
    threads = [threading.Thread(target=limiter.wait) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Whatever the interleaving, no rolling second may hold more than 4.
    stamps = sorted(limiter._times)
    for i, stamp in enumerate(stamps):
        in_window = sum(1 for other in stamps[i:] if other - stamp < 1.0)
        assert in_window <= 4

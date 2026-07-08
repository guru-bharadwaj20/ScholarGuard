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
from src.data_acquisition.pmc_oa_fetch import resolve_oa_package
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

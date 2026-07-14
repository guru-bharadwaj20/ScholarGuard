"""Unit tests for PMC OA package ingestion (JATS XML + bundled images).

Uses a tiny hand-built package (no network) so CI is self-contained: a
minimal JATS ``.nxml`` plus two stand-in image files, tarred up, and parsed
through the same code path the pipeline uses.
"""

import os
import tarfile

import cv2
import numpy as np
import pytest

from src.nlp.pmc_package import is_package, parse_pmc_package

_NXML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front><article-meta>
    <abstract><p>We study protein X across conditions.</p></abstract>
  </article-meta></front>
  <body>
    <sec><title>Introduction</title><p>Background on protein X.</p></sec>
    <sec><title>Results</title>
      <p>As shown in Figure 1, expression rises. Figure 2 confirms it.</p>
      <fig id="fig1"><label>Figure 1</label>
        <caption><p>Western blot across 4 conditions.</p></caption>
        <graphic xlink:href="paper.001"/></fig>
      <fig id="fig2"><label>Figure 2</label>
        <caption><p>Quantification bar chart.</p></caption>
        <graphic xlink:href="paper.002"/></fig>
    </sec>
  </body>
</article>
"""


@pytest.fixture
def package_dir(tmp_path):
    """An extracted-package directory with a .nxml and two images."""
    pkg = tmp_path / "PMC0000001"
    pkg.mkdir()
    (pkg / "paper.nxml").write_text(_NXML, encoding="utf-8")
    # Two stand-in figure rasters (a high-res .jpg and a .gif thumbnail for
    # figure 1, to exercise the extension-preference logic).
    img = (np.random.default_rng(0).integers(0, 255, (60, 80, 3))).astype(np.uint8)
    cv2.imwrite(str(pkg / "paper.001.jpg"), img)
    cv2.imwrite(str(pkg / "paper.001.gif"), img)
    cv2.imwrite(str(pkg / "paper.002.jpg"), img)
    return str(pkg)


def test_is_package_detects_dir_and_tgz(package_dir, tmp_path):
    assert is_package(package_dir) is True
    tgz = tmp_path / "PMC0000001.tar.gz"
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(package_dir, arcname="PMC0000001")
    assert is_package(str(tgz)) is True
    assert is_package(str(tmp_path / "nope.pdf")) is False


def test_parse_package_dir(package_dir):
    parsed = parse_pmc_package(package_dir)
    # sections + full text
    assert "Results" in parsed["sections"]
    assert "protein X" in parsed["full_text"]
    # two figures, captions + numbers + resolved images
    figs = parsed["figures"]
    assert len(figs) == 2
    assert figs[0]["figure_num"] == 1
    assert "Western blot" in figs[0]["caption"]
    assert figs[0]["image_path"].endswith(".jpg")   # prefers jpg over gif
    assert os.path.isfile(figs[0]["image_path"])
    # results context picks up the in-body Figure 1 mention
    assert "Figure 1" in figs[0]["results_context"] or \
        "expression" in figs[0]["results_context"]


def test_parse_tgz_roundtrip(package_dir, tmp_path):
    tgz = tmp_path / "pkg.tar.gz"
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(package_dir, arcname="PMC0000001")
    out = tmp_path / "extracted"
    out.mkdir()
    parsed = parse_pmc_package(str(tgz), extract_dir=str(out))
    assert len(parsed["figures"]) == 2
    assert all(f["image_path"] and os.path.isfile(f["image_path"])
               for f in parsed["figures"])


def test_missing_nxml_raises(tmp_path):
    empty = tmp_path / "PMCempty"
    empty.mkdir()
    (empty / "img.jpg").write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        parse_pmc_package(str(empty))


def test_orchestrator_accepts_package(package_dir, tmp_path):
    """The full pipeline runs on a package input (no LLM), producing a report."""
    from src.pipeline.orchestrator import run_pipeline
    report = run_pipeline(package_dir, llm_client=None,
                          output_dir=str(tmp_path / "out"))
    assert report["status"] == "completed"
    assert report["paper"]["n_figures"] == 2
    assert "overall_risk" in report

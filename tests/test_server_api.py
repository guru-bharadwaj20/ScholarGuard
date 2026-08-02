"""HTTP-level tests for the FastAPI bridge.

server/main.py had no tests, so its contract with the web client -- status
codes, content types, the shape of /result -- was unverified. The pipeline is
never run here; jobs are injected directly into the registry.
"""

import os

import cv2
import numpy as np
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from server import main as server_main
from server import pipeline_bridge as bridge


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(bridge, "_jobs", {})
    monkeypatch.setattr(bridge, "_inflight", 0)
    yield


@pytest.fixture
def client():
    return TestClient(server_main.app)


def _completed_job(tmp_path, image_name="fig0.png", forged=True):
    out = tmp_path / "job"
    out.mkdir(parents=True, exist_ok=True)
    image = out / image_name
    cv2.imwrite(str(image), np.full((50, 60, 3), 190, np.uint8))

    job = bridge.Job(job_id="jid", pdf_path=str(tmp_path / "p.pdf"),
                     output_dir=str(out), label="paper.pdf")
    job.report = {
        "schema_version": "scholarguard/stage6/1.0",
        "status": "completed",
        "paper": {"filename": "paper.pdf", "n_figures": 1,
                  "sections_found": []},
        "overall_risk": {"score": 30.0, "category": "moderate", "n_figures": 1},
        "figures": [{
            "figure": "Figure 1", "figure_num": 1, "caption": "",
            "image_path": str(image),
            "detectors": {"copy_move": {"status": "ok", "forged": forged,
                                        "confidence": 0.7, "n_regions": 1}},
            "risk": {"score": 30.0, "category": "moderate", "breakdown": []},
        }],
        "pipeline_warnings": [], "disclaimer": "leads, not proof", "error": None,
    }
    job.finish("completed", report=job.report)
    bridge._jobs["jid"] = job
    return job


# ---------------------------------------------------------------- basics
def test_health_reports_capacity(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["inflight"] == 0
    assert body["max_concurrent"] >= 1
    assert body["max_inflight"] > body["max_concurrent"]


def test_unknown_job_is_404(client):
    assert client.get("/analyze/nope/result").status_code == 404
    assert client.get("/analyze/nope/figures/0/image").status_code == 404


def test_non_pdf_upload_is_rejected(client):
    r = client.post("/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/analyze", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415


def test_oversized_upload_is_rejected(client, monkeypatch):
    monkeypatch.setattr(server_main, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/analyze",
                    files={"file": ("x.pdf", b"%PDF-1.4" + b"0" * 100,
                                    "application/pdf")})
    assert r.status_code == 413


def test_capacity_refusal_is_503_and_leaves_no_upload(client, monkeypatch,
                                                      tmp_path):
    monkeypatch.setattr(server_main, "UPLOADS_DIR", str(tmp_path / "uploads"))

    def full(*a, **k):
        raise bridge.CapacityError("too busy")

    monkeypatch.setattr(bridge, "start_job", full)
    r = client.post("/analyze",
                    files={"file": ("x.pdf", b"%PDF-1.4 body", "application/pdf")})
    assert r.status_code == 503
    assert "too busy" in r.json()["detail"]
    assert not list((tmp_path / "uploads").iterdir()), (
        "a refused upload was left on disk")


# ---------------------------------------------------------------- results
def test_result_shape_and_url_rewriting(client, tmp_path):
    _completed_job(tmp_path)
    body = client.get("/analyze/jid/result").json()

    fig = body["figures"][0]
    assert fig["image_url"] == "/analyze/jid/figures/0/image"
    assert fig["overlay_url"] == "/analyze/jid/figures/0/overlay"
    assert "image_path" not in fig, "local filesystem path leaked to the client"
    assert body["job"]["runtime_sec"] >= 0


def test_no_overlay_url_when_copy_move_did_not_fire(client, tmp_path):
    _completed_job(tmp_path, forged=False)
    fig = client.get("/analyze/jid/result").json()["figures"][0]
    assert fig["image_url"] is not None
    assert fig["overlay_url"] is None
    assert client.get("/analyze/jid/figures/0/overlay").status_code == 404


def test_running_job_result_is_409(client, tmp_path):
    job = bridge.Job(job_id="jid", pdf_path="p", output_dir=str(tmp_path))
    job.set_status("running")
    bridge._jobs["jid"] = job
    assert client.get("/analyze/jid/result").status_code == 409


# ------------------------------------------------------------ content types
@pytest.mark.parametrize("name, expected", [
    ("fig0.png", "image/png"),
    ("fig0.jpg", "image/jpeg"),
    ("fig0.tif", "image/tiff"),
])
def test_figure_image_content_type_follows_the_file(client, tmp_path, name,
                                                    expected):
    """PMC packages ship .jpg and .tif; both were served as image/png.

    Browsers sniff JPEG so that one merely lied, but a TIFF labelled image/png
    does not render at all.
    """
    _completed_job(tmp_path, image_name=name)
    r = client.get("/analyze/jid/figures/0/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == expected


def test_unknown_extension_falls_back_to_octet_stream():
    assert server_main._media_type_for("x.dat") == "application/octet-stream"
    assert server_main._media_type_for("X.JPEG") == "image/jpeg"

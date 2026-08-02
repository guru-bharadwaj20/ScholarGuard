"""ScholarGuard API bridge — a thin FastAPI transport layer.

Every endpoint is a thin call into existing, unmodified Stage 2-6 code via
``pipeline_bridge``. No detection, scoring, or report logic lives here.

Run (from the repo root):
    uvicorn server.main:app --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from server import pipeline_bridge as bridge

app = FastAPI(title="ScholarGuard bridge", version="1.0")

# Local dev: the Next.js app runs on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = os.path.join(bridge.REPO_ROOT, "server", "uploads")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — larger than any eval-set PDF

# Bundled example papers from the REAL Stage 7 evaluation set. The clean
# example is deliberately one that still scores moderately because of the
# copy-move detector's measured over-triggering — the demo is honest by
# example, not just by disclaimer.
EXAMPLES: dict[str, dict] = {
    "fraud-retracted": {
        "id": "fraud-retracted",
        "title": "Retracted paper (confirmed image fraud)",
        "description": (
            "A real PMC Open Access paper, formally retracted for image "
            "integrity concerns (Retraction Watch). The retraction is "
            "paper-level — which specific figure was manipulated is not "
            "publicly annotated."),
        "kind": "fraud",
        "path": os.path.join(bridge.REPO_ROOT, "data", "evaluation_set",
                             "fraud_cases", "PMC10551568.pdf"),
        "expected_runtime": "≈ 3 minutes (15 figures)",
        "honesty_note": None,
    },
    "clean-moderate": {
        "id": "clean-moderate",
        "title": "Clean paper (never retracted)",
        "description": (
            "A real, never-retracted PMC Open Access control paper."),
        "kind": "clean",
        "path": os.path.join(bridge.REPO_ROOT, "data", "evaluation_set",
                             "clean_control_papers", "PMC13343156.pdf"),
        "expected_runtime": "≈ 2-3 minutes",
        "honesty_note": (
            "Real clean paper — note it still scores ~55/100 (high zone) "
            "because of a known detector limitation: copy-move over-triggers "
            "on legitimate repeated structure. Explained in Methodology."),
    },
}


# ---------------------------------------------------------------------------
# Health + examples
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/examples")
def examples() -> list[dict]:
    return [
        {k: v for k, v in ex.items() if k != "path"} | {
            "available": os.path.isfile(ex["path"])}
        for ex in EXAMPLES.values()
    ]


# ---------------------------------------------------------------------------
# Starting analyses
# ---------------------------------------------------------------------------


@app.post("/analyze")
async def analyze(file: UploadFile) -> dict:
    """Accept a PDF, start a pipeline run, return the job id immediately."""
    name = os.path.basename(file.filename or "upload.pdf")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is too large (limit 50 MB).")
    if not data.startswith(b"%PDF"):
        # Not fatal for the pipeline (it degrades gracefully), but a clearer
        # early message for the common wrong-file case.
        raise HTTPException(415, "That file doesn't look like a PDF.")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    job_id_hint = os.urandom(4).hex()
    pdf_path = os.path.join(UPLOADS_DIR, f"{job_id_hint}_{safe}")
    with open(pdf_path, "wb") as fh:
        fh.write(data)

    job = bridge.start_job(pdf_path, label=name, owns_pdf=True)
    return {"job_id": job.job_id, "label": job.label}


@app.post("/analyze/example/{example_id}")
def analyze_example(example_id: str) -> dict:
    ex = EXAMPLES.get(example_id)
    if ex is None:
        raise HTTPException(404, "Unknown example.")
    if not os.path.isfile(ex["path"]):
        raise HTTPException(404, "Example PDF is not present in this checkout.")
    job = bridge.start_job(ex["path"], label=ex["title"])
    return {"job_id": job.job_id, "label": job.label}


# ---------------------------------------------------------------------------
# Progress stream + result
# ---------------------------------------------------------------------------


@app.get("/analyze/{job_id}/stream")
async def stream(job_id: str) -> EventSourceResponse:
    """Server-Sent Events: real progress parsed from the pipeline's own logs."""
    job = bridge.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")

    async def gen():
        sent = 0
        while True:
            with job.lock:
                pending = job.events[sent:]
                # Read the status inside the SAME lock as the event list, so a
                # job finishing between the two reads cannot make the loop
                # believe it has drained a list it has not yet seen grow.
                status = job.status
                total = len(job.events)
            for ev in pending:
                sent += 1
                yield {"event": ev["kind"], "data": json.dumps(ev)}
            if status in ("completed", "failed") and sent >= total:
                yield {"event": "end", "data": json.dumps({"status": status})}
                return
            await asyncio.sleep(0.3)

    return EventSourceResponse(gen())


@app.get("/analyze/{job_id}/result")
def result(job_id: str) -> dict:
    job = bridge.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")
    # One consistent view: status, report and runtime are published together,
    # so this can never see a finished report with an unset finish time.
    state = job.snapshot()
    if state["status"] == "failed" and state["report"] is None:
        return {"status": "failed", "error": state["error"]}
    if state["report"] is None:
        raise HTTPException(409, "Analysis still running.")

    # Rewrite local figure paths into API URLs; add whether a copy-move
    # overlay is offered (only when that detector actually fired).
    report = json.loads(json.dumps(state["report"]))  # deep copy, JSON-safe
    for i, fig in enumerate(report.get("figures") or []):
        has_image = bridge.figure_image_path(job, i) is not None
        fig["image_url"] = f"/analyze/{job_id}/figures/{i}/image" if has_image else None
        cm = (fig.get("detectors") or {}).get("copy_move") or {}
        fig["overlay_url"] = (
            f"/analyze/{job_id}/figures/{i}/overlay"
            if has_image and cm.get("status") == "ok" and cm.get("forged")
            else None)
        fig.pop("image_path", None)  # local filesystem detail, not for clients
    report["job"] = {"job_id": state["job_id"], "label": state["label"],
                     "runtime_sec": state["runtime_sec"]}
    return report


# ---------------------------------------------------------------------------
# Figure images + overlays (serve existing pipeline outputs)
# ---------------------------------------------------------------------------


@app.get("/analyze/{job_id}/figures/{index}/image")
def figure_image(job_id: str, index: int) -> FileResponse:
    job = bridge.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")
    path = bridge.figure_image_path(job, index)
    if path is None:
        raise HTTPException(404, "No image for this figure.")
    return FileResponse(path, media_type="image/png")


@app.get("/analyze/{job_id}/figures/{index}/overlay")
def figure_overlay(job_id: str, index: int) -> FileResponse:
    job = bridge.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")
    figures = (job.report or {}).get("figures") or []
    if not (0 <= index < len(figures)):
        raise HTTPException(404, "No such figure.")
    cm = (figures[index].get("detectors") or {}).get("copy_move") or {}
    if not (cm.get("status") == "ok" and cm.get("forged")):
        raise HTTPException(404, "No copy-move regions were flagged on this figure.")
    path = bridge.overlay_image_path(job, index)
    if path is None:
        raise HTTPException(404, "Overlay unavailable.")
    return FileResponse(path, media_type="image/png")

"""Thin bridge between the FastAPI transport layer and the EXISTING pipeline.

This module contains ZERO detection or scoring logic. Its only jobs:

  * call the existing, unchanged ``src.pipeline.orchestrator.run_pipeline()``
    in a worker thread;
  * turn the orchestrator's EXISTING log lines (logger name "scholarguard")
    into structured progress events — the UI shows real pipeline progress,
    never fabricated steps;
  * hold per-job state (events, final report) in memory for the SSE stream.

The one nuance: the "scholarguard" logger is process-global, so the attached
handler filters records by thread id — each job only sees its own log lines,
even if two analyses run concurrently.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field

# Make the repo root importable so `src.` resolves when uvicorn runs from
# anywhere (server/ lives directly under the repo root).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

JOBS_DIR = os.path.join(REPO_ROOT, "server", "jobs")

# ---------------------------------------------------------------------------
# Job state
# ---------------------------------------------------------------------------


@dataclass
class Job:
    """One pipeline run. Everything the API needs to answer requests."""

    job_id: str
    pdf_path: str
    output_dir: str
    label: str = ""                       # display name (filename or example title)
    status: str = "queued"                # queued | running | completed | failed
    events: list[dict] = field(default_factory=list)
    report: dict | None = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    n_figures_total: int | None = None
    #: True when the bridge wrote pdf_path itself (an upload) and may delete it
    #: on eviction. False for the bundled example papers, which are repo files.
    owns_pdf: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def emit(self, kind: str, message: str, **extra) -> None:
        with self.lock:
            self.events.append({
                "kind": kind,
                "message": message,
                "t": round(time.time() - self.started_at, 2),
                **extra,
            })

    def set_status(self, status: str) -> None:
        with self.lock:
            self.status = status

    def status_now(self) -> str:
        with self.lock:
            return self.status

    def finish(self, status: str, report: dict | None = None,
               error: str | None = None) -> None:
        """Publish the terminal state in ONE locked update.

        report, error, finished_at and status have to become visible together.
        They used to be assigned separately, so a /result request landing
        between `job.report = report` and the `finally` that set finished_at saw
        a finished report with finished_at still None and computed
        `(0) - started_at` -- a large negative runtime that the UI rendered
        verbatim.

        Callers must emit their terminal progress event BEFORE calling this: the
        SSE generator stops as soon as it sees a terminal status with no
        unsent events, so flipping the status first can drop the last event.
        """
        with self.lock:
            if report is not None:
                self.report = report
            self.error = error
            self.finished_at = time.time()
            self.status = status

    def snapshot(self) -> dict:
        """A consistent view of the job for the HTTP layer."""
        with self.lock:
            runtime = (round(self.finished_at - self.started_at, 1)
                       if self.finished_at is not None else None)
            return {"job_id": self.job_id, "label": self.label,
                    "status": self.status, "report": self.report,
                    "error": self.error, "runtime_sec": runtime}


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()

# Retention policy for finished jobs. Each entry pins a whole report dict in
# memory and a directory of figure images + overlays on disk, and nothing ever
# removed them: a long-lived server grew without bound in both. Finished jobs
# are kept long enough for the UI to fetch the result and for a reload to still
# work, then reclaimed. Running jobs are never evicted.
MAX_RETAINED_JOBS = 50
JOB_TTL_SECONDS = 60 * 60


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _discard_job_artifacts(job: Job) -> None:
    """Delete the job's output directory, and its upload if we wrote it."""
    shutil.rmtree(job.output_dir, ignore_errors=True)
    if job.owns_pdf and job.pdf_path:
        try:
            os.remove(job.pdf_path)
        except OSError:
            pass


def _evict_stale_jobs(now: float | None = None) -> list[Job]:
    """Drop finished jobs past the TTL, then the oldest beyond the cap.

    Returns the evicted jobs so the caller can reclaim their disk outside the
    registry lock. Jobs still queued or running are never touched, however old.
    """
    now = time.time() if now is None else now
    with _jobs_lock:
        finished = [(jid, j) for jid, j in _jobs.items()
                    if j.finished_at is not None]
        doomed = {jid for jid, j in finished
                  if now - j.finished_at > JOB_TTL_SECONDS}
        survivors = [(jid, j) for jid, j in finished if jid not in doomed]
        overflow = len(_jobs) - len(doomed) - MAX_RETAINED_JOBS
        if overflow > 0:
            survivors.sort(key=lambda item: item[1].finished_at)
            doomed.update(jid for jid, _ in survivors[:overflow])
        evicted = [_jobs.pop(jid) for jid in doomed]
    for job in evicted:
        _discard_job_artifacts(job)
    return evicted


# ---------------------------------------------------------------------------
# Log -> progress-event translation (reads the orchestrator's EXISTING logs)
# ---------------------------------------------------------------------------

_PARSED_RE = re.compile(r"parsed '(?P<name>[^']+)': (?P<sections>\d+) section\(s\), (?P<figs>\d+) figure\(s\)")
_ANALYZING_RE = re.compile(r"analyzing (?P<label>.+)")
_RISK_RE = re.compile(r"paper risk: (?P<cat>\w+) \((?P<score>[\d.]+)/100\)")
_REPORT_RE = re.compile(r"report written: (?P<path>.+)")


class _JobLogHandler(logging.Handler):
    """Translates 'scholarguard' log records into progress events for ONE job.

    Filters by thread id so concurrent jobs never see each other's lines.
    """

    def __init__(self, job: Job, thread_ident: int):
        super().__init__(level=logging.INFO)
        self._job = job
        self._thread = thread_ident
        self._figure_index = 0

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        if record.thread != self._thread:
            return
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - a broken log line must not kill the run
            return

        m = _PARSED_RE.search(msg)
        if m:
            self._job.n_figures_total = int(m.group("figs"))
            self._job.emit("parsed", f"Parsed PDF — {m.group('figs')} figure(s), "
                                     f"{m.group('sections')} section(s)",
                           n_figures=int(m.group("figs")))
            return
        m = _ANALYZING_RE.search(msg)
        if m:
            self._figure_index += 1
            total = self._job.n_figures_total
            suffix = f" of {total}" if total else ""
            self._job.emit("figure", f"Analyzing {m.group('label')} "
                                     f"({self._figure_index}{suffix})",
                           index=self._figure_index, total=total,
                           label=m.group("label"))
            return
        m = _RISK_RE.search(msg)
        if m:
            self._job.emit("scored", f"Compiling report — overall risk "
                                     f"{m.group('score')}/100 ({m.group('cat')})")
            return
        if _REPORT_RE.search(msg):
            self._job.emit("saved", "Report written to disk")
            return
        if record.levelno >= logging.WARNING:
            self._job.emit("warning", msg)


# ---------------------------------------------------------------------------
# Running a job
# ---------------------------------------------------------------------------


def start_job(pdf_path: str, label: str, owns_pdf: bool = False) -> Job:
    """Create a Job and run the existing pipeline on a background thread.

    ``owns_pdf`` marks an uploaded file the bridge may delete when the job is
    evicted; the bundled example papers are repo files and must not be.
    """
    _evict_stale_jobs()
    job_id = uuid.uuid4().hex[:12]
    output_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)
    job = Job(job_id=job_id, pdf_path=pdf_path, output_dir=output_dir,
              label=label, owns_pdf=owns_pdf)
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run, args=(job,), daemon=True,
                              name=f"scholarguard-job-{job_id}")
    thread.start()
    return job


# ---------------------------------------------------------------------------
# Log-level custody, shared by every concurrently-running job.
#
# The "scholarguard" logger is process-global, so each worker used to save the
# level, raise it to INFO, and restore it in its own `finally`. With two jobs
# running, the first to finish restored the level captured BEFORE it started --
# silencing the second job's progress stream for the rest of its run. Refcount
# instead: the first job in raises the level, the last job out restores it.
# ---------------------------------------------------------------------------
_log_level_lock = threading.Lock()
_log_level_users = 0
_log_level_saved: int | None = None


def _acquire_progress_logging(logger: logging.Logger) -> None:
    global _log_level_users, _log_level_saved
    with _log_level_lock:
        if _log_level_users == 0:
            _log_level_saved = logger.level
            if logger.level > logging.INFO or logger.level == logging.NOTSET:
                logger.setLevel(logging.INFO)
        _log_level_users += 1


def _release_progress_logging(logger: logging.Logger) -> None:
    global _log_level_users, _log_level_saved
    with _log_level_lock:
        _log_level_users = max(0, _log_level_users - 1)
        if _log_level_users == 0 and _log_level_saved is not None:
            logger.setLevel(_log_level_saved)
            _log_level_saved = None


def _run(job: Job) -> None:
    """Worker: attach the log tap, call run_pipeline(), record the outcome."""
    from src.pipeline.orchestrator import run_pipeline  # existing, unmodified

    logger = logging.getLogger("scholarguard")
    _acquire_progress_logging(logger)
    handler = _JobLogHandler(job, threading.get_ident())
    logger.addHandler(handler)

    job.set_status("running")
    job.emit("started", "Parsing PDF…")
    try:
        report = run_pipeline(job.pdf_path, output_dir=job.output_dir)
        if report.get("status") == "failed":
            error = report.get("error") or "the pipeline could not read this PDF"
            # Terminal event first, THEN the status flip: the SSE generator
            # exits as soon as it sees a terminal status with nothing unsent.
            job.emit("failed", error)
            job.finish("failed", report=report, error=error)
        else:
            job.emit("completed", "Analysis complete")
            job.finish("completed", report=report)
    except Exception as exc:  # noqa: BLE001 - report, never crash the server
        job.emit("failed", f"Pipeline error: {exc}")
        job.finish("failed", error=str(exc))
    finally:
        logger.removeHandler(handler)
        _release_progress_logging(logger)


# ---------------------------------------------------------------------------
# Figure images + copy-move overlay (reuses EXISTING Stage 2 code, no new logic)
# ---------------------------------------------------------------------------


def figure_image_path(job: Job, index: int) -> str | None:
    """Absolute path of the extracted image for figure ``index`` (0-based)."""
    if not job.report:
        return None
    figures = job.report.get("figures") or []
    if not (0 <= index < len(figures)):
        return None
    path = figures[index].get("image_path")
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(REPO_ROOT, path)
    return path if os.path.isfile(path) else None


def overlay_image_path(job: Job, index: int) -> str | None:
    """Copy-move region overlay for one figure, generated lazily and cached.

    Calls the EXISTING ``detect_copy_move()`` (Stage 2, unchanged) purely for
    its ``visualization`` output — the same drawing the Stage 2 CLI writes.
    No visualization logic is reimplemented here.
    """
    src_path = figure_image_path(job, index)
    if src_path is None:
        return None
    cache = os.path.join(job.output_dir, "_overlays")
    os.makedirs(cache, exist_ok=True)
    out_path = os.path.join(cache, f"fig{index:02d}_overlay.png")
    if os.path.isfile(out_path):
        return out_path

    from src.detectors.copy_move_detector import detect_copy_move  # existing
    from src.utils.image_io import save_image                       # existing
    result = detect_copy_move(src_path)
    save_image(result["visualization"], out_path)
    return out_path

"""Tests for the API bridge's job bookkeeping.

server/ had no tests at all, which is where every concurrency defect in this
layer lived: the log-level restore race, the negative runtime window, the
unbounded job registry. The pipeline itself is stubbed out here -- this file is
about the bridge's own state machine, not about detection.
"""

import logging
import os
import threading
import time

import pytest

pytest.importorskip("fastapi")

from server import pipeline_bridge as bridge


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    """Every test gets a fresh job registry and a clean log-level refcount."""
    monkeypatch.setattr(bridge, "_jobs", {})
    monkeypatch.setattr(bridge, "_log_level_users", 0)
    monkeypatch.setattr(bridge, "_log_level_saved", None)
    yield


# ---------------------------------------------------------------- log level
def test_log_level_is_raised_and_restored_by_a_single_job():
    logger = logging.getLogger("scholarguard.test.solo")
    logger.setLevel(logging.WARNING)

    bridge._acquire_progress_logging(logger)
    assert logger.level == logging.INFO
    bridge._release_progress_logging(logger)
    assert logger.level == logging.WARNING


def test_concurrent_jobs_do_not_restore_each_others_log_level():
    """The first job to finish must not silence the one still running.

    Each worker used to snapshot the level, raise it, and restore its own
    snapshot in `finally`. With two jobs in flight the earlier finisher put the
    level back to WARNING while the other was mid-run, dropping the rest of its
    progress events.
    """
    logger = logging.getLogger("scholarguard.test.concurrent")
    logger.setLevel(logging.WARNING)

    bridge._acquire_progress_logging(logger)      # job A starts
    bridge._acquire_progress_logging(logger)      # job B starts
    assert logger.level == logging.INFO

    bridge._release_progress_logging(logger)      # job A finishes
    assert logger.level == logging.INFO, "job B is still running"

    bridge._release_progress_logging(logger)      # job B finishes
    assert logger.level == logging.WARNING


def test_log_level_refcount_never_goes_negative():
    logger = logging.getLogger("scholarguard.test.underflow")
    logger.setLevel(logging.ERROR)

    bridge._acquire_progress_logging(logger)
    bridge._release_progress_logging(logger)
    bridge._release_progress_logging(logger)      # stray extra release
    assert bridge._log_level_users == 0

    bridge._acquire_progress_logging(logger)
    assert logger.level == logging.INFO
    bridge._release_progress_logging(logger)
    assert logger.level == logging.ERROR


def test_log_level_custody_is_thread_safe():
    logger = logging.getLogger("scholarguard.test.threads")
    logger.setLevel(logging.WARNING)
    seen: list[int] = []

    def worker():
        bridge._acquire_progress_logging(logger)
        seen.append(logger.level)
        time.sleep(0.01)
        bridge._release_progress_logging(logger)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert seen == [logging.INFO] * 12, "a worker saw a suppressed log level"
    assert bridge._log_level_users == 0
    assert logger.level == logging.WARNING


# ------------------------------------------------------------- job lifecycle
def _job(**kw):
    return bridge.Job(job_id="j1", pdf_path="p.pdf", output_dir="o", **kw)


def test_finish_publishes_report_and_finish_time_together():
    """A /result landing mid-completion must never see a half-written job.

    report, error, finished_at and status used to be assigned one at a time, so
    a request between `job.report = report` and the `finally` that set
    finished_at read a finished report with finished_at None and computed
    (0 - started_at): a large negative runtime the UI printed verbatim.
    """
    job = _job()
    job.finish("completed", report={"status": "completed"})

    state = job.snapshot()
    assert state["status"] == "completed"
    assert state["report"] == {"status": "completed"}
    assert state["runtime_sec"] is not None
    assert state["runtime_sec"] >= 0


def test_snapshot_of_a_running_job_has_no_runtime():
    job = _job()
    job.set_status("running")
    state = job.snapshot()
    assert state["status"] == "running"
    assert state["report"] is None
    assert state["runtime_sec"] is None


def test_runtime_is_never_negative_under_concurrent_completion():
    """Hammer snapshot() while finish() runs; no reader may see a negative."""
    job = _job()
    seen: list[float | None] = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            seen.append(job.snapshot()["runtime_sec"])

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.02)
    job.finish("completed", report={"status": "completed"})
    time.sleep(0.02)
    stop.set()
    t.join()

    assert seen, "reader never sampled"
    assert all(v is None or v >= 0 for v in seen)


def test_failed_job_without_a_report_still_carries_its_error():
    job = _job()
    job.finish("failed", error="boom")
    state = job.snapshot()
    assert state["status"] == "failed"
    assert state["report"] is None
    assert state["error"] == "boom"
    assert state["runtime_sec"] >= 0


def test_terminal_event_is_recorded_before_the_status_flips():
    """The SSE generator stops on a terminal status; the last event must exist.

    _run emits its "completed"/"failed" event before calling finish(), so a
    stream that wakes on the status flip always finds the final event already
    in the list.
    """
    job = _job()
    job.emit("completed", "Analysis complete")
    job.finish("completed", report={"status": "completed"})

    with job.lock:
        kinds = [e["kind"] for e in job.events]
    assert kinds[-1] == "completed"
    assert job.status_now() == "completed"


# ------------------------------------------------------------- job retention
def _finished_job(jid, finished_at, tmp_path, owns_pdf=False):
    out = tmp_path / jid
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text("{}", encoding="utf-8")
    pdf = tmp_path / f"{jid}.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = bridge.Job(job_id=jid, pdf_path=str(pdf), output_dir=str(out),
                     owns_pdf=owns_pdf)
    job.finished_at = finished_at
    job.status = "completed"
    return job


def test_finished_jobs_past_the_ttl_are_evicted(tmp_path, monkeypatch):
    now = time.time()
    fresh = _finished_job("fresh", now - 10, tmp_path)
    stale = _finished_job("stale", now - bridge.JOB_TTL_SECONDS - 60, tmp_path)
    monkeypatch.setattr(bridge, "_jobs", {"fresh": fresh, "stale": stale})

    bridge._evict_stale_jobs(now=now)

    assert set(bridge._jobs) == {"fresh"}
    assert not os.path.exists(stale.output_dir), "disk was not reclaimed"
    assert os.path.exists(fresh.output_dir)


def test_running_jobs_are_never_evicted(tmp_path, monkeypatch):
    now = time.time()
    running = bridge.Job(job_id="run", pdf_path="p.pdf",
                         output_dir=str(tmp_path / "run"))
    running.status = "running"
    running.started_at = now - bridge.JOB_TTL_SECONDS * 10   # ancient
    stale = _finished_job("old", now - bridge.JOB_TTL_SECONDS - 1, tmp_path)
    monkeypatch.setattr(bridge, "_jobs", {"run": running, "old": stale})

    bridge._evict_stale_jobs(now=now)
    assert "run" in bridge._jobs, "an in-flight analysis was discarded"


def test_oldest_finished_jobs_are_dropped_beyond_the_cap(tmp_path, monkeypatch):
    now = time.time()
    monkeypatch.setattr(bridge, "MAX_RETAINED_JOBS", 3)
    jobs = {f"j{i}": _finished_job(f"j{i}", now - (10 - i), tmp_path)
            for i in range(6)}          # j0 oldest ... j5 newest
    monkeypatch.setattr(bridge, "_jobs", dict(jobs))

    bridge._evict_stale_jobs(now=now)

    assert set(bridge._jobs) == {"j3", "j4", "j5"}
    for gone in ("j0", "j1", "j2"):
        assert not os.path.exists(jobs[gone].output_dir)


def test_eviction_deletes_uploads_but_never_bundled_examples(tmp_path,
                                                             monkeypatch):
    now = time.time()
    upload = _finished_job("up", now - bridge.JOB_TTL_SECONDS - 1, tmp_path,
                           owns_pdf=True)
    example = _finished_job("ex", now - bridge.JOB_TTL_SECONDS - 1, tmp_path,
                            owns_pdf=False)
    monkeypatch.setattr(bridge, "_jobs", {"up": upload, "ex": example})

    bridge._evict_stale_jobs(now=now)

    assert not os.path.exists(upload.pdf_path), "the upload should be reclaimed"
    assert os.path.exists(example.pdf_path), (
        "a bundled example paper is a repo file and must never be deleted")


def test_starting_a_job_prunes_the_registry(tmp_path, monkeypatch):
    now = time.time()
    stale = _finished_job("stale", now - bridge.JOB_TTL_SECONDS - 60, tmp_path)
    monkeypatch.setattr(bridge, "_jobs", {"stale": stale})
    monkeypatch.setattr(bridge, "JOBS_DIR", str(tmp_path / "jobs"))
    # Do not actually run the pipeline.
    monkeypatch.setattr(bridge.threading, "Thread",
                        lambda *a, **k: type("T", (), {"start": lambda self: None})())

    job = bridge.start_job(str(tmp_path / "new.pdf"), label="new")

    assert "stale" not in bridge._jobs
    assert job.job_id in bridge._jobs

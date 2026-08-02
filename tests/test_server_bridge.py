"""Tests for the API bridge's job bookkeeping.

server/ had no tests at all, which is where every concurrency defect in this
layer lived: the log-level restore race, the negative runtime window, the
unbounded job registry. The pipeline itself is stubbed out here -- this file is
about the bridge's own state machine, not about detection.
"""

import logging
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

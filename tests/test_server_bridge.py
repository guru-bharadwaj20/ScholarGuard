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

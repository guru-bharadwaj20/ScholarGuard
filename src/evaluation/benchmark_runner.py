"""Run the full Stage 6 pipeline across the labeled evaluation set (Stage 7).

Runs ``orchestrator.run_pipeline`` on every paper, saving results after EACH
paper so a crash mid-run loses nothing, and supporting ``--resume`` to skip
papers already completed. Progress is logged with a running ETA.

This module only *invokes* the pipeline — it never touches detector logic.
"""

from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger("scholarguard.eval")

# Reuse the orchestrator's own sentinel so "auto" means the same thing on both
# sides (a fresh object() here would be seen by the orchestrator as an explicit
# — and broken — client).
from src.pipeline.orchestrator import _AUTO  # noqa: E402


def _load_existing(report_path: str) -> dict:
    """Load a prior benchmark_report.json for --resume (or an empty shell)."""
    if os.path.isfile(report_path):
        try:
            with open(report_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "results" in data:
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("could not read existing report (%s); starting fresh",
                           exc)
    return {"results": {}}


def _save(report: dict, report_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    tmp = report_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    os.replace(tmp, report_path)  # atomic — never leaves a half-written file


def _fmt_secs(s: float) -> str:
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:d}h{m:02d}m{sec:02d}s" if h else f"{m:d}m{sec:02d}s"


def _run_one_paper(task: tuple) -> tuple:
    """Run the pipeline on one paper in a worker process.

    Module-level (so it pickles) and self-contained: every worker imports the
    pipeline itself and pins its own thread pools to one thread. Without the
    pinning, each of N processes would open its own OpenCV/OpenMP pool sized to
    all cores and the processes would fight for them — measurably slower than
    running sequentially.

    Returns ``(paper_id, status, runtime_sec, pipeline_report)``.
    """
    paper, pipeline_config_path, output_dir = task

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("SCHOLARGUARD_TORCH_THREADS", "1")

    import cv2

    cv2.setNumThreads(1)

    from src.pipeline.orchestrator import run_pipeline

    start = time.perf_counter()
    try:
        report = run_pipeline(paper["pdf_path"],
                              config_path=pipeline_config_path,
                              output_dir=os.path.join(output_dir,
                                                      "pipeline_reports"))
        status = "ok"
    except Exception as exc:  # noqa: BLE001 - a pipeline bug shouldn't halt the batch
        report, status = None, f"pipeline_exception: {exc}"
    return paper["paper_id"], status, round(time.perf_counter() - start, 2), report


def _run_parallel(todo: list, pipeline_config_path: str, output_dir: str,
                  results: dict, report: dict, report_path: str,
                  save_intermediate: bool, workers: int) -> list[float]:
    """Run ``todo`` papers across ``workers`` processes; save as each finishes.

    Papers are independent — each reads its own package and writes its own
    per-paper report — so this only changes scheduling, not results. Saving on
    completion keeps the same crash-safety as the sequential path: whatever
    finished is on disk and ``--resume`` picks up the rest.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    per_paper_secs: list[float] = []
    tasks = [(p, pipeline_config_path, output_dir) for p in todo]
    logger.info("running %d paper(s) across %d worker process(es)",
                len(tasks), workers)
    wall_start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_one_paper, t): t[0]["paper_id"] for t in tasks}
        for done, future in enumerate(as_completed(futures), start=1):
            pid = futures[future]
            try:
                pid, status, elapsed, pipeline_report = future.result()
            except Exception as exc:  # noqa: BLE001 - a dead worker is one paper
                logger.error("%s: worker died (recorded, continuing): %s", pid, exc)
                status, elapsed, pipeline_report = f"worker_died: {exc}", 0.0, None
            per_paper_secs.append(elapsed)
            results[pid] = {
                "ground_truth": next(p for p in todo if p["paper_id"] == pid),
                "status": status,
                "runtime_sec": elapsed,
                "pipeline_report": pipeline_report,
            }
            if save_intermediate:
                _save(report, report_path)
            logger.info("[%d/%d] %s done in %s (wall %s)", done, len(tasks), pid,
                        _fmt_secs(elapsed),
                        _fmt_secs(time.perf_counter() - wall_start))
    return per_paper_secs


def run_benchmark(
    evaluation_set: dict,
    pipeline_config_path: str,
    output_dir: str = "outputs/stage7_results",
    save_intermediate: bool = True,
    resume: bool = True,
    llm_client=_AUTO,
    workers: int = 1,
) -> dict:
    """Run the pipeline on every paper in ``evaluation_set``.

    Returns ``{"results": {paper_id: {...}}, "meta": {...}}`` where each result
    holds the paper's ground-truth labels and the full pipeline report (or an
    error record). Papers with a missing PDF are recorded as ``skipped_missing``.

    ``workers`` > 1 runs papers in parallel processes. Papers are independent,
    so this changes scheduling only — not results. It is incompatible with a
    caller-supplied ``llm_client`` (a live client cannot be pickled into a
    worker), which raises rather than silently dropping the client and
    reporting claim-consistency as skipped.
    """
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "benchmark_report.json")
    report = _load_existing(report_path) if resume else {"results": {}}
    results = report["results"]

    from src.pipeline.orchestrator import run_pipeline

    papers = evaluation_set["papers"]
    todo = [p for p in papers if p["paper_id"] not in results]
    already = len(papers) - len(todo)
    if already:
        logger.info("resume: %d/%d paper(s) already done, %d to run",
                    already, len(papers), len(todo))

    # Missing-PDF papers are recorded up front in both modes: they cost nothing
    # to handle and keep the worker path free of the special case.
    runnable = []
    for paper in todo:
        if paper.get("pdf_exists", False):
            runnable.append(paper)
            continue
        logger.warning("%s: PDF missing — skipping", paper["paper_id"])
        results[paper["paper_id"]] = {"ground_truth": paper,
                                      "status": "skipped_missing",
                                      "pipeline_report": None}
        if save_intermediate:
            _save(report, report_path)

    if workers > 1:
        if llm_client is not _AUTO:
            raise ValueError(
                "workers > 1 cannot be combined with an explicit llm_client: a "
                "live client is not picklable into a worker process. Run with "
                "workers=1, or leave llm_client at its default so each worker "
                "builds its own from the environment.")
        per_paper_secs = _run_parallel(runnable, pipeline_config_path, output_dir,
                                       results, report, report_path,
                                       save_intermediate, workers)
        todo = runnable
    else:
        per_paper_secs = _run_sequential(runnable, pipeline_config_path, output_dir,
                                         results, report, report_path,
                                         save_intermediate, llm_client)
        todo = runnable

    report["meta"] = {
        "dataset_name": evaluation_set.get("dataset_name"),
        "note": evaluation_set.get("note"),
        "n_papers": len(papers),
        "n_completed": sum(1 for r in results.values() if r["status"] == "ok"),
        "n_skipped_missing": sum(1 for r in results.values()
                                 if r["status"] == "skipped_missing"),
        "pipeline_config": pipeline_config_path,
        "workers": workers,
        "total_runtime_sec": round(sum(per_paper_secs), 2),
    }
    _save(report, report_path)
    logger.info("benchmark complete: %d/%d papers, %s total CPU time",
                report["meta"]["n_completed"], len(papers),
                _fmt_secs(sum(per_paper_secs)))
    return report


def _run_sequential(todo: list, pipeline_config_path: str, output_dir: str,
                    results: dict, report: dict, report_path: str,
                    save_intermediate: bool, llm_client) -> list[float]:
    """Original one-paper-at-a-time path, unchanged in behaviour."""
    from src.pipeline.orchestrator import run_pipeline

    per_paper_secs: list[float] = []
    for idx, paper in enumerate(todo, start=1):
        pid = paper["paper_id"]

        eta = (sum(per_paper_secs) / len(per_paper_secs) * (len(todo) - idx + 1)
               if per_paper_secs else None)
        logger.info("[%d/%d] running %s%s", idx, len(todo), pid,
                    f"  (ETA {_fmt_secs(eta)})" if eta else "")

        start = time.perf_counter()
        try:
            pipeline_report = run_pipeline(
                paper["pdf_path"],
                config_path=pipeline_config_path,
                output_dir=os.path.join(output_dir, "pipeline_reports"),
                llm_client=llm_client,
            )
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - a pipeline bug shouldn't halt the batch
            logger.error("%s: pipeline raised (recorded, continuing): %s", pid, exc)
            pipeline_report = None
            status = f"pipeline_exception: {exc}"

        elapsed = time.perf_counter() - start
        per_paper_secs.append(elapsed)
        results[pid] = {
            "ground_truth": paper,
            "status": status,
            "runtime_sec": round(elapsed, 2),
            "pipeline_report": pipeline_report,
        }
        logger.info("[%d/%d] %s done in %s (elapsed total %s)",
                    idx, len(todo), pid, _fmt_secs(elapsed),
                    _fmt_secs(sum(per_paper_secs)))
        if save_intermediate:
            _save(report, report_path)

    return per_paper_secs


def main(argv=None) -> int:
    """CLI: run the full benchmark + analysis from eval_config.yaml."""
    import argparse
    import sys

    import yaml

    parser = argparse.ArgumentParser(
        description="ScholarGuard Stage 7 evaluation benchmark")
    parser.add_argument("--eval-config", default="src/config/eval_config.yaml")
    parser.add_argument("--no-resume", action="store_true",
                        help="ignore existing results and re-run every paper")
    parser.add_argument("--analyze-only", action="store_true",
                        help="skip running the pipeline; analyze an existing "
                             "benchmark_report.json")
    parser.add_argument("--workers", type=int, default=1,
                        help="run this many papers in parallel processes "
                             "(default 1 = sequential). Papers are independent, "
                             "so results are identical either way; each worker "
                             "pins its own thread pools to one thread")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be >= 1")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log = logging.getLogger("scholarguard")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    logging.getLogger("scholarguard.eval").setLevel(logging.INFO)

    with open(args.eval_config, encoding="utf-8") as fh:
        eval_cfg = yaml.safe_load(fh)
    output_dir = eval_cfg.get("output", {}).get("dir", "outputs/stage7_results")

    from src.evaluation import error_analysis
    from src.evaluation.ground_truth_loader import load_evaluation_set

    if args.analyze_only:
        report = _load_existing(os.path.join(output_dir, "benchmark_report.json"))
        if not report["results"]:
            log.error("no benchmark_report.json to analyze in %s", output_dir)
            return 1
    else:
        evaluation_set = load_evaluation_set(
            eval_cfg["evaluation_set"]["labels_path"])
        report = run_benchmark(
            evaluation_set,
            pipeline_config_path=eval_cfg["pipeline_config"],
            output_dir=output_dir,
            resume=not args.no_resume,
            workers=args.workers,
        )

    summary = error_analysis.analyze_benchmark(report, eval_cfg, output_dir)
    print("\n=== Stage 7 evaluation complete ===")
    print(f"  combined precision : {summary['combined_paper']['metrics']['precision']}")
    print(f"  combined recall    : {summary['combined_paper']['metrics']['recall']}")
    print(f"  false positives    : {summary['errors']['n_false_positives']}")
    print(f"  recommended cutoff : {summary['threshold_recommendation']['threshold']}")
    print(f"  summary written to : {summary['metrics_summary_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

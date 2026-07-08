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


def run_benchmark(
    evaluation_set: dict,
    pipeline_config_path: str,
    output_dir: str = "outputs/stage7_results",
    save_intermediate: bool = True,
    resume: bool = True,
    llm_client=_AUTO,
) -> dict:
    """Run the pipeline on every paper in ``evaluation_set``.

    Returns ``{"results": {paper_id: {...}}, "meta": {...}}`` where each result
    holds the paper's ground-truth labels and the full pipeline report (or an
    error record). Papers with a missing PDF are recorded as ``skipped_missing``.
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

    per_paper_secs: list[float] = []
    for idx, paper in enumerate(todo, start=1):
        pid = paper["paper_id"]

        if not paper.get("pdf_exists", False):
            logger.warning("[%d/%d] %s: PDF missing — skipping", idx, len(todo), pid)
            results[pid] = {"ground_truth": paper, "status": "skipped_missing",
                            "pipeline_report": None}
            if save_intermediate:
                _save(report, report_path)
            continue

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

    report["meta"] = {
        "dataset_name": evaluation_set.get("dataset_name"),
        "note": evaluation_set.get("note"),
        "n_papers": len(papers),
        "n_completed": sum(1 for r in results.values() if r["status"] == "ok"),
        "n_skipped_missing": sum(1 for r in results.values()
                                 if r["status"] == "skipped_missing"),
        "pipeline_config": pipeline_config_path,
        "total_runtime_sec": round(sum(per_paper_secs), 2),
    }
    _save(report, report_path)
    logger.info("benchmark complete: %d/%d papers, %s total",
                report["meta"]["n_completed"], len(papers),
                _fmt_secs(sum(per_paper_secs)))
    return report


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
    args = parser.parse_args(argv)

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

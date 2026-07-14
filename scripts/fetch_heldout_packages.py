#!/usr/bin/env python
"""Build a held-out evaluation set as PMC OA *packages* (format parity).

Why packages, and why both classes
-----------------------------------
Retracted image-fraud papers are almost never available as a main PDF in
PMC — only as OA packages (JATS XML + native figure images). To measure the
pipeline on real fraud we must ingest packages. And to keep the comparison
honest, the CLEAN controls must be ingested the SAME way — otherwise the
detectors could separate fraud (native images) from clean (PDF-extracted
images) by a format artifact rather than by manipulation.

So this script downloads BOTH classes as packages:

* **Fraud:** fresh image-retraction papers from Retraction Watch, resolved
  to PMC and downloaded as packages, EXCLUDING every DOI/PMCID already used
  in the calibration set (no train/test leakage).
* **Clean:** re-fetched as packages using the PMCIDs of the existing clean
  control set (same papers, package format), so the clean class is fixed and
  disjoint from the fraud class.

Each package is extracted to ``<output>/<category>/<PMCID>/`` and the
labels' ``pdf_path`` points at that directory; the orchestrator ingests it
via :func:`src.nlp.pmc_package.parse_pmc_package`.

Example:
    export NCBI_CONTACT_EMAIL=you@institution.edu
    python scripts/fetch_heldout_packages.py --fraud-target 30
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests  # noqa: E402
from tqdm import tqdm  # noqa: E402

from src.data_acquisition import labels_builder  # noqa: E402
from src.data_acquisition import retraction_watch as rw  # noqa: E402
from src.data_acquisition.doi_resolver import resolve_dois_to_pmcids  # noqa: E402
from src.data_acquisition.pmc_oa_fetch import (  # noqa: E402
    DOWNLOAD_SIZE_CAP,
    download_package_ex,
    resolve_oa_package,
)
from src.data_acquisition.pmc_search import get_contact_email  # noqa: E402
from src.data_acquisition.rate_limiter import RateLimiter  # noqa: E402
from src.nlp.pmc_package import extract_package  # noqa: E402

logger = logging.getLogger("scholarguard.data")


def _load_papers(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    return data["papers"] if isinstance(data, dict) else data


def _download_and_extract(pmcid: str, category_dir: str, args,
                          session, limiter) -> str | None:
    """Download a PMCID's OA package and extract it. Returns the package dir."""
    oa = resolve_oa_package(pmcid, session=session, rate_limiter=limiter)
    if oa.get("error") or not oa.get("tgz_url"):
        return None
    pkg_dir = os.path.join(category_dir, pmcid)
    if os.path.isdir(pkg_dir) and any(n.endswith(".nxml") for n in os.listdir(pkg_dir)):
        return pkg_dir  # already fetched
    os.makedirs(category_dir, exist_ok=True)
    tgz = os.path.join(category_dir, f"{pmcid}.tar.gz")
    ok, outcome = download_package_ex(oa["tgz_url"], tgz,
                                      max_size_mb=args.max_package_mb,
                                      session=session, rate_limiter=limiter)
    if not ok:
        if outcome == DOWNLOAD_SIZE_CAP:
            logger.info("%s: over size cap, skipping", pmcid)
        return None
    try:
        extracted = extract_package(tgz, category_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s: extract failed: %s", pmcid, exc)
        return None
    finally:
        if os.path.isfile(tgz):
            os.remove(tgz)  # keep only the extracted dir
    return extracted


def collect_fraud(args, session, limiter, used_dois, used_pmcids) -> list[dict]:
    df = rw.load_retraction_watch(args.rw_repo)
    image_df = rw.filter_image_related(df)
    logger.info("%d image-related formal retractions in the database", len(image_df))

    rows_by_doi, fresh_dois = {}, []
    for _, row in image_df.head(args.max_scan).iterrows():
        doi = rw.normalize_doi(row["OriginalPaperDOI"])
        if not doi or doi in used_dois or doi in rows_by_doi:
            continue
        rows_by_doi[doi] = row
        fresh_dois.append(doi)
    logger.info("%d fresh candidate fraud DOIs after exclusion", len(fresh_dois))

    doi_to_pmcid = resolve_dois_to_pmcids(
        fresh_dois, batch_size=args.batch_size, session=session, rate_limiter=limiter)

    fraud_dir = os.path.join(args.output_dir, "fraud_cases")
    entries: list[dict] = []
    progress = tqdm(total=args.fraud_target, unit="pkg", desc="fraud packages",
                    dynamic_ncols=True)
    for doi, pmcid in doi_to_pmcid.items():
        if len(entries) >= args.fraud_target:
            break
        if not pmcid or pmcid.upper() in used_pmcids:
            continue
        used_pmcids.add(pmcid.upper())
        pkg_dir = _download_and_extract(pmcid, fraud_dir, args, session, limiter)
        if not pkg_dir:
            continue
        row = rows_by_doi.get(doi)
        entries.append(labels_builder.build_labels_entry(
            pmcid=pmcid, doi=doi,
            title=str(row["Title"]) if row is not None else "",
            category="fraud",
            fraud_type=rw.reason_to_fraud_type(str(row["Reason"]))
            if row is not None else "copy_move",
            retraction_reason=str(row["Reason"]) if row is not None else None,
            pdf_path=os.path.relpath(pkg_dir).replace("\\", "/")))
        progress.update(1)
        logger.info("fraud package %s (%s)", pmcid, doi)
    progress.close()
    return entries


def collect_clean(args, session, limiter) -> list[dict]:
    """Re-fetch the existing clean controls as packages (same papers)."""
    clean_pmcids = [p["paper_id"] for p in _load_papers(args.clean_from)
                    if not p.get("is_fraudulent")]
    logger.info("re-fetching %d clean control paper(s) as packages", len(clean_pmcids))
    clean_dir = os.path.join(args.output_dir, "clean_control_papers")
    entries: list[dict] = []
    progress = tqdm(total=len(clean_pmcids), unit="pkg", desc="clean packages",
                    dynamic_ncols=True)
    for pmcid in clean_pmcids:
        pkg_dir = _download_and_extract(pmcid, clean_dir, args, session, limiter)
        progress.update(1)
        if not pkg_dir:
            continue
        entries.append(labels_builder.build_labels_entry(
            pmcid=pmcid, doi="", title="", category="clean",
            pdf_path=os.path.relpath(pkg_dir).replace("\\", "/")))
    progress.close()
    return entries


def run(args) -> int:
    get_contact_email()
    session, limiter = requests.Session(), RateLimiter()
    os.makedirs(args.output_dir, exist_ok=True)

    used_dois, used_pmcids = set(), set()
    for path in args.exclude:
        for p in _load_papers(path):
            if p.get("doi"):
                used_dois.add(rw.normalize_doi(p["doi"]))
            if p.get("paper_id"):
                used_pmcids.add(p["paper_id"].upper())
    logger.info("excluding %d DOIs / %d PMCIDs (calibration set)",
                len(used_dois), len(used_pmcids))

    fraud = collect_fraud(args, session, limiter, used_dois, used_pmcids)
    clean = collect_clean(args, session, limiter)
    papers = fraud + clean

    labels_path = os.path.join(args.output_dir, "labels.json")
    labels = {
        "dataset_name": "real_heldout_packages",
        "note": ("Held-out PMC OA packages (JATS XML + native figure images). "
                 "Fraud = fresh image-retraction papers disjoint from the "
                 "calibration set; clean = calibration-disjoint controls, same "
                 "package format for parity."),
        "papers": papers,
    }
    with open(labels_path, "w", encoding="utf-8") as fh:
        json.dump(labels, fh, indent=2)

    print(f"\nHeld-out package set: {len(fraud)} fraud / {len(clean)} clean "
          f"-> {labels_path}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fraud-target", type=int, default=30)
    p.add_argument("--output-dir", default="data/heldout_packages")
    p.add_argument("--clean-from", default="data/heldout_set/labels.json",
                   help="labels.json whose clean PMCIDs are re-fetched as packages")
    p.add_argument("--exclude", nargs="*",
                   default=["data/evaluation_set/labels.json"],
                   help="labels.json files whose papers must be excluded (fraud)")
    p.add_argument("--rw-repo", default="retraction-watch-data")
    p.add_argument("--max-scan", type=int, default=100000)
    p.add_argument("--max-package-mb", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=200)
    return p


def main(argv=None) -> int:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log = logging.getLogger("scholarguard")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    return run(build_arg_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

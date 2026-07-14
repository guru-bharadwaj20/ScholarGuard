#!/usr/bin/env python
"""Top up a held-out set with FRESH image-fraud papers not seen in calibration.

Why this exists
---------------
``fetch_evaluation_set.py`` scans the *newest* image retractions and keeps the
first N that happen to be in the PMC Open Access subset with a downloadable
PDF. Re-running it therefore returns the SAME handful of papers — every fraud
case it found for the held-out set was already in the 25-paper calibration set,
so removing the overlap would leave zero positives and make ROC-AUC undefined.

This script instead scans DEEPER into the image-retraction list and explicitly
EXCLUDES every DOI / PMCID already used (calibration set + existing held-out
set), downloading only genuinely unseen fraud papers and appending them to the
held-out ``labels.json``. It reuses the project's tested resolution/download
code unchanged (``resolve_oa_package`` / ``download_package_ex`` /
``resolve_dois_to_pmcids`` / ``labels_builder``).

Example:
    export NCBI_CONTACT_EMAIL=you@institution.edu
    python scripts/fetch_fresh_fraud.py --target 10

Requires NCBI_CONTACT_EMAIL; NCBI_API_KEY optional (3 -> 10 req/s).
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

logger = logging.getLogger("scholarguard.data")


def _load_used(paths: list[str]) -> tuple[set[str], set[str]]:
    """Return (used_pmcids, used_dois) across every existing labels.json."""
    pmcids: set[str] = set()
    dois: set[str] = set()
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        papers = data["papers"] if isinstance(data, dict) else data
        for p in papers:
            if p.get("paper_id"):
                pmcids.add(p["paper_id"].upper())
            if p.get("doi"):
                dois.add(rw.normalize_doi(p["doi"]))
    return pmcids, dois


def _load_labels(path: str) -> dict:
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "papers" in data:
            return data
        if isinstance(data, list):
            return {"papers": data}
    return {"papers": []}


def run(args) -> int:
    get_contact_email()  # raises a clear error if NCBI_CONTACT_EMAIL is unset
    session = requests.Session()
    limiter = RateLimiter()

    labels_path = os.path.join(args.output_dir, "labels.json")
    fraud_dir = os.path.join(args.output_dir, "fraud_cases")
    os.makedirs(fraud_dir, exist_ok=True)

    exclude = [labels_path] + list(args.exclude)
    used_pmcids, used_dois = _load_used(exclude)
    logger.info("excluding %d PMCIDs / %d DOIs already used (calibration + held-out)",
                len(used_pmcids), len(used_dois))

    df = rw.load_retraction_watch(args.rw_repo)
    image_df = rw.filter_image_related(df)
    logger.info("%d image-related formal retractions in the database", len(image_df))

    # Candidate DOIs = image retractions NOT already used, scanned as deep as
    # --max-scan (default: the whole list, so we reach past the top hits the
    # other script keeps re-finding).
    rows_by_doi = {}
    fresh_dois: list[str] = []
    for _, row in image_df.head(args.max_scan).iterrows():
        doi = rw.normalize_doi(row["OriginalPaperDOI"])
        if not doi or doi in used_dois or doi in rows_by_doi:
            continue
        rows_by_doi[doi] = row
        fresh_dois.append(doi)
    logger.info("%d fresh candidate DOIs after exclusion", len(fresh_dois))

    doi_to_pmcid = resolve_dois_to_pmcids(
        fresh_dois, batch_size=args.batch_size, session=session, rate_limiter=limiter)

    labels = _load_labels(labels_path)
    new_entries: list[dict] = []
    progress = tqdm(total=args.target, unit="pdf", desc="fresh fraud PDFs",
                    dynamic_ncols=True)
    for doi, pmcid in doi_to_pmcid.items():
        if len(new_entries) >= args.target:
            break
        if not pmcid or pmcid.upper() in used_pmcids:
            continue
        used_pmcids.add(pmcid.upper())

        oa = resolve_oa_package(pmcid, session=session, rate_limiter=limiter)
        if oa.get("error") or not oa.get("pdf_url"):
            continue
        dest = os.path.join(fraud_dir, f"{pmcid}.pdf")
        if not os.path.isfile(dest):
            ok, outcome = download_package_ex(
                oa["pdf_url"], dest, max_size_mb=args.max_package_mb,
                session=session, rate_limiter=limiter)
            if not ok:
                if outcome == DOWNLOAD_SIZE_CAP:
                    logger.info("%s: over size cap, skipping", pmcid)
                continue

        row = rows_by_doi.get(doi)
        entry = labels_builder.build_labels_entry(
            pmcid=pmcid, doi=doi,
            title=str(row["Title"]) if row is not None else "",
            category="fraud",
            fraud_type=rw.reason_to_fraud_type(str(row["Reason"]))
            if row is not None else "copy_move",
            retraction_reason=str(row["Reason"]) if row is not None else None,
            pdf_path=os.path.relpath(dest).replace("\\", "/"),
        )
        new_entries.append(entry)
        labels["papers"].append(entry)
        progress.update(1)
        logger.info("downloaded fresh fraud paper %s (%s)", pmcid, doi)
    progress.close()

    if new_entries:
        with open(labels_path, "w", encoding="utf-8") as fh:
            json.dump(labels, fh, indent=2)
        logger.info("appended %d fresh fraud paper(s) to %s",
                    len(new_entries), labels_path)
    else:
        logger.warning("no fresh fraud papers could be downloaded — try raising "
                       "--max-scan or --target")

    n_fraud = sum(1 for p in labels["papers"] if p.get("is_fraudulent"))
    n_clean = len(labels["papers"]) - n_fraud
    print(f"\nHeld-out set now: {n_fraud} fraud / {n_clean} clean "
          f"(+{len(new_entries)} fresh fraud this run)")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", type=int, default=10,
                   help="how many FRESH fraud papers to add")
    p.add_argument("--output-dir", default="data/heldout_set")
    p.add_argument("--exclude", nargs="*",
                   default=["data/evaluation_set/labels.json"],
                   help="labels.json files whose papers must be excluded "
                        "(the held-out labels.json is always excluded too)")
    p.add_argument("--rw-repo", default="retraction-watch-data")
    p.add_argument("--max-scan", type=int, default=100000,
                   help="how many image-retraction rows to scan (default: all)")
    p.add_argument("--max-package-mb", type=int, default=50)
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

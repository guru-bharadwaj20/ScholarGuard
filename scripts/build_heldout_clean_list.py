#!/usr/bin/env python
"""Select the held-out CLEAN control PMCIDs — without downloading any PDF.

Why this exists
---------------
``fetch_heldout_packages.py`` re-fetches the clean class as OA *packages*,
reading the PMCIDs from a ``labels.json`` given by ``--clean-from`` (it uses
only ``paper_id`` / ``is_fraudulent``). The only existing producer of that
file, ``fetch_evaluation_set.py``, downloads a full **PDF** per clean paper
first — ~1 GB for 58 papers that the package benchmark never opens, because
package ingestion reads the JATS XML + native images instead.

This script performs the *same clean selection* as
``fetch_evaluation_set.collect_clean_controls`` — identical search terms
(dose-response + generic), identical screen against the FULL Retraction Watch
DOI list, so a retracted paper can never enter the clean class — but stops at
the PMCID list and writes ``labels.json`` with an empty ``pdf_path``, which
``fetch_heldout_packages.py`` then fills in with the extracted package dir.

Calibration disjointness is explicit: every PMCID/DOI in ``--exclude`` is
dropped, so the held-out clean class shares no paper with the 25-paper
calibration set.

Example:
    export NCBI_CONTACT_EMAIL=you@institution.edu
    python scripts/build_heldout_clean_list.py --clean-target 58

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

from src.data_acquisition import labels_builder  # noqa: E402
from src.data_acquisition import retraction_watch as rw  # noqa: E402
from src.data_acquisition.doi_resolver import resolve_pmcids_to_dois  # noqa: E402
from src.data_acquisition.pmc_search import get_contact_email, search_pmc  # noqa: E402
from src.data_acquisition.rate_limiter import RateLimiter  # noqa: E402

# Imported from the PDF-based builder so the two selections cannot drift.
from scripts.fetch_evaluation_set import (  # noqa: E402
    DOSE_RESPONSE_TERMS,
    GENERIC_TERMS,
)

logger = logging.getLogger("scholarguard.data")


def _excluded_ids(paths: list[str]) -> tuple[set[str], set[str]]:
    """Return (pmcids, dois) already used by another labels.json."""
    pmcids: set[str] = set()
    dois: set[str] = set()
    for path in paths:
        if not os.path.isfile(path):
            logger.warning("exclude file not found (ignored): %s", path)
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for paper in (data["papers"] if isinstance(data, dict) else data):
            if paper.get("paper_id"):
                pmcids.add(paper["paper_id"].upper())
            if paper.get("doi"):
                dois.add(rw.normalize_doi(paper["doi"]))
    return pmcids, dois


def collect(args) -> list[dict]:
    get_contact_email()  # fail fast with the policy message
    session, limiter = requests.Session(), RateLimiter()

    used_pmcids, used_dois = _excluded_ids(args.exclude)
    logger.info("excluding %d PMCIDs / %d DOIs (calibration set)",
                len(used_pmcids), len(used_dois))

    retracted = rw.retracted_doi_set(rw.load_retraction_watch(args.rw_repo))
    logger.info("%d retracted DOIs to screen the clean class against",
                len(retracted))

    dose_target = min(args.dose_response_count, args.clean_target)
    plan = [("dose_response", DOSE_RESPONSE_TERMS, dose_target),
            ("generic", GENERIC_TERMS, args.clean_target - dose_target)]

    entries: list[dict] = []
    for subset, terms, target in plan:
        if target <= 0:
            continue
        pmcids: list[str] = []
        for term in terms:
            pmcids.extend(search_pmc(term, retmax=args.retmax_per_term,
                                     session=session, rate_limiter=limiter))
        pmcids = [p for p in dict.fromkeys(pmcids) if p.upper() not in used_pmcids]
        logger.info("clean/%s: %d candidate PMCIDs for target %d",
                    subset, len(pmcids), target)

        pmcid_to_doi = resolve_pmcids_to_dois(
            pmcids, batch_size=args.batch_size,
            session=session, rate_limiter=limiter)

        kept = 0
        unscreened = 0
        for pmcid in pmcids:
            if kept >= target:
                break
            doi = rw.normalize_doi(pmcid_to_doi.get(pmcid) or "")
            if not doi:
                # FAIL CLOSED. Without a DOI the Retraction Watch screen cannot
                # run, so admitting this paper would put an *unscreened* article
                # into the clean class -- and a single idconv 429 used to do
                # exactly that, silently, for a whole batch. A clean control we
                # could not verify is worse than one fewer clean control.
                unscreened += 1
                continue
            if doi in retracted or doi in used_dois:
                logger.info("%s (%s): retracted or already used — excluded",
                            pmcid, doi)
                continue
            used_pmcids.add(pmcid.upper())
            entries.append(labels_builder.build_labels_entry(
                pmcid=pmcid, doi=doi, title="", category="clean",
                pdf_path="",           # filled in by fetch_heldout_packages.py
                subset=subset))
            kept += 1
        logger.info("clean/%s: selected %d (%d candidate(s) dropped unscreened: "
                    "no DOI resolved)", subset, kept, unscreened)
        if kept < target:
            logger.warning("clean/%s: only %d of %d targeted — candidates ran "
                           "out after screening", subset, kept, target)

    return entries


def run(args) -> int:
    entries = collect(args)
    labels_builder.write_labels_json(
        entries, args.output,
        dataset_name="scholarguard_heldout_clean_pmcids",
        note=("Clean-control PMCID list for the held-out set. Selected by the "
              "same terms and Retraction-Watch screen as "
              "fetch_evaluation_set.collect_clean_controls, disjoint from the "
              "calibration set, with NO PDF downloaded: pdf_path is empty and "
              "is populated by fetch_heldout_packages.py once each paper is "
              "fetched as an OA package."))
    print(f"\nSelected {len(entries)} clean control PMCIDs -> {args.output}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--clean-target", type=int, default=58)
    p.add_argument("--dose-response-count", type=int, default=20,
                   help="subset of --clean-target sourced from dose-response "
                        "terms (a known false-positive trap)")
    p.add_argument("--output", default="data/heldout_set/labels.json")
    p.add_argument("--exclude", nargs="*",
                   default=["data/evaluation_set/labels.json"],
                   help="labels.json files whose papers must not be reused")
    p.add_argument("--rw-repo", default="retraction-watch-data")
    p.add_argument("--retmax-per-term", type=int, default=200)
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

#!/usr/bin/env python
"""Build a real corpus of scientific figures from PubMed Central Open Access.

Searches PMC's open-access subset for the given terms, downloads each paper's
OA package, extracts and dimension-filters the figure images, and saves them
to a target folder — skipping retracted papers, respecting NCBI rate limits,
and recording everything in a resumable manifest.

Examples:
    python scripts/fetch_corpus.py --search-terms "western blot" "immunoblot" \
        --target-count 300 --output-dir data/clean
    python scripts/fetch_corpus.py --search-terms "microscopy panel" \
        --target-count 150 --output-dir data/figure_corpus

Requires the NCBI_CONTACT_EMAIL environment variable (NCBI usage policy).
Set NCBI_API_KEY to raise the rate limit from 3 to 10 requests/second.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import logging
import os
import sys

# Make `src` importable when run as `python scripts/fetch_corpus.py`.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests  # noqa: E402
from tqdm import tqdm  # noqa: E402

from src.data_acquisition import manifest as manifest_mod  # noqa: E402
from src.data_acquisition.figure_extractor import (  # noqa: E402
    extract_article_metadata,
    extract_figures,
)
from src.data_acquisition.pmc_oa_fetch import (  # noqa: E402
    DOWNLOAD_SIZE_CAP,
    download_package_ex,
    resolve_oa_package,
)
from src.data_acquisition.pmc_search import get_contact_email, search_pmc  # noqa: E402
from src.data_acquisition.rate_limiter import RateLimiter  # noqa: E402

logger = logging.getLogger("scholarguard.data")

# Skip reason labels (also used to group the final summary).
SKIP_RETRACTED = "retracted"
SKIP_NO_PACKAGE = "no OA package"
SKIP_DOWNLOAD_FAILED = "download failed"
SKIP_SIZE_CAP = "size cap exceeded"
SKIP_NO_IMAGES = "no qualifying images"
SKIP_ERROR = "unexpected error"


def _process_paper(pmcid, args, session, limiter):
    """Handle one paper. Returns (manifest_entry, n_images, skip_reason|None)."""
    oa = resolve_oa_package(pmcid, session=session, rate_limiter=limiter)
    base_entry = {
        "pmcid": pmcid, "doi": None, "title": None,
        "license": oa.get("license"), "retracted": oa.get("retracted", False),
        "images": [], "n_images": 0,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    if oa.get("error") or (not oa.get("tgz_url") and not oa.get("pdf_url")):
        reason = SKIP_RETRACTED if oa.get("retracted") else SKIP_NO_PACKAGE
        return {**base_entry, "status": "skipped", "reason": oa.get("error") or reason}, 0, reason

    if oa["retracted"]:
        # Retracted papers are excluded from the CLEAN corpus (recorded so a
        # re-run doesn't fetch them again).
        return {**base_entry, "status": "skipped_retracted",
                "reason": SKIP_RETRACTED}, 0, SKIP_RETRACTED

    # Prefer the full package (tgz, contains all figures + article XML); fall
    # back to the PDF only if no tgz is offered.
    url = oa.get("tgz_url") or oa.get("pdf_url")
    ext = ".tar.gz" if url == oa.get("tgz_url") else ".pdf"
    dest = os.path.join(args.raw_dir, f"{pmcid}{ext}")

    if not os.path.isfile(dest):
        ok, outcome = download_package_ex(
            url, dest, max_size_mb=args.max_package_mb,
            session=session, rate_limiter=limiter)
        if not ok:
            if outcome == DOWNLOAD_SIZE_CAP:
                # Deterministic: the package will always be too big. Terminal,
                # so a re-run never re-downloads a huge supplementary bundle.
                return {**base_entry, "status": "skipped_too_large",
                        "reason": SKIP_SIZE_CAP}, 0, SKIP_SIZE_CAP
            # Transient: recorded as retryable so a later run attempts it again.
            return {**base_entry, "status": "download_failed", "retryable": True,
                    "reason": SKIP_DOWNLOAD_FAILED}, 0, SKIP_DOWNLOAD_FAILED

    meta = extract_article_metadata(dest) if ext == ".tar.gz" else {}
    images = extract_figures(dest, args.output_dir, pmcid,
                             min_dim=args.min_image_dim)
    entry = {**base_entry, "doi": meta.get("doi"), "title": meta.get("title"),
             "images": images, "n_images": len(images),
             "package_format": ext.lstrip(".")}

    if not images:
        return {**entry, "status": "no_images", "reason": SKIP_NO_IMAGES}, 0, SKIP_NO_IMAGES
    return {**entry, "status": "ok", "reason": None}, len(images), None


def run(args) -> dict:
    """Execute the corpus build; return a summary dict."""
    get_contact_email()  # fail fast with a clear message if the email is unset
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.raw_dir, exist_ok=True)

    session = requests.Session()
    limiter = RateLimiter()  # auto 3/s, or 10/s if NCBI_API_KEY is set
    logger.info("rate limit: %.0f req/s%s", limiter.requests_per_second,
                " (NCBI_API_KEY detected)" if os.environ.get("NCBI_API_KEY") else "")

    skips: collections.Counter = collections.Counter()
    papers_processed = 0
    images_saved = 0

    progress = tqdm(total=args.target_count, unit="img",
                    desc="figures saved", dynamic_ncols=True)
    try:
        for term in args.search_terms:
            if images_saved >= args.target_count:
                break
            pmcids = search_pmc(term, retmax=args.retmax_per_term,
                                session=session, rate_limiter=limiter)
            for pmcid in pmcids:
                if images_saved >= args.target_count:
                    break
                if manifest_mod.is_processed(pmcid, args.manifest,
                                             retry_failed=not args.no_retry_failed):
                    logger.info("%s already in manifest - skipping", pmcid)
                    continue
                try:
                    entry, n_imgs, reason = _process_paper(pmcid, args, session, limiter)
                except Exception as exc:  # noqa: BLE001 - never crash the run
                    logger.warning("%s: unexpected error, skipping: %s", pmcid, exc)
                    entry = {"pmcid": pmcid, "status": "error", "retryable": True,
                             "reason": SKIP_ERROR, "error": str(exc),
                             "timestamp": datetime.datetime.now().isoformat(
                                 timespec="seconds")}
                    n_imgs, reason = 0, SKIP_ERROR

                manifest_mod.add_entry(entry, args.manifest)
                papers_processed += 1
                if reason:
                    skips[reason] += 1
                if n_imgs:
                    images_saved += n_imgs
                    progress.update(n_imgs)
    finally:
        progress.close()

    return {"papers_processed": papers_processed, "images_saved": images_saved,
            "skips": dict(skips), "output_dir": args.output_dir,
            "manifest": args.manifest}


def _print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("  ScholarGuard corpus build — summary")
    print("=" * 60)
    print(f"  papers processed : {summary['papers_processed']}")
    print(f"  images saved     : {summary['images_saved']}  -> {summary['output_dir']}")
    if summary["skips"]:
        print("  papers skipped (by reason):")
        for reason, n in sorted(summary["skips"].items(), key=lambda kv: -kv[1]):
            print(f"    - {reason}: {n}")
    else:
        print("  papers skipped   : 0")
    print(f"  manifest         : {summary['manifest']}")
    print("=" * 60)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a clean PMC-OA figure corpus")
    p.add_argument("--search-terms", nargs="+", required=True,
                   help='one or more search terms, e.g. "western blot" "immunoblot"')
    p.add_argument("--target-count", type=int, default=300,
                   help="stop once this many images are saved across all terms")
    p.add_argument("--output-dir", default="data/clean")
    p.add_argument("--min-image-dim", type=int, default=200,
                   help="minimum shorter-side length (px) to keep an image")
    p.add_argument("--max-package-mb", type=int, default=50,
                   help="skip packages larger than this (MB)")
    p.add_argument("--retmax-per-term", type=int, default=200,
                   help="max PMCIDs to fetch per search term")
    p.add_argument("--manifest", default="data/manifest.json")
    p.add_argument("--raw-dir", default="data/raw_downloads")
    p.add_argument("--no-retry-failed", action="store_true",
                   help="treat every recorded PMCID as done, including papers "
                        "whose download previously failed (default: retry those)")
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log = logging.getLogger("scholarguard.data")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)

    try:
        summary = run(args)
    except RuntimeError as exc:  # e.g. missing NCBI_CONTACT_EMAIL
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

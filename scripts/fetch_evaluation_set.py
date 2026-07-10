#!/usr/bin/env python
"""Build the REAL evaluation set: documented image-fraud cases + clean controls.

Cross-references the Retraction Watch database against the PMC Open Access
subset to find real, formally-retracted image-manipulation papers with
downloadable PDFs, plus clean control papers (including dose-response series —
a known false-positive trap found in Stage 7's synthetic run). Emits a
``labels.json`` that Stage 7's ground_truth_loader consumes unchanged.

Unlike scripts/fetch_corpus.py (which extracts figure images), this saves the
**full PDF** of each paper, because Stage 5's pdf_parser needs the whole
document — captions and results text intact.

Reuses, unchanged: pmc_oa_fetch.resolve_oa_package / download_package_ex,
pmc_search.search_pmc, rate_limiter.RateLimiter, and manifest's atomic,
terminal-vs-transient resumability.

Example:
    python scripts/fetch_evaluation_set.py --fraud-target 15 --clean-target 10

Requires NCBI_CONTACT_EMAIL; NCBI_API_KEY optional (3 -> 10 req/s).
"""

from __future__ import annotations

import argparse
import collections
import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests  # noqa: E402
from tqdm import tqdm  # noqa: E402

from src.data_acquisition import labels_builder, manifest as manifest_mod  # noqa: E402
from src.data_acquisition import retraction_watch as rw  # noqa: E402
from src.data_acquisition.doi_resolver import (  # noqa: E402
    resolve_dois_to_pmcids,
    resolve_pmcids_to_dois,
)
from src.data_acquisition.pmc_oa_fetch import (  # noqa: E402
    DOWNLOAD_SIZE_CAP,
    download_package_ex,
    resolve_oa_package,
)
from src.data_acquisition.pmc_search import get_contact_email, search_pmc  # noqa: E402
from src.data_acquisition.rate_limiter import RateLimiter  # noqa: E402

logger = logging.getLogger("scholarguard.data")

DOSE_RESPONSE_TERMS = ["dose response western blot", "dose dependent immunoblot"]
GENERIC_TERMS = ["gene expression analysis", "protein expression profiling"]

SKIP_NO_PDF = "no OA PDF available"
SKIP_SIZE_CAP = "size cap exceeded"
SKIP_DOWNLOAD_FAILED = "download failed"
SKIP_RETRACTED = "retracted (excluded from clean set)"
SKIP_IN_RW = "DOI present in Retraction Watch"
SKIP_ERROR = "unexpected error"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _fetch_pdf(pmcid: str, dest_dir: str, args, session, limiter):
    """Resolve + download one paper's PDF. Returns (pdf_path|None, oa, reason)."""
    oa = resolve_oa_package(pmcid, session=session, rate_limiter=limiter)
    if oa.get("error") or not oa.get("pdf_url"):
        return None, oa, (oa.get("error") or SKIP_NO_PDF)

    dest = os.path.join(dest_dir, f"{pmcid}.pdf")
    if os.path.isfile(dest):
        return dest, oa, None

    ok, outcome = download_package_ex(oa["pdf_url"], dest,
                                      max_size_mb=args.max_package_mb,
                                      session=session, rate_limiter=limiter)
    if ok:
        return dest, oa, None
    if outcome == DOWNLOAD_SIZE_CAP:
        return None, oa, SKIP_SIZE_CAP
    return None, oa, SKIP_DOWNLOAD_FAILED


def _record(entry: dict, args) -> None:
    manifest_mod.add_entry(entry, args.manifest)


def load_processed_ids(args) -> set[str]:
    """PMCIDs already handled terminally (transient failures stay retryable).

    Reuses manifest.is_retryable so the terminal/transient semantics match the
    rest of the project. Cached once because ``is_processed`` re-reads the whole
    JSON per lookup, which is O(n^2) across thousands of candidates.
    """
    return {e["pmcid"] for e in manifest_mod.load_manifest(args.manifest)
            if e.get("pmcid") and not manifest_mod.is_retryable(e)}


def count_downloaded(args, category: str, subset: str | None = None) -> int:
    """How many PDFs of this category/subset a previous run already fetched.

    Targets are ABSOLUTE, not per-run: resuming a partially-complete build must
    top the set up to the target, never fetch a fresh full quota on top of it.
    """
    total = 0
    for e in manifest_mod.load_manifest(args.manifest):
        if e.get("status") != "ok" or e.get("category") != category:
            continue
        if subset is not None and e.get("subset") != subset:
            continue
        total += 1
    return total


def collect_fraud_cases(args, session, limiter, stats) -> list[dict]:
    """Steps (a)-(c): RW -> DOIs -> PMCIDs -> PDFs -> label entries."""
    df = rw.load_retraction_watch(args.rw_repo)
    stats["rw_total_records"] = len(df)
    image_df = rw.filter_image_related(df)
    stats["rw_image_related"] = len(image_df)

    # Exclusion set for the clean stage — ALL retractions, not just image ones.
    stats["_retracted_dois"] = rw.retracted_doi_set(df)

    already = count_downloaded(args, "fraud")
    needed = max(0, args.fraud_target - already)
    stats["fraud_preexisting"] = already
    if needed == 0:
        logger.info("fraud target already met (%d PDFs) - nothing to fetch", already)
        stats["fraud_downloaded"] = 0
        return []
    logger.info("fraud: %d already downloaded, need %d more", already, needed)

    # Resolve newest-first until we have enough PMCID candidates.
    candidates = image_df.head(args.max_doi_resolve)
    dois = [rw.normalize_doi(d) for d in candidates["OriginalPaperDOI"]]
    doi_to_pmcid = resolve_dois_to_pmcids(
        dois, batch_size=args.batch_size, session=session, rate_limiter=limiter)
    stats["dois_attempted"] = len(dois)
    stats["dois_resolved"] = sum(1 for v in doi_to_pmcid.values() if v)
    stats["dois_unresolved"] = stats["dois_attempted"] - stats["dois_resolved"]

    # Row lookup so we can attach title + verbatim reason to each label.
    by_doi = {}
    for _, row in candidates.iterrows():
        by_doi.setdefault(rw.normalize_doi(row["OriginalPaperDOI"]), row)

    fraud_dir = os.path.join(args.output_dir, "fraud_cases")
    os.makedirs(fraud_dir, exist_ok=True)
    entries: list[dict] = []

    processed = load_processed_ids(args)
    progress = tqdm(total=needed, unit="pdf", desc="fraud PDFs",
                    dynamic_ncols=True)
    try:
        for doi, pmcid in doi_to_pmcid.items():
            if len(entries) >= needed:
                break
            if not pmcid:
                continue
            if pmcid in processed:
                continue
            processed.add(pmcid)

            row = by_doi.get(doi)
            reason = str(row["Reason"]) if row is not None else ""
            title = str(row["Title"]) if row is not None else ""

            try:
                pdf, oa, skip = _fetch_pdf(pmcid, fraud_dir, args, session, limiter)
            except Exception as exc:  # noqa: BLE001 - never abort the batch
                logger.warning("%s: unexpected error: %s", pmcid, exc)
                _record({"pmcid": pmcid, "doi": doi, "category": "fraud",
                         "status": "error", "retryable": True,
                         "reason": SKIP_ERROR, "error": str(exc),
                         "timestamp": _now()}, args)
                stats["fraud_skips"][SKIP_ERROR] += 1
                continue

            if not pdf:
                terminal = skip != SKIP_DOWNLOAD_FAILED
                _record({"pmcid": pmcid, "doi": doi, "category": "fraud",
                         "status": "skipped" if terminal else "download_failed",
                         "retryable": not terminal, "reason": skip,
                         "license": oa.get("license"), "timestamp": _now()}, args)
                stats["fraud_skips"][skip] += 1
                continue

            entry = labels_builder.build_labels_entry(
                pmcid=pmcid, doi=doi, title=title, category="fraud",
                fraud_type=rw.reason_to_fraud_type(reason),
                label_confidence="confirmed",  # formal retraction
                pdf_path=os.path.relpath(pdf).replace("\\", "/"),
                retraction_reason=reason)
            entries.append(entry)
            _record({"pmcid": pmcid, "doi": doi, "category": "fraud",
                     "status": "ok", "reason": None, "pdf_path": entry["pdf_path"],
                     "license": oa.get("license"), "retracted": oa.get("retracted"),
                     "label_confidence": "confirmed", "title": title,
                     "retraction_reason": reason, "timestamp": _now()}, args)
            progress.update(1)
    finally:
        progress.close()

    stats["fraud_downloaded"] = len(entries)
    return entries


def collect_clean_controls(args, session, limiter, stats) -> list[dict]:
    """Steps (d)-(e): search, exclude every retracted DOI, download PDFs."""
    retracted = stats["_retracted_dois"]
    clean_dir = os.path.join(args.output_dir, "clean_control_papers")
    os.makedirs(clean_dir, exist_ok=True)

    dose_target = min(args.dose_response_count, args.clean_target)
    generic_target = args.clean_target - dose_target
    plan = [("dose_response", DOSE_RESPONSE_TERMS, dose_target),
            ("generic", GENERIC_TERMS, generic_target)]

    entries: list[dict] = []
    processed = load_processed_ids(args)
    # Absolute targets: top up what earlier runs already fetched.
    remaining = {s: max(0, t - count_downloaded(args, "clean", s))
                 for s, _terms, t in plan}
    for subset, _terms, target in plan:
        stats[f"clean_{subset}"] = count_downloaded(args, "clean", subset)

    progress = tqdm(total=sum(remaining.values()), unit="pdf", desc="clean PDFs",
                    dynamic_ncols=True)
    try:
        for subset, terms, target in plan:
            got = 0
            target = remaining[subset]
            if target <= 0:
                logger.info("clean/%s target already met - skipping", subset)
                continue
            # Gather candidate PMCIDs across this subset's terms.
            pmcids: list[str] = []
            for term in terms:
                pmcids.extend(search_pmc(term, retmax=args.retmax_per_term,
                                         session=session, rate_limiter=limiter))
            pmcids = list(dict.fromkeys(pmcids))

            # Resolve to DOIs so we can screen against Retraction Watch BEFORE
            # downloading anything.
            pmcid_to_doi = resolve_pmcids_to_dois(
                pmcids, batch_size=args.batch_size,
                session=session, rate_limiter=limiter)

            for pmcid in pmcids:
                if got >= target:
                    break
                if pmcid in processed:
                    continue
                processed.add(pmcid)

                doi = rw.normalize_doi(pmcid_to_doi.get(pmcid) or "")
                if doi and doi in retracted:
                    logger.info("%s (%s) is retracted - excluded from clean set",
                                pmcid, doi)
                    _record({"pmcid": pmcid, "doi": doi, "category": "clean",
                             "status": "skipped", "reason": SKIP_IN_RW,
                             "timestamp": _now()}, args)
                    stats["clean_skips"][SKIP_IN_RW] += 1
                    continue

                try:
                    pdf, oa, skip = _fetch_pdf(pmcid, clean_dir, args,
                                               session, limiter)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("%s: unexpected error: %s", pmcid, exc)
                    _record({"pmcid": pmcid, "doi": doi, "category": "clean",
                             "status": "error", "retryable": True,
                             "reason": SKIP_ERROR, "timestamp": _now()}, args)
                    stats["clean_skips"][SKIP_ERROR] += 1
                    continue

                # Belt and braces: the OA record itself must not say retracted.
                if oa.get("retracted"):
                    _record({"pmcid": pmcid, "doi": doi, "category": "clean",
                             "status": "skipped", "reason": SKIP_RETRACTED,
                             "timestamp": _now()}, args)
                    stats["clean_skips"][SKIP_RETRACTED] += 1
                    if pdf and os.path.isfile(pdf):
                        os.remove(pdf)
                    continue

                if not pdf:
                    terminal = skip != SKIP_DOWNLOAD_FAILED
                    _record({"pmcid": pmcid, "doi": doi, "category": "clean",
                             "status": "skipped" if terminal else "download_failed",
                             "retryable": not terminal, "reason": skip,
                             "timestamp": _now()}, args)
                    stats["clean_skips"][skip] += 1
                    continue

                entry = labels_builder.build_labels_entry(
                    pmcid=pmcid, doi=doi, title="", category="clean",
                    label_confidence="confirmed",
                    pdf_path=os.path.relpath(pdf).replace("\\", "/"),
                    subset=subset)
                entries.append(entry)
                _record({"pmcid": pmcid, "doi": doi, "category": "clean",
                         "subset": subset, "status": "ok", "reason": None,
                         "pdf_path": entry["pdf_path"],
                         "license": oa.get("license"), "retracted": False,
                         "timestamp": _now()}, args)
                got += 1
                progress.update(1)
            stats[f"clean_{subset}"] += got
    finally:
        progress.close()

    stats["clean_downloaded"] = len(entries)
    return entries


def labels_from_manifest(args) -> list[dict]:
    """Rebuild every label entry from the manifest (the source of truth).

    Building labels only from the current run's downloads would silently drop
    papers fetched by an earlier, resumed run — the manifest holds them all.
    Only records that actually produced a PDF on disk are included.
    """
    entries: list[dict] = []
    for rec in manifest_mod.load_manifest(args.manifest):
        if rec.get("status") != "ok":
            continue
        pdf_path = rec.get("pdf_path") or ""
        if not os.path.isfile(pdf_path):
            logger.warning("%s: manifest says ok but PDF is missing (%s) - "
                           "excluding from labels", rec.get("pmcid"), pdf_path)
            continue
        category = rec.get("category")
        entries.append(labels_builder.build_labels_entry(
            pmcid=rec["pmcid"], doi=rec.get("doi", ""),
            title=rec.get("title", ""), category=category,
            fraud_type=(rw.reason_to_fraud_type(rec.get("retraction_reason", ""))
                        if category == "fraud" else None),
            label_confidence=rec.get("label_confidence", "confirmed"),
            pdf_path=pdf_path,
            retraction_reason=rec.get("retraction_reason"),
            subset=rec.get("subset")))
    return entries


def run(args) -> dict:
    get_contact_email()  # fail fast, clear message
    os.makedirs(args.output_dir, exist_ok=True)
    session = requests.Session()
    limiter = RateLimiter()
    logger.info("rate limit: %.0f req/s%s", limiter.requests_per_second,
                " (NCBI_API_KEY detected)" if os.environ.get("NCBI_API_KEY") else "")

    stats = {"fraud_skips": collections.Counter(),
             "clean_skips": collections.Counter(),
             "clean_dose_response": 0, "clean_generic": 0}

    collect_fraud_cases(args, session, limiter, stats)
    collect_clean_controls(args, session, limiter, stats)

    # Assemble labels from the manifest so a resumed run still emits a complete
    # labels.json covering papers downloaded in earlier runs.
    all_entries = labels_from_manifest(args)
    labels_path = os.path.join(args.output_dir, "labels.json")
    labels_builder.write_labels_json(all_entries, labels_path)
    stats["labels_path"] = labels_path
    stats["labels_entries"] = len(all_entries)
    stats["labels_fraud"] = sum(1 for e in all_entries if e["is_fraudulent"])
    stats["labels_clean"] = len(all_entries) - stats["labels_fraud"]
    stats.pop("_retracted_dois", None)
    return stats


def _print_summary(s: dict) -> None:
    print("\n" + "=" * 66)
    print("  ScholarGuard evaluation-set build - summary")
    print("=" * 66)
    print(f"  Retraction Watch records total : {s.get('rw_total_records', 0)}")
    print(f"  ... image-related (formal)     : {s.get('rw_image_related', 0)}")
    print(f"  DOIs attempted -> PMCID        : {s.get('dois_attempted', 0)}")
    print(f"  ... resolved to a PMCID        : {s.get('dois_resolved', 0)}")
    print(f"  ... failed to resolve          : {s.get('dois_unresolved', 0)}")
    print(f"  FRAUD PDFs this run            : {s.get('fraud_downloaded', 0)}"
          f"  (+{s.get('fraud_preexisting', 0)} from earlier runs)")
    if s["fraud_skips"]:
        for reason, n in s["fraud_skips"].most_common(5):
            print(f"      skipped - {reason}: {n}")
    print(f"  CLEAN PDFs this run            : {s.get('clean_downloaded', 0)}")
    print(f"  CLEAN totals  generic          : {s.get('clean_generic', 0)}")
    print(f"                dose-response    : {s.get('clean_dose_response', 0)}"
          f"   (known false-positive trap)")
    if s["clean_skips"]:
        for reason, n in s["clean_skips"].most_common():
            print(f"      skipped - {reason}: {n}")
    print(f"  labels.json entries            : {s.get('labels_entries', 0)}"
          f"  (fraud {s.get('labels_fraud', 0)}, clean {s.get('labels_clean', 0)})")
    print(f"  labels.json path               : {s.get('labels_path')}")
    print("=" * 66)
    print("  NOTE: labels are PAPER-LEVEL. figure_num is null for every fraud")
    print("  case - Retraction Watch does not say which figure was manipulated.")
    print("=" * 66)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build the real evaluation set")
    p.add_argument("--fraud-target", type=int, default=40)
    p.add_argument("--clean-target", type=int, default=25)
    p.add_argument("--dose-response-count", type=int, default=10,
                   help="subset of --clean-target sourced from dose-response terms")
    p.add_argument("--output-dir", default="data/evaluation_set")
    p.add_argument("--manifest", default="data/evaluation_manifest.json")
    p.add_argument("--rw-repo", default="retraction-watch-data")
    p.add_argument("--max-package-mb", type=int, default=50)
    p.add_argument("--max-doi-resolve", type=int, default=2000,
                   help="how many image-related DOIs to try resolving (newest first)")
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--retmax-per-term", type=int, default=100)
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log = logging.getLogger("scholarguard.data")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)

    try:
        stats = run(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    _print_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

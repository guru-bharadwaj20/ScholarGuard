#!/usr/bin/env python
"""Annotate WHICH figures a retraction notice names, unlocking recall.

The problem this solves
-----------------------
Every fraud label in this project is paper-level: Retraction Watch says a paper
was retracted for "Duplication of/in Image", never which figure was duplicated.
So the evaluation can measure each detector's false-alarm rate on clean figures
and nothing else — ``metrics_summary.md`` reports recall as *not measurable* and
excludes every fraud-paper figure as UNKNOWN. Detector changes cannot be
steered: a change that makes a detector quieter and a change that makes it
smarter look identical.

The retraction *notice*, however, is a separate article that frequently does say
"Figure 3B was duplicated". This script finds those notices and extracts the
figure numbers, turning paper-level labels into figure-level ones.

Why not read the packages we already have: the OA package is the article *as
published*, so it predates its own retraction — only 1 of 30 fraud packages
contains a ``<related-article>`` link to the notice. The notices are reachable
through PubMed instead, whose record for a retracted article carries a
``CommentsCorrections RefType="RetractionIn"`` pointer to the notice's PMID.

Pipeline: PMCID -> PMID -> notice PMID -> notice text (PMC full text if it is
open access, else the PubMed abstract) -> figure numbers.

The figure numbers line up with the pipeline's own ``figure_num``, which
``src/nlp/pmc_package.py`` parses from each figure's JATS ``<label>`` — so
"Figure 3" in a notice and figure_num 3 in a report are the same figure by
construction, not by ordinal guesswork.

**Coverage is partial and that is expected**: many notices are a bare "Retracted:
<title>" with no detail. Papers whose notice names no figure are left exactly as
they were — paper-level only — so they keep being excluded from figure metrics
rather than being silently treated as all-clean.

Example:
    export NCBI_CONTACT_EMAIL=you@institution.edu
    python scripts/annotate_fraud_figures.py \
        --labels data/heldout_packages/labels.json --dry-run
    python scripts/annotate_fraud_figures.py \
        --labels data/heldout_packages/labels.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests  # noqa: E402

from src.data_acquisition import retraction_watch as rw  # noqa: E402
from src.data_acquisition.doi_resolver import _idconv_batch  # noqa: E402
from src.data_acquisition.pmc_search import (  # noqa: E402
    EUTILS_BASE,
    get_contact_email,
    ncbi_common_params,
)
from src.data_acquisition.rate_limiter import RateLimiter  # noqa: E402

logger = logging.getLogger("scholarguard.annotate")

#: "Figure 3", "Fig. 3", "Figures 2 and 4", "Figs 1-3", "Figure 5B".
#: The panel letter carries a negative lookahead so it cannot swallow the first
#: letter of a following word — without it, "Figures 2 and 4" parses as
#: "2 a" and the 4 is lost.
_PANEL = r"\d{1,2}(?:\s?[A-Za-z](?![A-Za-z]))?"
_FIG_RE = re.compile(
    r"\b(?:fig(?:ure)?s?\.?)\s*"
    rf"((?:{_PANEL})(?:\s*(?:,|and|&|to|through|[-–—])\s*(?:{_PANEL}))*)",
    re.IGNORECASE)
_RANGE_RE = re.compile(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})")
#: A figure number above this is far likelier to be a typo or a year fragment.
_MAX_FIGURE = 30


def parse_figure_numbers(text: str) -> tuple[set[int], list[str]]:
    """Figure numbers mentioned in ``text``, plus the wording they came from.

    Ranges ("Figures 1-3") expand; letter panels ("Figure 5B") collapse to the
    figure. A text window around each match is returned so every annotation can
    be audited against the notice's own wording instead of taken on trust.

    Matching runs over the whole text rather than sentence by sentence: a
    sentence splitter breaks "Fig. 7" in half at the abbreviating period and
    loses the number entirely.
    """
    found: set[int] = set()
    evidence: list[str] = []
    for match in _FIG_RE.finditer(text):
        body = match.group(1)
        hits: set[int] = set()
        for lo, hi in _RANGE_RE.findall(body):
            if int(lo) <= int(hi) and int(hi) - int(lo) <= 20:
                hits.update(range(int(lo), int(hi) + 1))
        hits.update(int(n) for n in re.findall(r"\d{1,2}", body))
        hits = {n for n in hits if 1 <= n <= _MAX_FIGURE}
        if not hits:
            continue
        found |= hits
        lo = max(0, match.start() - 120)
        evidence.append(" ".join(text[lo:match.end() + 120].split()))
    return found, evidence


def _get(url: str, params: dict, session, limiter) -> str | None:
    limiter.acquire()
    try:
        r = session.get(url, params=params, timeout=60)
        r.raise_for_status()
        return r.text
    except requests.RequestException as exc:
        logger.warning("request failed (%s): %s", url, exc)
        return None


def pmcids_to_pmids(pmcids: list[str], session, limiter) -> dict[str, str]:
    """Map PMCID -> PMID via the same idconv service the project already uses."""
    out: dict[str, str] = {}
    for i in range(0, len(pmcids), 200):
        limiter.acquire()
        for rec in _idconv_batch(pmcids[i:i + 200], session, limiter):
            if rec.get("pmcid") and rec.get("pmid"):
                out[rec["pmcid"].upper()] = str(rec["pmid"])
    return out


def find_retraction_notices(pmids: list[str], session, limiter) -> dict[str, str]:
    """Map article PMID -> its retraction notice's PMID.

    PubMed records the link on the *retracted* article as a CommentsCorrections
    entry of type RetractionIn, which is exactly the pointer we need.
    """
    out: dict[str, str] = {}
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        xml = _get(f"{EUTILS_BASE}/efetch.fcgi",
                   {**ncbi_common_params(), "db": "pubmed",
                    "id": ",".join(chunk), "retmode": "xml"}, session, limiter)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            logger.warning("could not parse PubMed XML: %s", exc)
            continue
        for art in root.iter("PubmedArticle"):
            pmid_el = art.find(".//MedlineCitation/PMID")
            if pmid_el is None:
                continue
            for cc in art.iter("CommentsCorrections"):
                if cc.get("RefType") == "RetractionIn":
                    ref = cc.find("PMID")
                    if ref is not None and ref.text:
                        out[pmid_el.text] = ref.text.strip()
                        break
    return out


def _pmc_fulltext(pmid: str, session, limiter) -> str:
    """Notice full text from PMC when it is open access ('' if unavailable)."""
    recs = _idconv_batch([pmid], session, limiter)
    pmcid = next((r.get("pmcid") for r in recs if r.get("pmcid")), None)
    if not pmcid:
        return ""
    xml = _get(f"{EUTILS_BASE}/efetch.fcgi",
               {**ncbi_common_params(), "db": "pmc", "id": pmcid,
                "retmode": "xml"}, session, limiter)
    if not xml:
        return ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    return " ".join(t.strip() for t in root.itertext() if t and t.strip())


def notice_text(pmid: str, session, limiter) -> tuple[str, str]:
    """(text, source) for a notice — PMC full text preferred, else abstract."""
    full = _pmc_fulltext(pmid, session, limiter)
    if len(full) > 400:
        return full, "pmc_fulltext"
    xml = _get(f"{EUTILS_BASE}/efetch.fcgi",
               {**ncbi_common_params(), "db": "pubmed", "id": pmid,
                "retmode": "xml"}, session, limiter)
    if not xml:
        return full, "pmc_fulltext" if full else "none"
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return full, "none"
    parts = []
    for tag in (".//ArticleTitle", ".//AbstractText"):
        parts += [ "".join(el.itertext()) for el in root.iterfind(tag)]
    abstract = " ".join(p.strip() for p in parts if p)
    if len(abstract) > len(full):
        return abstract, "pubmed_abstract"
    return full, "pmc_fulltext" if full else "none"


def run(args) -> int:
    get_contact_email()
    session, limiter = requests.Session(), RateLimiter()

    with open(args.labels, encoding="utf-8") as fh:
        data = json.load(fh)
    papers = data["papers"] if isinstance(data, dict) else data
    fraud = [p for p in papers if p.get("is_fraudulent")]
    logger.info("%d fraud paper(s) to annotate", len(fraud))

    pmid_by_pmcid = pmcids_to_pmids([p["paper_id"] for p in fraud],
                                    session, limiter)
    logger.info("resolved %d/%d PMCID -> PMID", len(pmid_by_pmcid), len(fraud))

    notices = find_retraction_notices(sorted(set(pmid_by_pmcid.values())),
                                      session, limiter)
    logger.info("found a retraction notice for %d/%d", len(notices),
                len(pmid_by_pmcid))

    annotated, no_notice, no_figures = 0, 0, 0
    audit = []
    for paper in fraud:
        pmid = pmid_by_pmcid.get(paper["paper_id"].upper())
        notice_pmid = notices.get(pmid) if pmid else None
        if not notice_pmid:
            no_notice += 1
            continue
        text, source = notice_text(notice_pmid, session, limiter)
        figures, evidence = parse_figure_numbers(text)
        if not figures:
            no_figures += 1
            logger.info("%s: notice %s names no figure (%s, %d chars)",
                        paper["paper_id"], notice_pmid, source, len(text))
            continue

        ftype = rw.reason_to_fraud_type(paper.get("retraction_reason", "") or "")
        paper["figures"] = [{
            "figure_num": n,
            "fraud_type": ftype,
            "label_confidence": "confirmed",
            "note": (f"named in retraction notice PMID {notice_pmid} "
                     f"({source})"),
        } for n in sorted(figures)]
        paper["retraction_notice_pmid"] = notice_pmid
        annotated += 1
        audit.append({"paper_id": paper["paper_id"], "notice_pmid": notice_pmid,
                      "source": source, "figures": sorted(figures),
                      "evidence": evidence[:4]})
        logger.info("%s: figures %s (notice %s)", paper["paper_id"],
                    sorted(figures), notice_pmid)

    print(f"\nAnnotated {annotated}/{len(fraud)} fraud papers with figure-level "
          f"labels")
    print(f"  no retraction notice found : {no_notice}")
    print(f"  notice named no figure     : {no_figures}")
    print(f"  figures marked manipulated : {sum(len(a['figures']) for a in audit)}")

    if args.dry_run:
        print("\n--dry-run: nothing written. Evidence sentences:")
        for a in audit[:10]:
            print(f"  {a['paper_id']} -> {a['figures']}")
            for e in a["evidence"][:2]:
                print(f"      \"{e[:160]}\"")
        return 0

    shutil.copyfile(args.labels, args.labels + ".prelabel.bak")
    with open(args.labels, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    audit_path = os.path.join(os.path.dirname(args.labels),
                              "figure_annotations_audit.json")
    with open(audit_path, "w", encoding="utf-8") as fh:
        json.dump({"n_annotated": annotated, "n_no_notice": no_notice,
                   "n_notice_without_figures": no_figures,
                   "annotations": audit}, fh, indent=2)
    print(f"\nWrote {args.labels} (backup: {args.labels}.prelabel.bak)")
    print(f"Audit  {audit_path}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--labels", default="data/heldout_packages/labels.json")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would be annotated, with the notice "
                        "sentences each figure number came from")
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

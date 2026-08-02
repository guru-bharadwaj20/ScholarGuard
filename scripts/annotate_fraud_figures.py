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
import collections
import itertools
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

#: The "Figure"/"Fig."/"Figs" prefix that a number list may follow.
_PREFIX_RE = re.compile(r"\bfig(?:ure)?s?\b\.?", re.IGNORECASE)
#: One item of a following list: optional separator, optional range dash, a
#: number, and an optional panel letter. The letter's negative lookahead stops
#: it swallowing the first letter of a following word — without it "Figures 2
#: and 4" reads as "2 a" and the 4 is lost. Separators stack (", and ") because
#: "Figs 3, 4, and 5" is the single most common phrasing in these notices.
_ITEM_RE = re.compile(
    r"\s*(?:(?:,|;|and|&|to|through)\s*)*(?:(?P<dash>[-–—])\s*)?"
    r"(?P<num>\d{1,2})(?:\s?[A-Za-z](?![A-Za-z]))?",
    re.IGNORECASE)
#: A reference is skipped when this appears just before it: supplementary
#: figures are numbered separately and are NOT the paper's Figure N.
_SUPPLEMENT_RE = re.compile(
    r"(?:supp(?:l(?:ement(?:al|ary)?)?)?\.?|extended\s+data|online)\s*$",
    re.IGNORECASE)
#: A figure number above this is far likelier to be a typo or a year fragment.
_MAX_FIGURE = 30
#: Longest list accepted after one prefix, so a match cannot run away down a
#: sentence of unrelated numbers.
_MAX_ITEMS = 12
#: A figure reference only counts as an ACCUSATION if one of these appears near
#: it. Notices mention figures for innocent reasons too, and the difference is
#: not visible to a pattern match — one real notice says "the authors have
#: provided individual level data underlying the graphs and most blots presented
#: in Figs 1-5", which would otherwise mark every figure in the paper as
#: manipulated on the strength of the authors' *defence*.
_CUE_RE = re.compile(
    r"duplicat|manipulat|splic|overlap|irregular|alter|reus|falsif|fabricat|"
    r"doctor|identical|similar|concern|integrity|inappropriate|affect",
    re.IGNORECASE)
#: Sentence boundary used to scope the cue search. The uppercase/bullet
#: lookahead keeps "Fig. 7" and "Figs 1-5." intact, since a digit never starts a
#: new sentence here; a mis-split only narrows the window, which is the safe
#: direction — it can drop a true figure, never invent one.
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z•‐-―*-])")
#: Reuse ACROSS articles — the cross-figure detector's actual target. Phrases
#: like "Figure 4a published in [1] and Figure 2b in [2]" or "also appears in a
#: previously published article".
_CROSS_ARTICLE_RE = re.compile(
    # One optional word may sit between, as in "previously PUBLISHED article".
    r"(?:another|different|previous(?:ly)?|separate|other|earlier)\s+"
    r"(?:\w+\s+)?(?:article|paper|publication|study|manuscript)"
    r"|published\s+in\s*\[|in\s+the\s+(?:earlier|prior)\s+(?:article|paper)"
    r"|from\s+(?:a|an)\s+(?:different|other|unrelated)\s+(?:source|paper|article)",
    re.IGNORECASE)
#: Explicitly generated/synthetic imagery. Rare in these notices, kept narrow.
_AI_RE = re.compile(
    r"\b(?:ai[- ]generated|generative|synthetic image|computer[- ]generated)\b",
    re.IGNORECASE)
#: Duplication/manipulation confined to this paper's own figures.
_WITHIN_RE = re.compile(
    r"duplicat|overlap|splic|identical|manipulat|altered|reus", re.IGNORECASE)


def parse_figure_numbers(text: str) -> tuple[set[int], list[str]]:
    """Figure numbers mentioned in ``text``, plus the wording they came from.

    Ranges ("Figures 1-3") expand; letter panels ("Figure 5B") collapse to the
    figure. A text window around each match is returned so every annotation can
    be audited against the notice's own wording instead of taken on trust.

    Matching runs over the whole text rather than sentence by sentence: a
    sentence splitter breaks "Fig. 7" in half at the abbreviating period and
    loses the number entirely.
    """
    refs = parse_figure_references(text)
    evidence: list[str] = []
    for windows in refs.values():
        for w in windows:
            if w not in evidence:
                evidence.append(w)
    return set(refs), evidence


def parse_figure_references(text: str) -> dict[int, list[str]]:
    """Map each named figure number to the wording that named it.

    Same extraction as :func:`parse_figure_numbers`, but keeping the per-figure
    association so each figure can be typed by what the notice says *about it*
    rather than inheriting one label from the paper's retraction reason.
    """
    # Sentence spans, so a cue is only credited to the reference it sits with.
    bounds = [0] + [m.end() for m in _SENTENCE_SPLIT.finditer(text)] + [len(text)]
    spans = list(itertools.pairwise(bounds))

    def enclosing(index: int) -> str:
        for lo, hi in spans:
            if lo <= index < hi:
                return text[lo:hi]
        return text

    refs: dict[int, list[str]] = {}
    for prefix in _PREFIX_RE.finditer(text):
        if _SUPPLEMENT_RE.search(text[max(0, prefix.start() - 24):prefix.start()]):
            continue  # "Supplementary Figure 1" is not this paper's Figure 1
        hits: set[int] = set()
        pos, previous = prefix.end(), None
        for _ in range(_MAX_ITEMS):
            item = _ITEM_RE.match(text, pos)
            if not item:
                break
            num = int(item.group("num"))
            if not 1 <= num <= _MAX_FIGURE:
                break
            if item.group("dash") and previous is not None and previous < num:
                hits.update(range(previous, num + 1))   # "Figs 1-3"
            hits.add(num)
            previous, pos = num, item.end()
        if not hits:
            continue
        sentence = enclosing(prefix.start())
        if not _CUE_RE.search(sentence):
            continue
        lo = max(0, prefix.start() - 120)
        window = " ".join(text[lo:pos + 80].split())
        for num in hits:
            refs.setdefault(num, []).append(window)
    return refs


def classify_manipulation(windows: list[str], default: str) -> str:
    """Fraud type for one figure, from what the notice says *about that figure*.

    Until now every annotated figure inherited a single ``fraud_type`` from its
    paper's Retraction Watch reason, so no figure was ever typed
    ``cross_figure`` and that detector's recall stayed unmeasurable no matter
    how many papers were annotated. The notice usually distinguishes the modes
    in plain language — reuse *across articles* reads very differently from
    duplication within one figure — so the type is taken per figure here, with
    the paper-level reason as the fallback.
    """
    blob = " ".join(windows)
    if _CROSS_ARTICLE_RE.search(blob):
        return "cross_figure"
    if _AI_RE.search(blob):
        return "ai_generated"
    if _WITHIN_RE.search(blob):
        return "copy_move"
    return default


def _get(url: str, params: dict, session, limiter) -> str | None:
    limiter.wait()
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
        # _idconv_batch rate-limits itself; do not double-throttle here.
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
    types = collections.Counter()
    audit = []
    for paper in fraud:
        pmid = pmid_by_pmcid.get(paper["paper_id"].upper())
        notice_pmid = notices.get(pmid) if pmid else None
        if not notice_pmid:
            no_notice += 1
            continue
        text, source = notice_text(notice_pmid, session, limiter)
        refs = parse_figure_references(text)
        figures, evidence = parse_figure_numbers(text)
        if not figures:
            no_figures += 1
            logger.info("%s: notice %s names no figure (%s, %d chars)",
                        paper["paper_id"], notice_pmid, source, len(text))
            continue

        default_type = rw.reason_to_fraud_type(
            paper.get("retraction_reason", "") or "")
        typed = {n: classify_manipulation(refs.get(n, []), default_type)
                 for n in sorted(figures)}
        paper["figures"] = [{
            "figure_num": n,
            "fraud_type": typed[n],
            "label_confidence": "confirmed",
            "note": (f"named in retraction notice PMID {notice_pmid} "
                     f"({source}); type inferred from the notice wording"),
        } for n in sorted(figures)]
        paper["retraction_notice_pmid"] = notice_pmid
        annotated += 1
        for t in typed.values():
            types[t] += 1
        audit.append({"paper_id": paper["paper_id"], "notice_pmid": notice_pmid,
                      "source": source, "figures": sorted(figures),
                      "fraud_types": typed, "evidence": evidence[:4]})
        logger.info("%s: figures %s (notice %s)", paper["paper_id"],
                    [f"{n}:{typed[n]}" for n in sorted(figures)], notice_pmid)

    print(f"\nAnnotated {annotated}/{len(fraud)} fraud papers with figure-level "
          f"labels")
    print(f"  no retraction notice found : {no_notice}")
    print(f"  notice named no figure     : {no_figures}")
    print(f"  figures marked manipulated : {sum(len(a['figures']) for a in audit)}")
    print(f"  by inferred type           : {dict(types)}")

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
                   "figures_by_inferred_type": dict(types),
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

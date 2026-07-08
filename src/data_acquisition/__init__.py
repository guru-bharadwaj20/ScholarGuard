"""PubMed Central Open Access corpus acquisition (clean, non-retracted figures).

Modules:
* :mod:`rate_limiter`    — NCBI-compliant request pacing (3/s, or 10/s with a key).
* :mod:`pmc_search`      — esearch wrapper -> PMCID list.
* :mod:`pmc_oa_fetch`    — oa.fcgi resolve + streaming package download.
* :mod:`figure_extractor`— extract + dimension-filter images from a package.
* :mod:`manifest`        — resumable, atomic processing/attribution record.

This package builds the CLEAN corpus only; retracted papers are skipped.
"""

"""Tests for the evaluation-set acquisition (Retraction Watch x PMC OA).

All network calls and git clones are mocked — nothing here touches the real
Retraction Watch repo, idconv, or PMC.
"""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data_acquisition import labels_builder, retraction_watch as rw
from src.data_acquisition.doi_resolver import resolve_dois_to_pmcids
from src.data_acquisition.rate_limiter import RateLimiter


@pytest.fixture
def fast_limiter():
    return RateLimiter(requests_per_second=1000)


@pytest.fixture(autouse=True)
def _contact_email(monkeypatch):
    monkeypatch.setenv("NCBI_CONTACT_EMAIL", "test@example.org")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)


def _mock_rw_df():
    """A small stand-in for the real CSV, using the VERIFIED reason strings."""
    return pd.DataFrame([
        # image-related, formal retraction -> kept
        {"Title": "Blot paper", "Reason": "+Duplication of/in Image;+Paper Mill",
         "RetractionNature": "Retraction", "OriginalPaperDOI": "10.1/dup",
         "RetractionDOI": "10.1/dup-r", "OriginalPaperDate": "2021-01-01"},
        {"Title": "Manip paper", "Reason": "+Manipulation of Images",
         "RetractionNature": "Retraction", "OriginalPaperDOI": "10.1/manip",
         "RetractionDOI": "10.1/manip-r", "OriginalPaperDate": "2022-01-01"},
        {"Title": "Fab paper", "Reason": "+Falsification/Fabrication of Image",
         "RetractionNature": "Retraction", "OriginalPaperDOI": "10.1/fab",
         "RetractionDOI": "10.1/fab-r", "OriginalPaperDate": "2023-01-01"},
        # image-related but NOT a formal retraction -> dropped
        {"Title": "EoC paper", "Reason": "+Duplication of/in Image",
         "RetractionNature": "Expression of concern", "OriginalPaperDOI": "10.1/eoc",
         "RetractionDOI": "10.1/eoc-r", "OriginalPaperDate": "2020-01-01"},
        # not image-related -> dropped from fraud set, but still "retracted"
        {"Title": "Peer review", "Reason": "+Compromised Peer Review",
         "RetractionNature": "Retraction", "OriginalPaperDOI": "10.1/peer",
         "RetractionDOI": "10.1/peer-r", "OriginalPaperDate": "2019-01-01"},
        # weak image signal we deliberately exclude
        {"Title": "Concerns", "Reason": "+Concerns/Issues about Image",
         "RetractionNature": "Retraction", "OriginalPaperDOI": "10.1/concern",
         "RetractionDOI": "10.1/concern-r", "OriginalPaperDate": "2018-01-01"},
    ])


# ---------------------------------------------------------------- test 1
def test_filter_image_related_identifies_image_fraud_rows():
    out = rw.filter_image_related(_mock_rw_df())
    dois = set(out["OriginalPaperDOI"])
    assert dois == {"10.1/dup", "10.1/manip", "10.1/fab"}
    # Expression-of-concern and non-image reasons are excluded.
    assert "10.1/eoc" not in dois
    assert "10.1/peer" not in dois
    # "Concerns/Issues about Image" is not evidence of manipulation.
    assert "10.1/concern" not in dois
    # Newest first (helps PMC OA hit-rate).
    assert list(out["OriginalPaperDOI"])[0] == "10.1/fab"


def test_reason_mapping_never_claims_ai_generation():
    """Fabrication must not be mapped to ai_generated (see module rationale)."""
    for reason in rw.IMAGE_REASON_PATTERNS:
        ftype = rw.reason_to_fraud_type(reason)
        assert ftype in labels_builder.VALID_FRAUD_TYPES
        assert ftype != "ai_generated"


def test_retracted_doi_set_covers_all_retractions_not_just_image():
    """The clean-control exclusion list must include NON-image retractions."""
    dois = rw.retracted_doi_set(_mock_rw_df())
    assert "10.1/peer" in dois          # non-image retraction still excluded
    assert "10.1/eoc" in dois           # expression of concern still excluded
    assert "10.1/dup-r" in dois         # the notice DOI too


def test_normalize_doi_strips_prefixes():
    assert rw.normalize_doi("https://doi.org/10.1/ABC") == "10.1/abc"
    assert rw.normalize_doi("  DOI:10.1/x ") == "10.1/x"
    assert rw.normalize_doi(None) == ""


# ---------------------------------------------------------------- test 2
def test_resolve_dois_to_pmcids_parses_batch_and_errors(fast_limiter):
    body = {"status": "ok", "records": [
        {"doi": "10.1/found", "pmcid": "PMC111", "pmid": 1,
         "requested-id": "10.1/found"},
        {"doi": "10.1/missing", "requested-id": "10.1/missing",
         "status": "error", "errmsg": "Identifier not found in PMC"},
    ]}
    resp = MagicMock()
    resp.status_code = 200          # real responses carry an int; the resolver
    resp.raise_for_status.return_value = None   # branches on it to spot 4xx/5xx
    resp.json.return_value = body
    session = MagicMock()
    session.get.return_value = resp

    out = resolve_dois_to_pmcids(["10.1/found", "10.1/missing"],
                                 session=session, rate_limiter=fast_limiter)
    assert out == {"10.1/found": "PMC111", "10.1/missing": None}


def test_resolve_dois_batches_requests(fast_limiter):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": []}
    session = MagicMock()
    session.get.return_value = resp

    resolve_dois_to_pmcids([f"10.1/{i}" for i in range(5)], batch_size=2,
                           session=session, rate_limiter=fast_limiter)
    assert session.get.call_count == 3  # 2 + 2 + 1


def test_resolve_handles_network_failure(fast_limiter):
    import requests as rq
    session = MagicMock()
    session.get.side_effect = rq.RequestException("boom")
    out = resolve_dois_to_pmcids(["10.1/x"], session=session,
                                 rate_limiter=fast_limiter)
    assert out == {"10.1/x": None}  # degraded, not crashed


# ---------------------------------------------------------------- test 3
def test_build_labels_entry_matches_ground_truth_loader_schema(tmp_path):
    """The generated labels.json must load cleanly in Stage 7's loader."""
    from src.evaluation.ground_truth_loader import load_evaluation_set

    pdf = tmp_path / "PMC1.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    clean_pdf = tmp_path / "PMC2.pdf"
    clean_pdf.write_bytes(b"%PDF-1.4 y")

    fraud = labels_builder.build_labels_entry(
        pmcid="PMC1", doi="10.1/dup", title="Blot paper", category="fraud",
        fraud_type="copy_move", label_confidence="confirmed",
        pdf_path=str(pdf), retraction_reason="+Duplication of/in Image")
    clean = labels_builder.build_labels_entry(
        pmcid="PMC2", doi="10.1/ok", title="Clean paper", category="clean",
        pdf_path=str(clean_pdf), subset="dose_response")

    # Field-by-field against the loader's contract.
    assert fraud["paper_id"] == "PMC1" and fraud["is_fraudulent"] is True
    assert fraud["label_confidence"] in {"confirmed", "disputed"}
    assert len(fraud["figures"]) == 1
    fig = fraud["figures"][0]
    assert fig["figure_num"] is None          # never guessed
    assert fig["fraud_type"] in labels_builder.VALID_FRAUD_TYPES
    assert clean["is_fraudulent"] is False and clean["figures"] == []
    assert clean["subset"] == "dose_response"

    # And end-to-end: the real loader accepts the written file.
    labels_path = str(tmp_path / "labels.json")
    labels_builder.write_labels_json([fraud, clean], labels_path)
    loaded = load_evaluation_set(labels_path)
    assert len(loaded["papers"]) == 2
    assert loaded["warnings"] == []  # both PDFs exist
    by_id = {p["paper_id"]: p for p in loaded["papers"]}
    assert by_id["PMC1"]["is_fraudulent"] is True
    assert by_id["PMC1"]["figures"][0]["fraud_type"] == "copy_move"


def test_build_labels_entry_rejects_bad_inputs():
    with pytest.raises(ValueError):
        labels_builder.build_labels_entry("PMC1", "d", "t", category="bogus")
    with pytest.raises(ValueError):
        labels_builder.build_labels_entry("PMC1", "d", "t", category="fraud",
                                          fraud_type="not_a_type")
    with pytest.raises(ValueError):
        labels_builder.build_labels_entry("PMC1", "d", "t", category="fraud",
                                          label_confidence="maybe")


def test_source_field_recorded_and_validated():
    real = labels_builder.build_labels_entry("PMC1", "d", "t", "fraud",
                                             pdf_path="x.pdf")
    assert real["source"] == "real"  # default for downloaded entries
    syn = labels_builder.build_labels_entry("PMC2", "d", "t", "clean",
                                            pdf_path="y.pdf", source="synthetic")
    assert syn["source"] == "synthetic"
    with pytest.raises(ValueError):
        labels_builder.build_labels_entry("PMC3", "d", "t", "clean",
                                          source="made_up")


def test_overwrite_guard_blocks_without_force_allows_with_force(tmp_path, monkeypatch):
    """make_eval_set must never silently destroy real downloaded labels."""
    import src.evaluation.make_eval_set as mes

    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps({"papers": [
        {"paper_id": "PMC1", "source": "real", "is_fraudulent": True},
        {"paper_id": "PMC2", "source": "real", "is_fraudulent": False},
    ]}), encoding="utf-8")

    monkeypatch.setattr(mes, "LABELS_PATH", str(labels_path))
    monkeypatch.setattr(mes, "FRAUD_DIR", str(tmp_path / "fraud"))
    monkeypatch.setattr(mes, "CLEAN_DIR", str(tmp_path / "clean"))

    # Without --force: refuses, and generates NOTHING (guard runs first).
    with pytest.raises(labels_builder.RealDataOverwriteError, match="2 REAL"):
        mes.generate_evaluation_set(force=False)
    assert json.loads(labels_path.read_text())["papers"][0]["source"] == "real"
    assert not (tmp_path / "fraud").exists(), "no PDFs may be written when blocked"

    # The CLI surfaces it as exit code 2 with a clear message, not a traceback.
    assert mes.main([]) == 2


def test_overwrite_guard_force_replaces_and_marks_synthetic(tmp_path, monkeypatch):
    import src.evaluation.make_eval_set as mes

    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps({"papers": [
        {"paper_id": "PMC1", "source": "real", "is_fraudulent": True}]}),
        encoding="utf-8")
    monkeypatch.setattr(mes, "LABELS_PATH", str(labels_path))
    monkeypatch.setattr(mes, "FRAUD_DIR", str(tmp_path / "fraud"))
    monkeypatch.setattr(mes, "CLEAN_DIR", str(tmp_path / "clean"))

    labels = mes.generate_evaluation_set(seed=1, force=True)
    assert labels["papers"], "force must actually regenerate"
    assert all(p["source"] == "synthetic" for p in labels["papers"])
    on_disk = json.loads(labels_path.read_text())
    assert [p["paper_id"] for p in on_disk["papers"]] ==         [p["paper_id"] for p in labels["papers"]],         "the returned labels must match what was written to disk"
    assert labels_builder.count_real_entries(str(labels_path)) == 0


def test_guard_ignores_labels_without_source_field(tmp_path):
    """A pre-`source` labels.json (all synthetic) must not block generation."""
    p = tmp_path / "labels.json"
    p.write_text(json.dumps({"papers": [{"paper_id": "x"}]}), encoding="utf-8")
    assert labels_builder.count_real_entries(str(p)) == 0
    labels_builder.assert_safe_to_overwrite(str(p))  # does not raise


def test_write_labels_json_is_atomic_and_annotated(tmp_path):
    path = str(tmp_path / "labels.json")
    e = labels_builder.build_labels_entry("PMC1", "10.1/a", "t", "fraud",
                                          pdf_path="x.pdf")
    labels_builder.write_labels_json([e], path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["n_fraud"] == 1 and data["n_clean"] == 0
    # The paper-level-only caveat must be recorded in the file itself.
    assert "PAPER-LEVEL" in data["note"]
    assert not list(tmp_path.glob("*.tmp"))  # temp file cleaned up


# ---------------------------------------------------------------- test 4
def test_clean_path_excludes_retracted_pmcid(tmp_path, monkeypatch, fast_limiter):
    """A search hit whose DOI is in Retraction Watch must never be accepted."""
    import scripts.fetch_evaluation_set as fes

    retracted = {"10.1/peer"}  # a NON-image retraction: still must be excluded
    stats = {"clean_skips": __import__("collections").Counter(),
             "_retracted_dois": retracted}

    # PMC9 is retracted; PMC8 is clean.
    monkeypatch.setattr(fes, "search_pmc", lambda *a, **k: ["PMC9", "PMC8"])
    monkeypatch.setattr(fes, "resolve_pmcids_to_dois",
                        lambda ids, **k: {"PMC9": "10.1/peer", "PMC8": "10.1/ok"})

    fetched = []

    def fake_fetch(pmcid, dest_dir, args, session, limiter):
        fetched.append(pmcid)
        p = tmp_path / f"{pmcid}.pdf"
        p.write_bytes(b"%PDF")
        return str(p), {"license": "CC BY", "retracted": False}, None

    monkeypatch.setattr(fes, "_fetch_pdf", fake_fetch)
    monkeypatch.setattr(fes, "_record", lambda entry, args: None)

    args = fes.build_arg_parser().parse_args([
        "--clean-target", "1", "--dose-response-count", "1",
        "--output-dir", str(tmp_path), "--manifest", str(tmp_path / "m.json")])

    entries = fes.collect_clean_controls(args, MagicMock(), fast_limiter, stats)

    # The retracted paper was never even downloaded.
    assert "PMC9" not in fetched
    assert [e["paper_id"] for e in entries] == ["PMC8"]
    assert stats["clean_skips"][fes.SKIP_IN_RW] == 1


def test_clean_path_excludes_paper_flagged_retracted_by_oa(tmp_path, monkeypatch,
                                                           fast_limiter):
    """Belt-and-braces: oa.fcgi retracted=yes also excludes a clean candidate."""
    import scripts.fetch_evaluation_set as fes

    stats = {"clean_skips": __import__("collections").Counter(),
             "_retracted_dois": set()}
    monkeypatch.setattr(fes, "search_pmc", lambda *a, **k: ["PMC7"])
    monkeypatch.setattr(fes, "resolve_pmcids_to_dois", lambda ids, **k: {"PMC7": "10.1/x"})

    def fake_fetch(pmcid, dest_dir, args, session, limiter):
        p = tmp_path / f"{pmcid}.pdf"
        p.write_bytes(b"%PDF")
        return str(p), {"license": "CC BY", "retracted": True}, None

    monkeypatch.setattr(fes, "_fetch_pdf", fake_fetch)
    monkeypatch.setattr(fes, "_record", lambda entry, args: None)

    args = fes.build_arg_parser().parse_args([
        "--clean-target", "1", "--dose-response-count", "1",
        "--output-dir", str(tmp_path), "--manifest", str(tmp_path / "m.json")])
    entries = fes.collect_clean_controls(args, MagicMock(), fast_limiter, stats)

    assert entries == []
    assert stats["clean_skips"][fes.SKIP_RETRACTED] == 1
    assert not (tmp_path / "PMC7.pdf").exists()  # downloaded file removed

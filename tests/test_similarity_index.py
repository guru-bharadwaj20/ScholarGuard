"""Backend-agnostic behaviour of the corpus similarity index.

The embedding tier's thresholds (embed_review 0.85, embed_high 0.985) are
COSINE SIMILARITIES. Every backend therefore has to report a cosine, whatever
its native metric is -- the annoy fallback used to report a raw annoy distance
and silently ranked candidates backwards on any machine without faiss.
"""

import os

import numpy as np
import pytest

from src.indexing.similarity_index import (
    SimilarityIndex,
    angular_distance_to_cosine,
)


def _unit(vec) -> np.ndarray:
    arr = np.asarray(vec, np.float32)
    return arr / np.linalg.norm(arr)


# --------------------------------------------------------------- conversion
@pytest.mark.parametrize("cosine", [1.0, 0.985, 0.85, 0.5, 0.0, -0.5, -1.0])
def test_angular_conversion_round_trips(cosine):
    """d = sqrt(2(1-cos)) must invert exactly back to cos."""
    distance = np.sqrt(2.0 * (1.0 - cosine))
    assert angular_distance_to_cosine(distance) == pytest.approx(cosine, abs=1e-6)


def test_angular_conversion_is_monotonically_decreasing():
    """Nearer (smaller distance) must always mean more similar."""
    distances = [0.0, 0.2, 0.5, 1.0, 1.5, 2.0]
    cosines = [angular_distance_to_cosine(d) for d in distances]
    assert all(b < a for a, b in zip(cosines, cosines[1:]))
    assert cosines[0] == pytest.approx(1.0)
    assert cosines[-1] == pytest.approx(-1.0)


def test_angular_conversion_clamps_float_error():
    assert angular_distance_to_cosine(-1e-9) <= 1.0
    assert angular_distance_to_cosine(2.0000001) >= -1.0


# ------------------------------------------------------------- ranking parity
@pytest.fixture
def corpus():
    """Four images whose similarity to the query is strictly ordered."""
    query = _unit([1.0, 0.0, 0.0, 0.0])
    rows = np.stack([
        _unit([1.00, 0.02, 0.0, 0.0]),   # nearest
        _unit([1.00, 0.40, 0.0, 0.0]),
        _unit([1.00, 1.00, 0.0, 0.0]),
        _unit([0.0, 1.00, 0.0, 0.0]),    # orthogonal, furthest
    ])
    paths = [f"/corpus/img{i}.png" for i in range(len(rows))]
    phashes = [f"{i:016x}" for i in range(len(rows))]
    return query, paths, rows, phashes


def _ranked(backend, query, paths, rows, phashes):
    """(basename, similarity) per hit. add() absolutizes paths, hence basename."""
    index = SimilarityIndex(rows.shape[1], backend=backend)
    index.add(paths, rows, phashes)
    hits = index.query_embedding(query, k=len(paths))
    return [(os.path.basename(h["path"]), h["similarity"]) for h in hits]


def test_numpy_backend_ranks_by_cosine(corpus):
    ranked = _ranked("numpy", *corpus)
    assert [p for p, _ in ranked] == [f"img{i}.png" for i in range(4)]
    sims = [s for _, s in ranked]
    assert all(b <= a for a, b in zip(sims, sims[1:]))
    assert sims[0] == pytest.approx(1.0, abs=1e-3)
    assert sims[-1] == pytest.approx(0.0, abs=1e-3)


def test_faiss_backend_matches_numpy(corpus):
    pytest.importorskip("faiss")
    faiss_ranked = _ranked("faiss", *corpus)
    numpy_ranked = _ranked("numpy", *corpus)
    assert [p for p, _ in faiss_ranked] == [p for p, _ in numpy_ranked]
    for (_, f), (_, n) in zip(faiss_ranked, numpy_ranked):
        assert f == pytest.approx(n, abs=1e-4)


def test_annoy_backend_matches_numpy(corpus):
    """The fallback backend must agree with exact search, not invert it."""
    pytest.importorskip("annoy")
    annoy_ranked = _ranked("annoy", *corpus)
    numpy_ranked = _ranked("numpy", *corpus)
    assert [p for p, _ in annoy_ranked] == [p for p, _ in numpy_ranked]
    for (_, a), (_, n) in zip(annoy_ranked, numpy_ranked):
        assert a == pytest.approx(n, abs=1e-3)
    # And the similarities must be in cosine range, not raw annoy distances.
    assert all(-1.0 <= s <= 1.0 for _, s in annoy_ranked)


def test_annoy_code_path_converts_distances_without_the_package(corpus, monkeypatch):
    """Exercise the annoy branch with a stand-in, so CI covers it too.

    annoy is an optional dependency and is absent from CI (faiss resolves
    first), which is exactly why the distance-vs-similarity bug survived: the
    fallback everyone would hit on a machine without faiss was never run. This
    stub reproduces annoy's documented contract -- neighbours ordered nearest
    first, with ANGULAR DISTANCES, not similarities.
    """
    query, paths, rows, phashes = corpus

    class _FakeAnnoyIndex:
        def __init__(self, dim, metric):
            assert metric == "angular", "must not use the dot metric"
            self._rows = []

        def add_item(self, i, vec):
            self._rows.append(np.asarray(vec, np.float64))

        def build(self, n_trees):
            self._built = True

        def get_nns_by_vector(self, vector, n, include_distances=False):
            v = np.asarray(vector, np.float64)
            cosines = [float(r @ v) for r in self._rows]
            distances = [float(np.sqrt(max(0.0, 2.0 * (1.0 - c)))) for c in cosines]
            order = sorted(range(len(distances)), key=lambda i: distances[i])[:n]
            return (order, [distances[i] for i in order]) if include_distances else order

    monkeypatch.setitem(__import__("sys").modules, "annoy",
                        type("m", (), {"AnnoyIndex": _FakeAnnoyIndex}))

    annoy_ranked = _ranked("annoy", query, paths, rows, phashes)
    numpy_ranked = _ranked("numpy", query, paths, rows, phashes)
    assert [p for p, _ in annoy_ranked] == [p for p, _ in numpy_ranked]
    for (_, a), (_, n) in zip(annoy_ranked, numpy_ranked):
        assert a == pytest.approx(n, abs=1e-4)
    # Raw annoy distances would put the nearest neighbour at ~0.02, below the
    # embed_review floor of 0.85, and discard the true duplicate.
    assert annoy_ranked[0][1] > 0.99


# --------------------------------------------------------------- phash lookup
def _index_with_hashes(hashes):
    dim = 4
    index = SimilarityIndex(dim, backend="numpy")
    index.add([f"/c/{i}.png" for i in range(len(hashes))],
              np.zeros((len(hashes), dim), np.float32), hashes)
    return index


def test_phash_hamming_distances_are_exact():
    """Vectorised popcount must agree with the obvious Python computation."""
    rng = np.random.default_rng(3)
    values = [int(rng.integers(0, 2 ** 63)) for _ in range(64)]
    hashes = [f"{v:016x}" for v in values]
    index = _index_with_hashes(hashes)

    query_value = values[0]
    hits = index.query_phash(f"{query_value:016x}", max_distance=64)
    got = {os.path.basename(h["path"]): h["hamming_distance"] for h in hits}

    for i, v in enumerate(values):
        expected = bin(v ^ query_value).count("1")
        assert got[f"{i}.png"] == expected


def test_phash_respects_the_distance_cutoff_and_orders_nearest_first():
    index = _index_with_hashes([
        "0000000000000000",   # distance 0
        "0000000000000001",   # distance 1
        "0000000000000003",   # distance 2
        "ffffffffffffffff",   # distance 64
    ])
    hits = index.query_phash("0000000000000000", max_distance=2)
    assert [h["hamming_distance"] for h in hits] == [0, 1, 2]
    assert [os.path.basename(h["path"]) for h in hits] == \
        ["0.png", "1.png", "2.png"]


def test_phash_handles_the_top_bit():
    """>u8 byte view must not misread hashes with bit 63 set."""
    index = _index_with_hashes(["8000000000000000", "0000000000000000"])
    hits = index.query_phash("8000000000000000", max_distance=64)
    by_name = {os.path.basename(h["path"]): h["hamming_distance"] for h in hits}
    assert by_name["0.png"] == 0
    assert by_name["1.png"] == 1


def test_incremental_add_keeps_every_hash():
    """add() appends to the parsed hash table instead of rebuilding it."""
    dim = 4
    index = SimilarityIndex(dim, backend="numpy")
    for i in range(4):
        index.add([f"/c/{i}.png"], np.zeros((1, dim), np.float32),
                  [f"{i:016x}"])
    assert len(index._hash_ints) == 4
    hits = index.query_phash("0000000000000000", max_distance=64)
    assert len(hits) == 4

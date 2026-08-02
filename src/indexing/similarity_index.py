"""Similarity index over a corpus of figure images.

Two lookup structures, matching the two feature types:

* an ANN index over L2-normalized deep embeddings (FAISS ``IndexFlatIP``
  preferred; falls back to Annoy, then to exact NumPy dot products), and
* a pHash table for instant near-exact duplicate lookup — 64-bit hashes
  are compared with a vectorized XOR/popcount, so even a linear scan over
  hundreds of thousands of hashes is sub-millisecond.

Embeddings are stored per *view* (whole image + 2x2 quadrant tiles, 5 rows
per image) so that a reused sub-panel can match on a tile even when the
whole-image similarity is unremarkable. Queries score a corpus image by
the maximum similarity over all (query view x corpus view) pairs.

``IndexFlatIP`` is exact (not approximate) and comfortably handles the
"hundreds to thousands of figures" scale of this project; if a corpus ever
grows past ~1M tile vectors, swap in ``faiss.IndexIVFFlat`` here without
touching callers.

The index persists to a directory (``save``/``load``) so a corpus is only
embedded once; ``build_or_load`` caches under ``<corpus>/.scholarguard_index``.
"""

from __future__ import annotations

import json
import os

import numpy as np

from src.indexing.feature_extractor import FeatureExtractor

INDEX_DIRNAME = ".scholarguard_index"


def _fingerprint_folder(paths: list[str]) -> dict[str, list]:
    """``{abspath: [size, mtime_ns]}`` for every corpus image.

    Content identity is approximated by size + modification time rather than a
    hash: hashing every image on every startup would cost more than the cache
    saves, while size+mtime catches the in-place edit that a filename-only
    check misses entirely.
    """
    out: dict[str, list] = {}
    for path in paths:
        try:
            stat = os.stat(path)
        except OSError:
            continue
        out[os.path.abspath(path)] = [stat.st_size, stat.st_mtime_ns]
    return out


def angular_distance_to_cosine(distance: float) -> float:
    """Annoy angular distance -> cosine similarity, for L2-normalized vectors.

    Annoy defines angular distance as ``sqrt(2 * (1 - cos(u, v)))``, so the
    inverse is exact::

        cos = 1 - d**2 / 2

    which maps d=0 to +1 (identical) and d=2 to -1 (opposite). Every threshold
    in this project (``embed_review``, ``embed_high``) is a cosine similarity,
    so the conversion has to happen before any comparison. Clamped to [-1, 1]
    against float error.
    """
    cosine = 1.0 - (float(distance) ** 2) / 2.0
    return max(-1.0, min(1.0, cosine))


def _pick_backend() -> str:
    try:
        import faiss  # noqa: F401
        return "faiss"
    except ImportError:
        pass
    try:
        import annoy  # noqa: F401
        return "annoy"
    except ImportError:
        return "numpy"


class SimilarityIndex:
    """Embedding ANN search + pHash lookup for a figure corpus."""

    def __init__(self, embedding_dim: int, backend: str = "auto"):
        self.embedding_dim = embedding_dim
        self.backend = _pick_backend() if backend == "auto" else backend
        self.paths: list[str] = []           # one entry per image
        self.phashes: list[str] = []         # one entry per image
        self._hash_ints: np.ndarray = np.zeros(0, np.uint64)
        self.embeddings = np.zeros((0, embedding_dim), np.float32)  # per view
        self.row_to_image = np.zeros(0, np.int64)  # embedding row -> image id
        self._ann = None  # built lazily; rebuilt after every add()

    def __len__(self) -> int:
        return len(self.paths)

    # ------------------------------------------------------------ building
    def add(
        self,
        paths: list[str],
        embeddings: np.ndarray,
        phashes: list[str],
        row_to_image: np.ndarray | None = None,
    ) -> None:
        """Add a batch of images.

        ``embeddings`` holds one row per view; ``row_to_image`` maps each
        row to its position in ``paths`` (defaults to the identity, i.e.
        one whole-image embedding per image).
        """
        if len(paths) != len(phashes):
            raise ValueError("paths and phashes must align")
        if row_to_image is None:
            if len(embeddings) != len(paths):
                raise ValueError("need row_to_image when embeddings aren't 1:1")
            row_to_image = np.arange(len(paths), dtype=np.int64)

        offset = len(self.paths)
        self.paths.extend(os.path.abspath(p) for p in paths)
        self.phashes.extend(phashes)
        # Parse only the NEW hashes and append. This used to re-parse the whole
        # table on every add(), which is quadratic over an incremental build.
        self._hash_ints = np.concatenate([
            self._hash_ints,
            np.array([int(h, 16) for h in phashes], np.uint64),
        ])
        self.embeddings = (np.concatenate([self.embeddings, embeddings])
                           .astype(np.float32))
        self.row_to_image = np.concatenate(
            [self.row_to_image, np.asarray(row_to_image, np.int64) + offset]
        )
        self._ann = None  # force rebuild on next query

    def _build_ann(self):
        if self.backend == "faiss":
            import faiss

            index = faiss.IndexFlatIP(self.embedding_dim)
            index.add(self.embeddings)
            return index
        if self.backend == "annoy":
            from annoy import AnnoyIndex

            # ANGULAR, not "dot". Annoy always returns a *distance*, and its
            # dot-metric distance is a negated inner product whose sign
            # convention has varied across releases -- feeding it straight into
            # the cosine thresholds (embed_review=0.85, embed_high=0.985)
            # ranked candidates backwards and silently. Angular distance has a
            # documented, stable definition that inverts exactly for the
            # L2-normalized vectors this index stores; see
            # :func:`angular_distance_to_cosine`.
            index = AnnoyIndex(self.embedding_dim, "angular")
            for i, vec in enumerate(self.embeddings):
                index.add_item(i, vec)
            index.build(20)
            return index
        return "numpy"  # exact brute-force fallback

    # ------------------------------------------------------------ querying
    def query_embedding(self, embedding: np.ndarray, k: int = 10) -> list[dict]:
        """Candidate corpus *images* most similar to the query.

        ``embedding`` may be a single (dim,) vector or a (T, dim) stack of
        tiled query views (view 0 = whole image, by convention of
        ``FeatureExtractor.tile_image``).

        Candidates are the union of two top-k rankings — measured on the
        synthetic corpus, neither alone retrieves everything:

        * **whole-image score** (query's whole view vs. all corpus views):
          best for whole-figure duplicates and large reused panels;
        * **tile-max score** (max over every query-view x corpus-view
          pair): lets a small reused panel dominate one quadrant tile, but
          is noisier because generic texture tiles score high everywhere.

        Returns [{"path", "similarity", "whole_similarity"}] sorted by the
        max score, up to 2k entries. Vectors are L2-normalized, so inner
        product == cosine similarity in [-1, 1].
        """
        if not self.paths:
            return []
        queries = np.atleast_2d(embedding).astype(np.float32)
        # Fetch enough view-rows that k distinct images survive dedup: each
        # image contributes up to (its view count) rows per query view.
        views_per_image = max(1, len(self.embeddings) // max(1, len(self.paths)))
        k_rows = min(len(self.embeddings), max(2 * k * views_per_image, k))

        if self._ann is None:
            self._ann = self._build_ann()

        if self.backend == "faiss":
            scores, ids = self._ann.search(queries, k_rows)
        elif self.backend == "annoy":
            ids, scores = [], []
            for query in queries:
                i, distances = self._ann.get_nns_by_vector(
                    query, k_rows, include_distances=True)
                ids.append(i)
                # Annoy hands back DISTANCES; everything downstream (and every
                # configured threshold) is in cosine similarity.
                scores.append([angular_distance_to_cosine(d) for d in distances])
            ids, scores = np.array(ids), np.array(scores)
        else:  # exact numpy
            sims = queries @ self.embeddings.T  # (T, n_rows)
            ids = np.argsort(-sims, axis=1)[:, :k_rows]
            scores = np.take_along_axis(sims, ids, axis=1)

        # Per-image best score, per query view.
        best_any: dict[int, float] = {}    # max over all views
        best_whole: dict[int, float] = {}  # query whole view only
        for view, (view_ids, view_scores) in enumerate(zip(ids, scores)):
            for row, score in zip(view_ids.tolist(), view_scores.tolist()):
                if row < 0:
                    continue
                image_id = int(self.row_to_image[row])
                best_any[image_id] = max(best_any.get(image_id, -1.0), float(score))
                if view == 0:
                    best_whole[image_id] = max(best_whole.get(image_id, -1.0),
                                               float(score))

        top_any = sorted(best_any, key=lambda i: -best_any[i])[:k]
        top_whole = sorted(best_whole, key=lambda i: -best_whole[i])[:k]
        union = sorted(set(top_any) | set(top_whole), key=lambda i: -best_any[i])
        return [{"path": self.paths[i],
                 "similarity": best_any[i],
                 "whole_similarity": best_whole.get(i, -1.0)}
                for i in union]

    def query_phash(self, phash: str, max_distance: int = 6) -> list[dict]:
        """All corpus images within a Hamming distance of the query pHash.

        Vectorized XOR + popcount over the whole table; effectively free.
        Returns [{"path", "hamming_distance"}] sorted nearest-first.
        """
        if not self.paths:
            return []
        query = np.uint64(int(phash, 16))
        xor = np.bitwise_xor(self._hash_ints, query)
        # Genuinely vectorised popcount: view the 64-bit hashes as bytes and
        # unpack to bits. The docstring has always claimed "vectorized XOR +
        # popcount ... effectively free", but the implementation was a Python
        # loop of bin(int(v)).count("1") over every corpus entry -- the one part
        # of this class that could not survive the corpus size it advertises.
        distances = np.unpackbits(
            xor.astype(">u8").view(np.uint8).reshape(-1, 8), axis=1
        ).sum(axis=1)
        # Select first, then sort: only the neighbours are ordered, not the
        # whole corpus.
        within = np.flatnonzero(distances <= max_distance)
        order = within[np.argsort(distances[within], kind="stable")]
        return [{"path": self.paths[i], "hamming_distance": int(distances[i])}
                for i in order]

    # ---------------------------------------------------------- persistence
    def save(self, directory: str, fingerprints: dict | None = None) -> None:
        os.makedirs(directory, exist_ok=True)
        np.save(os.path.join(directory, "embeddings.npy"), self.embeddings)
        np.save(os.path.join(directory, "row_to_image.npy"), self.row_to_image)
        with open(os.path.join(directory, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"paths": self.paths, "phashes": self.phashes,
                       "embedding_dim": self.embedding_dim,
                       "fingerprints": fingerprints or {}}, fh)

    @classmethod
    def load(cls, directory: str,
             backend: str = "auto") -> tuple["SimilarityIndex", dict]:
        """Load a cached index. Returns ``(index, fingerprints)``."""
        with open(os.path.join(directory, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        index = cls(meta["embedding_dim"], backend=backend)
        index.add(meta["paths"],
                  np.load(os.path.join(directory, "embeddings.npy")),
                  meta["phashes"],
                  np.load(os.path.join(directory, "row_to_image.npy")))
        return index, meta.get("fingerprints") or {}

    # ------------------------------------------------------- one-call build
    @classmethod
    def build_from_folder(
        cls,
        corpus_dir: str,
        extractor: FeatureExtractor | None = None,
        backend: str = "auto",
        show_progress: bool = True,
        tiles: bool = True,
    ) -> "SimilarityIndex":
        """Extract features for every image in a folder and index them."""
        extractor = extractor or FeatureExtractor()
        paths, phashes, embeddings, row_to_image = extractor.extract_folder(
            corpus_dir, show_progress=show_progress, tiles=tiles
        )
        index = cls(extractor.embedding_dim, backend=backend)
        if paths:
            index.add(paths, embeddings, phashes, row_to_image)
        return index

    @classmethod
    def build_or_load(
        cls,
        corpus_dir: str,
        extractor: FeatureExtractor | None = None,
        backend: str = "auto",
        show_progress: bool = True,
        force_rebuild: bool = False,
    ) -> "SimilarityIndex":
        """Load the cached index for a corpus, rebuilding when stale.

        The cache lives in ``<corpus_dir>/.scholarguard_index`` and is stale
        when any image was added, removed, **or modified in place**. Staleness
        used to be judged on the filename list alone, so editing an image and
        re-running served the old embeddings and the old pHash indefinitely --
        silently, and with no way to tell from the output.
        """
        from src.utils.image_io import list_images

        cache_dir = os.path.join(corpus_dir, INDEX_DIRNAME)
        current = _fingerprint_folder(list_images(corpus_dir))
        if not force_rebuild and os.path.isfile(os.path.join(cache_dir, "meta.json")):
            try:
                index, cached = cls.load(cache_dir, backend=backend)
                if cached == current:
                    return index
            except (OSError, KeyError, ValueError):
                pass  # stale/corrupt cache -> rebuild
        index = cls.build_from_folder(corpus_dir, extractor=extractor,
                                      backend=backend, show_progress=show_progress)
        index.save(cache_dir, fingerprints=current)
        return index

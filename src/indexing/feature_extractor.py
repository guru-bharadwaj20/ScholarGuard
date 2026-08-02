"""Per-image feature extraction for cross-figure duplicate search.

Two complementary representations per image:

* **Perceptual hash (pHash)** — 64-bit DCT hash via ``imagehash``. Nearly
  free to compute and compare; catches exact re-saves, resizes and mild
  recompression, but breaks under rotation, cropping or contrast edits.
* **Deep embedding** — global-average-pooled features from an
  ImageNet-pretrained CNN (``torchvision``, inference only, CPU). Robust
  to rotation/crop/color adjustments that defeat hashing, at the cost of
  ~0.1–0.3 s per image on a low-end CPU.

Default backbone is MobileNetV3-small: on an i3-class CPU it embeds a
figure in ~0.1 s versus ~1 s for ResNet50, with comparable retrieval
quality on figure-sized corpora. Pass ``backbone="resnet50"`` if you want
the heavier model.
"""

from __future__ import annotations

import os

import cv2
import imagehash
import numpy as np
from PIL import Image
from tqdm import tqdm

from src.utils.image_io import list_images
from src.utils.torch_config import configure_torch_threads

# torch is imported lazily so hash-only workflows don't pay its startup
# cost (and so the module still imports if torch is missing).
_TORCH_ERROR = (
    "torch/torchvision are required for deep embeddings. Install CPU-only "
    "wheels: pip install torch torchvision --index-url "
    "https://download.pytorch.org/whl/cpu"
)


class FeatureExtractor:
    """Computes perceptual hashes and deep embeddings for figure images."""

    #: embedding dimensionality per supported backbone
    BACKBONE_DIMS = {"mobilenet_v3_small": 576, "resnet50": 2048}

    def __init__(self, backbone: str = "mobilenet_v3_small", input_size: int = 224):
        if backbone not in self.BACKBONE_DIMS:
            raise ValueError(f"unsupported backbone {backbone!r}; "
                             f"choose from {sorted(self.BACKBONE_DIMS)}")
        self.backbone = backbone
        self.input_size = input_size
        self.embedding_dim = self.BACKBONE_DIMS[backbone]
        self._model = None  # built lazily on first embed() call

    # ------------------------------------------------------------- hashing
    @staticmethod
    def phash(image_path: str, hash_size: int = 8) -> imagehash.ImageHash:
        """64-bit perceptual (DCT) hash of an image file."""
        with Image.open(image_path) as img:
            return imagehash.phash(img.convert("L"), hash_size=hash_size)

    # ---------------------------------------------------------- embeddings
    def _build_model(self):
        try:
            import torch
            from torchvision import models
        except ImportError as exc:  # pragma: no cover - environment issue
            raise ImportError(_TORCH_ERROR) from exc

        if self.backbone == "mobilenet_v3_small":
            net = models.mobilenet_v3_small(
                weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
            )
            # features -> avgpool gives the 576-d penultimate representation
            model = torch.nn.Sequential(net.features, net.avgpool, torch.nn.Flatten(1))
        else:  # resnet50
            net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
            model = torch.nn.Sequential(*list(net.children())[:-1], torch.nn.Flatten(1))
        model.eval()
        # Figures are processed one query at a time, so leave a core for the
        # rest of the app -- but honour SCHOLARGUARD_TORCH_THREADS, because the
        # parallel benchmark runner pins each worker to one thread and
        # set_num_threads is process-global. This used to hardcode
        # cpu_count-1 and, since cross-figure indexes every paper, silently
        # undid that pinning inside every worker.
        configure_torch_threads()
        return model

    def _preprocess(self, bgr: np.ndarray) -> np.ndarray:
        """BGR uint8 -> normalized float32 CHW array (ImageNet stats)."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.input_size, self.input_size),
                         interpolation=cv2.INTER_AREA)
        arr = rgb.astype(np.float32) / 255.0
        arr = (arr - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
            [0.229, 0.224, 0.225], np.float32
        )
        return arr.transpose(2, 0, 1)

    def embed_images(self, images: list[np.ndarray], batch_size: int = 8) -> np.ndarray:
        """Embed a list of BGR images. Returns L2-normalized (N, dim) floats.

        L2-normalization makes inner product == cosine similarity, which is
        what the FAISS index and all thresholds in this project assume.
        """
        import torch

        if self._model is None:
            self._model = self._build_model()

        chunks = []
        with torch.inference_mode():
            for start in range(0, len(images), batch_size):
                batch = np.stack([self._preprocess(im)
                                  for im in images[start:start + batch_size]])
                feats = self._model(torch.from_numpy(batch)).numpy()
                chunks.append(feats)
        embeddings = np.concatenate(chunks).astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / np.clip(norms, 1e-12, None)

    def embed_path(self, image_path: str) -> np.ndarray:
        """Embed a single image file -> L2-normalized (dim,) vector."""
        from src.utils.image_io import load_image

        return self.embed_images([load_image(image_path)])[0]

    # ------------------------------------------------------------- tiling
    @staticmethod
    def tile_image(bgr: np.ndarray) -> list[np.ndarray]:
        """Whole image + 2x2 quadrants (5 views).

        A reused *panel* occupies only a fraction of a figure and barely
        moves a global embedding, so retrieval on whole-image vectors
        misses it. Embedding each quadrant separately lets a panel
        dominate at least one tile's vector. 2x2 (not finer) keeps the
        index at 5 vectors/image, which MobileNetV3 handles at ~0.5 s per
        figure on an i3-class CPU.
        """
        h, w = bgr.shape[:2]
        half_h, half_w = h // 2, w // 2
        return [
            bgr,
            bgr[:half_h, :half_w], bgr[:half_h, half_w:],
            bgr[half_h:, :half_w], bgr[half_h:, half_w:],
        ]

    def embed_tiles(self, bgr: np.ndarray, batch_size: int = 8) -> np.ndarray:
        """Embed the 5 tiled views of one BGR image -> (5, dim)."""
        return self.embed_images(self.tile_image(bgr), batch_size=batch_size)

    # -------------------------------------------------------- combined API
    def extract(self, image_path: str) -> dict:
        """Both representations for one image file."""
        return {
            "phash": str(self.phash(image_path)),
            "embedding": self.embed_path(image_path),
        }

    def extract_folder(
        self,
        folder: str,
        batch_size: int = 8,
        show_progress: bool = True,
        tiles: bool = True,
    ) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
        """Extract features for every image in a folder.

        Returns ``(paths, phashes, embeddings, row_to_image)`` where
        ``embeddings`` holds one row per *view* (5 tiled views per image
        when ``tiles=True``, else 1) and ``row_to_image[r]`` gives the
        index into ``paths`` that row ``r`` belongs to. On an i3-class CPU
        expect ~2 images/s tiled with MobileNetV3-small.
        """
        from src.utils.image_io import load_image

        paths = list_images(folder)
        phashes: list[str] = []
        embeddings: list[np.ndarray] = []
        row_to_image: list[int] = []
        iterator = enumerate(paths)
        if show_progress:
            iterator = tqdm(iterator, total=len(paths),
                            desc=f"indexing {os.path.basename(folder) or folder}",
                            unit="img")
        for image_id, path in iterator:
            phashes.append(str(self.phash(path)))
            image = load_image(path)
            views = self.tile_image(image) if tiles else [image]
            embeddings.append(self.embed_images(views, batch_size=batch_size))
            row_to_image.extend([image_id] * len(views))
        stacked = (np.concatenate(embeddings) if embeddings
                   else np.zeros((0, self.embedding_dim), np.float32))
        return paths, phashes, stacked, np.array(row_to_image, np.int64)

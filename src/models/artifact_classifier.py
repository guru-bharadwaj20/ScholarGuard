"""Lightweight real-vs-AI-generated image classifier (inference only).

This module defines the *architecture* and an *inference-only* loader. It
deliberately contains **no training loop** — the classifier is fine-tuned
separately on a GPU via ``colab/train_artifact_classifier.ipynb`` and its
weights are downloaded to ``src/models/weights/artifact_classifier.pt``.

Design
------
* Backbone: **MobileNetV3-small** (ImageNet-pretrained), chosen for the
  same reason as Stage 3 — it runs on CPU (~0.1 s/image) yet fine-tunes
  quickly on a free T4. The 1000-way head is replaced with a 2-logit
  (real / AI-generated) classification head.
* Input: 224x224 RGB, ImageNet normalization (matches the training
  notebook exactly — keep the two in sync).
* A checkpoint is a dict ``{"state_dict", "backbone", "input_size",
  "classes", "val_accuracy", ...}`` so inference can verify it matches this
  architecture.

Inference still runs (slowly) on a CPU-only laptop; if no weights file is
present, :func:`classify_artifact` returns ``None`` so the Stage 4
orchestrator can fall back to the frequency + noise signals alone.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

DEFAULT_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights",
                                    "artifact_classifier.pt")
INPUT_SIZE = 224
CLASSES = ("real", "ai_generated")
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], np.float32)


def build_model(backbone: str = "mobilenet_v3_small", num_classes: int = 2):
    """Construct the classifier architecture (untrained).

    Shared by both the Colab training notebook and local inference so the
    two never drift. Returns a ``torch.nn.Module``.
    """
    import torch  # noqa: F401  (import here so the module loads without torch)
    from torchvision import models

    if backbone == "mobilenet_v3_small":
        net = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
        )
        in_features = net.classifier[3].in_features
        net.classifier[3] = _new_linear(in_features, num_classes)
    elif backbone == "efficientnet_b0":
        net = models.efficientnet_b0(
            weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1
        )
        in_features = net.classifier[1].in_features
        net.classifier[1] = _new_linear(in_features, num_classes)
    else:
        raise ValueError(f"unsupported backbone {backbone!r}")
    return net


def _new_linear(in_features: int, num_classes: int):
    import torch.nn as nn

    return nn.Linear(in_features, num_classes)


def _preprocess(image_path: str):
    """Load an image file -> (1, 3, H, W) float tensor, ImageNet-normalized."""
    import torch

    from src.utils.image_io import load_image

    bgr = load_image(image_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
    arr = (rgb.astype(np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
    return torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)


# Cache the loaded model so repeated calls don't rebuild/reload it.
_loaded: dict = {}


def weights_available(weights_path: str | None = None) -> bool:
    """True if a classifier checkpoint exists on disk."""
    return os.path.isfile(weights_path or DEFAULT_WEIGHTS_PATH)


def classify_artifact(image_path: str, weights_path: str | None = None) -> dict | None:
    """Classify one image as real vs AI-generated (inference only).

    Returns ``{"is_ai_generated": bool, "confidence": float,
    "p_ai_generated": float, "val_accuracy": float | None}`` or **None** if
    no trained weights are available (so callers can degrade gracefully to
    the forensic signals).

    ``confidence`` is the probability of the predicted class; ``p_ai_
    generated`` is always the AI-generated class probability.
    """
    weights_path = weights_path or DEFAULT_WEIGHTS_PATH
    if not os.path.isfile(weights_path):
        return None

    import torch

    if weights_path not in _loaded:
        checkpoint = torch.load(weights_path, map_location="cpu")
        model = build_model(checkpoint.get("backbone", "mobilenet_v3_small"),
                            num_classes=len(checkpoint.get("classes", CLASSES)))
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        # One process gets the machine; N parallel processes must not each take
        # it (the benchmark runner sets SCHOLARGUARD_TORCH_THREADS to 1 in every
        # worker, otherwise 32 processes would open 31 threads apiece and
        # thrash). Shared with the feature extractor so the policy is decided
        # once — see src.utils.torch_config.
        from src.utils.torch_config import configure_torch_threads

        configure_torch_threads()
        _loaded[weights_path] = checkpoint, model
    checkpoint, model = _loaded[weights_path]

    with torch.inference_mode():
        logits = model(_preprocess(image_path))
        probs = torch.softmax(logits, dim=1)[0].numpy()

    classes = checkpoint.get("classes", CLASSES)
    ai_idx = list(classes).index("ai_generated")
    p_ai = float(probs[ai_idx])
    return {
        "is_ai_generated": bool(p_ai >= 0.5),
        "confidence": float(max(p_ai, 1.0 - p_ai)),
        "p_ai_generated": p_ai,
        "val_accuracy": checkpoint.get("val_accuracy"),
    }

"""Round-trip test for the AI-generation classifier load/inference path.

We cannot train on a GPU in CI, but we CAN prove that a checkpoint in the
exact format the Colab notebook writes will load and run through
``classify_artifact`` and blend into the AI detector — so the training,
once done, pays off with zero glue work.
"""


import cv2
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from src.models import artifact_classifier as AC


@pytest.fixture(scope="module")
def trained_checkpoint(tmp_path_factory):
    """A checkpoint in the notebook's format, from a (randomly-init) model."""
    model = AC.build_model("mobilenet_v3_small", num_classes=2)
    ckpt = {
        "state_dict": model.state_dict(),
        "backbone": "mobilenet_v3_small",
        "input_size": AC.INPUT_SIZE,
        "classes": list(AC.CLASSES),
        "val_accuracy": 0.91,
        "normalization": {"mean": [0.485, 0.456, 0.406],
                          "std": [0.229, 0.224, 0.225]},
    }
    path = tmp_path_factory.mktemp("weights") / "artifact_classifier.pt"
    torch.save(ckpt, str(path))
    return str(path)


@pytest.fixture
def image_file(tmp_path):
    img = (np.random.default_rng(0).integers(0, 255, (128, 160, 3))).astype(np.uint8)
    p = tmp_path / "fig.png"
    cv2.imwrite(str(p), img)
    return str(p)


def test_no_weights_returns_none(image_file, tmp_path):
    assert AC.classify_artifact(image_file, str(tmp_path / "absent.pt")) is None
    assert AC.weights_available(str(tmp_path / "absent.pt")) is False


def test_checkpoint_roundtrip_classifies(trained_checkpoint, image_file):
    AC._loaded.clear()
    assert AC.weights_available(trained_checkpoint) is True
    r = AC.classify_artifact(image_file, trained_checkpoint)
    assert r is not None
    assert set(r) >= {"is_ai_generated", "confidence", "p_ai_generated",
                      "val_accuracy"}
    assert 0.0 <= r["p_ai_generated"] <= 1.0
    assert 0.5 <= r["confidence"] <= 1.0
    assert r["val_accuracy"] == 0.91


def test_detector_blends_classifier_when_present(trained_checkpoint, image_file):
    """detect_ai_generation must switch to the blended (classifier) verdict."""
    from src.detectors.ai_generation_detector import detect_ai_generation
    AC._loaded.clear()
    r = detect_ai_generation(image_file, weights_path=trained_checkpoint)
    assert r["classifier_score"] is not None          # classifier engaged
    assert r["details"]["classifier_available"] is True

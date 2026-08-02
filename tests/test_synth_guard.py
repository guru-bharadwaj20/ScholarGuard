"""The synthetic generator must never write into a real dataset directory.

`data/clean/` is the real PMC control corpus: tests/test_real_image_regression.py
reads it, and scripts/train_artifact_classifier.py uses it as the REAL class
when training the AI detector. The CLI used to default --clean-dir to exactly
that path, so `python -m src.utils.synth` dropped clean_000.png..clean_005.png
into it -- and data/ is gitignored, so nothing would have flagged it.
"""

import cv2
import numpy as np
import pytest

from src.utils import synth


def _write_image(path, value=200):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((40, 40, 3), value, np.uint8))


def test_refuses_to_write_into_a_directory_of_real_images(tmp_path):
    real = tmp_path / "clean"
    _write_image(real / "PMC13343060_rmdopen-12-3-g001.jpg")

    with pytest.raises(ValueError, match="refusing to write synthetic figures"):
        synth.generate_dataset(str(tmp_path / "synthetic"), n_forged=1,
                               n_clean=1, clean_dir=str(real))

    # Nothing was written into the real directory.
    assert [p.name for p in real.iterdir()] == [
        "PMC13343060_rmdopen-12-3-g001.jpg"]


def test_refuses_when_the_forged_output_dir_holds_real_images(tmp_path):
    out = tmp_path / "out"
    _write_image(out / "PMC999_fig1.jpg")
    with pytest.raises(ValueError, match="refusing to write synthetic figures"):
        synth.generate_dataset(str(out), n_forged=1, n_clean=1)


def test_allows_an_empty_or_previously_synthetic_directory(tmp_path):
    out = tmp_path / "synthetic"
    clean = tmp_path / "synthetic_clean"

    first = synth.generate_dataset(str(out), n_forged=1, n_clean=1,
                                   clean_dir=str(clean), seed=1)
    assert len(first["forged"]) == 1 and len(first["clean"]) == 1

    # Re-running over its own output is fine -- those names are ours.
    second = synth.generate_dataset(str(out), n_forged=1, n_clean=1,
                                    clean_dir=str(clean), seed=2)
    assert len(second["forged"]) == 1


def test_cli_default_clean_dir_is_not_the_real_corpus():
    import subprocess
    import sys

    help_text = subprocess.run(
        [sys.executable, "-m", "src.utils.synth", "--help"],
        capture_output=True, text=True, check=True).stdout
    assert "data/synthetic_clean" in help_text
    assert "default: data/clean)" not in help_text

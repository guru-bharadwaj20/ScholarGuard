"""Synthetic copy-move forgery generator.

Produces images that mimic common scientific-figure content (blot-like
bands, microscopy-style blobs, plot markers) on a noisy background, then
copy-moves a patch to a new location and records the ground-truth mask
(source + duplicate marked, matching Stage 1's output convention:
``<stem>.png`` + ``<stem>_mask.png``).

This is a stand-in / augmentation for the Stage 1 dataset so that the
Stage 2 detector can be developed and benchmarked end-to-end. If real
Stage 1 output already sits in ``data/synthetic/`` with the same naming
convention, this module is not needed.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np

from src.utils.image_io import save_image, save_mask


def make_base_figure(rng: np.random.Generator, size: tuple[int, int] = (480, 640)) -> np.ndarray:
    """Create a synthetic 'scientific figure' style grayscale image (as BGR).

    Light noisy background (like a blot/gel scan) with dark elliptical
    bands and small blob clusters, then mild blur + sensor noise so the
    texture statistics are not trivially uniform.
    """
    h, w = size
    # Paper-like background with low-frequency shading
    base = np.full((h, w), 225.0, np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base += 12 * np.sin(xx / w * np.pi * rng.uniform(0.5, 2))
    base += 8 * np.cos(yy / h * np.pi * rng.uniform(0.5, 2))

    # Dark "bands" (western blot style). Each band gets its own internal
    # texture so no two bands in a *clean* image are pixel-identical —
    # otherwise a copy-move detector would (correctly!) flag them.
    for _ in range(rng.integers(4, 8)):
        cx, cy = rng.integers(60, w - 60), rng.integers(50, h - 50)
        ax, ay = rng.integers(25, 60), rng.integers(8, 18)
        darkness = rng.uniform(90, 170)
        band = np.zeros((h, w), np.float32)
        cv2.ellipse(band, (int(cx), int(cy)), (int(ax), int(ay)),
                    float(rng.uniform(-8, 8)), 0, 360, darkness, -1)
        texture = cv2.GaussianBlur(
            rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 2.0
        )
        band *= 1.0 + 0.6 * texture
        band = cv2.GaussianBlur(band, (0, 0), rng.uniform(2, 5))
        base -= band

    # Small blob clusters (microscopy style), each with a unique intensity
    # wobble for the same reason as the bands above.
    for _ in range(rng.integers(15, 35)):
        cx, cy = rng.integers(10, w - 10), rng.integers(10, h - 10)
        radius = int(rng.integers(2, 6))
        blob = np.zeros((h, w), np.float32)
        cv2.circle(blob, (int(cx), int(cy)), radius, float(rng.uniform(45, 165)), -1)
        blob *= 1.0 + 0.25 * rng.standard_normal()
        base = np.where(blob > 0, blob + rng.normal(0, 6, (h, w)).astype(np.float32),
                        base)

    # Medium-scale grain (paper/scanner texture) so every location has a
    # unique fingerprint that survives the final blur.
    grain = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.5)
    base += 8.0 * grain

    base = cv2.GaussianBlur(base, (0, 0), 1.0)
    base += rng.normal(0, 4.5, (h, w)).astype(np.float32)  # sensor noise
    gray = np.clip(base, 0, 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def apply_copy_move(
    image: np.ndarray,
    rng: np.random.Generator,
    patch_size: tuple[int, int] | None = None,
    max_rotation_deg: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Copy a patch and paste it elsewhere in the same image.

    Returns (forged_image, ground_truth_mask) where the mask marks BOTH the
    source and pasted regions (the usual convention for copy-move ground
    truth, since either could be "the fake").
    """
    h, w = image.shape[:2]
    if patch_size is None:
        patch_size = (int(rng.integers(50, 90)), int(rng.integers(60, 110)))
    ph, pw = patch_size

    # Pick the source window with the most content among random candidates —
    # real fraud duplicates *content* (a band, a cell cluster), not blank
    # background, and a noise-only patch would be undetectable by design.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    best_std = -1.0
    sy = sx = 10
    for _ in range(40):
        cy = int(rng.integers(10, h - ph - 10))
        cx = int(rng.integers(10, w - pw - 10))
        std = float(gray[cy:cy + ph, cx:cx + pw].std())
        if std > best_std:
            best_std, sy, sx = std, cy, cx
    patch = image[sy:sy + ph, sx:sx + pw].copy()

    if max_rotation_deg > 0:
        angle = float(rng.uniform(-max_rotation_deg, max_rotation_deg))
        rotation = cv2.getRotationMatrix2D((pw / 2, ph / 2), angle, 1.0)
        patch = cv2.warpAffine(patch, rotation, (pw, ph),
                               borderMode=cv2.BORDER_REPLICATE)

    # Destination far enough away that source and paste don't overlap.
    for _ in range(200):
        dy = int(rng.integers(10, h - ph - 10))
        dx = int(rng.integers(10, w - pw - 10))
        if abs(dy - sy) > ph or abs(dx - sx) > pw:
            break

    forged = image.copy()
    forged[dy:dy + ph, dx:dx + pw] = patch

    mask = np.zeros((h, w), np.uint8)
    mask[sy:sy + ph, sx:sx + pw] = 255
    mask[dy:dy + ph, dx:dx + pw] = 255
    return forged, mask


def generate_dataset(
    output_dir: str,
    n_forged: int = 12,
    n_clean: int = 6,
    clean_dir: str | None = None,
    seed: int = 42,
    max_rotation_deg: float = 5.0,
) -> dict:
    """Write a small benchmark dataset to disk.

    Forged images + ``_mask.png`` ground truths go to ``output_dir``;
    clean (unforged) images go to ``clean_dir`` if given, else alongside
    with an all-zero mask.
    """
    rng = np.random.default_rng(seed)
    os.makedirs(output_dir, exist_ok=True)
    written = {"forged": [], "clean": []}

    for i in range(n_forged):
        base = make_base_figure(rng)
        # Half plain translations, half with a small rotation
        rotation = max_rotation_deg if i % 2 else 0.0
        forged, mask = apply_copy_move(base, rng, max_rotation_deg=rotation)
        image_path = os.path.join(output_dir, f"forged_{i:03d}.png")
        save_image(forged, image_path)
        save_mask(mask, os.path.join(output_dir, f"forged_{i:03d}_mask.png"))
        written["forged"].append(image_path)

    target = clean_dir or output_dir
    os.makedirs(target, exist_ok=True)
    for i in range(n_clean):
        clean = make_base_figure(rng)
        image_path = os.path.join(target, f"clean_{i:03d}.png")
        save_image(clean, image_path)
        written["clean"].append(image_path)

    return written


# --------------------------------------------------------------------------
# Stage 3: multi-paper figure corpus with cross-figure reuse ground truth
# --------------------------------------------------------------------------
def _transform_panel(panel: np.ndarray, rng: np.random.Generator,
                     kind: str) -> np.ndarray:
    """Apply the kind of edits fraudsters use to disguise a reused panel."""
    out = panel.copy()
    if kind in ("rotate", "rotate_crop"):
        h, w = out.shape[:2]
        angle = float(rng.uniform(-12, 12))
        rotation = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        out = cv2.warpAffine(out, rotation, (w, h), borderMode=cv2.BORDER_REPLICATE)
    if kind in ("crop", "rotate_crop"):
        h, w = out.shape[:2]
        margin_y, margin_x = int(h * 0.08), int(w * 0.08)
        out = out[margin_y:h - margin_y, margin_x:w - margin_x]
    if kind == "brightness":
        out = np.clip(out.astype(np.float32) * rng.uniform(0.85, 1.15)
                      + rng.uniform(-12, 12), 0, 255).astype(np.uint8)
    if kind == "recompress":
        quality = int(rng.integers(55, 80))
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            out = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return out


def generate_figure_corpus(
    output_dir: str,
    n_papers: int = 8,
    figures_per_paper: int = 3,
    n_whole_duplicates: int = 3,
    n_panel_reuses: int = 4,
    seed: int = 123,
) -> dict:
    """Simulate a database of figures from multiple papers, with fraud.

    Writes ``paperNN_figM.png`` images plus:

    * ``n_whole_duplicates`` figures that are disguised copies of another
      figure (resized / recompressed / brightness-shifted / rotated+cropped),
      named ``dupNN_of_<source>.png``;
    * ``n_panel_reuses`` figures that embed a transformed *sub-region*
      (panel) cropped from another figure, named ``reuseNN_from_<source>.png``.

    Ground truth is saved to ``<output_dir>/ground_truth.json`` as
    ``{"pairs": [{"query", "source", "type"}], "clean": [...]}``.
    """
    rng = np.random.default_rng(seed)
    os.makedirs(output_dir, exist_ok=True)

    originals = []
    for paper in range(n_papers):
        for fig in range(figures_per_paper):
            size = (int(rng.integers(400, 560)), int(rng.integers(520, 720)))
            image = make_base_figure(rng, size=size)
            name = f"paper{paper:02d}_fig{fig}.png"
            save_image(image, os.path.join(output_dir, name))
            originals.append(name)

    pairs = []
    whole_kinds = ["recompress", "brightness", "rotate_crop"]
    for i in range(n_whole_duplicates):
        source = originals[int(rng.integers(len(originals)))]
        image = cv2.imread(os.path.join(output_dir, source))
        kind = whole_kinds[i % len(whole_kinds)]
        dup = _transform_panel(image, rng, kind)
        if kind == "recompress":  # also resize, as republication typically does
            dup = cv2.resize(dup, None, fx=0.85, fy=0.85, interpolation=cv2.INTER_AREA)
        name = f"dup{i:02d}_of_{os.path.splitext(source)[0]}.png"
        save_image(dup, os.path.join(output_dir, name))
        pairs.append({"query": name, "source": source,
                      "type": f"whole_{kind}"})

    for i in range(n_panel_reuses):
        source = originals[int(rng.integers(len(originals)))]
        src_img = cv2.imread(os.path.join(output_dir, source))
        h, w = src_img.shape[:2]
        # Crop the most content-rich candidate window as the reused panel.
        ph, pw = int(h * rng.uniform(0.30, 0.45)), int(w * rng.uniform(0.30, 0.45))
        best_std, sy, sx = -1.0, 0, 0
        gray = cv2.cvtColor(src_img, cv2.COLOR_BGR2GRAY)
        for _ in range(40):
            cy, cx = int(rng.integers(0, h - ph)), int(rng.integers(0, w - pw))
            std = float(gray[cy:cy + ph, cx:cx + pw].std())
            if std > best_std:
                best_std, sy, sx = std, cy, cx
        panel = _transform_panel(src_img[sy:sy + ph, sx:sx + pw], rng,
                                 "rotate" if i % 2 else "brightness")

        # Paste the panel into a brand-new figure ("different experiment").
        host = make_base_figure(rng, size=(int(rng.integers(420, 540)),
                                           int(rng.integers(560, 700))))
        hh, hw = host.shape[:2]
        py = int(rng.integers(10, hh - panel.shape[0] - 10))
        px = int(rng.integers(10, hw - panel.shape[1] - 10))
        host[py:py + panel.shape[0], px:px + panel.shape[1]] = panel
        name = f"reuse{i:02d}_from_{os.path.splitext(source)[0]}.png"
        save_image(host, os.path.join(output_dir, name))
        pairs.append({"query": name, "source": source, "type": "panel"})

    ground_truth = {"pairs": pairs, "clean": originals}
    with open(os.path.join(output_dir, "ground_truth.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ground_truth, fh, indent=2)
    return ground_truth


# --------------------------------------------------------------------------
# Stage 4: real-vs-AI-generated figure samples for the generation detector
# --------------------------------------------------------------------------
def apply_generative_artifacts(
    image: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Bake the *forensic signatures* of a generative model into an image.

    This is a LOCAL STAND-IN for real GAN/diffusion output — it does not
    call any generator. It reproduces the three artifacts the Stage 4
    forensics modules key on, so the pipeline can be built and validated
    end-to-end on a CPU-only laptop:

    1. **Over-smoothed sensor noise** — a strong denoise (bilateral +
       Gaussian) strips the broadband high-frequency noise floor, leaving
       an unnaturally weak, spatially-correlated residual (as diffusion
       decoders do).
    2. **Periodic upsampling grid** — a faint checkerboard added at a fixed
       stride, mimicking transposed-convolution ("deconv") artifacts that
       show up as periodic peaks in the spectrum.
    3. **Mild recompression** — as republished generated images usually get.

    For PRODUCTION, replace ``data/ai_generated_samples/`` with genuine
    generator output (see colab/train_artifact_classifier.ipynb) — these
    synthetic samples are for wiring/validation, not a substitute for real
    diffusion data.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    # 1. Over-smooth: remove the sensor noise floor.
    smooth = cv2.bilateralFilter(gray, 7, 40, 40)
    smooth = cv2.GaussianBlur(smooth, (0, 0), 0.8).astype(np.float32)

    # 2. Periodic grid (checkerboard) from a fixed upsampling stride.
    h, w = smooth.shape
    stride = int(rng.choice([2, 4]))
    yy, xx = np.mgrid[0:h, 0:w]
    grid = ((yy % stride) < stride // 2) ^ ((xx % stride) < stride // 2)
    smooth += (grid.astype(np.float32) - 0.5) * rng.uniform(2.5, 4.0)

    # A whisper of low-amplitude, spatially-smooth "generator noise" (NOT
    # the broadband white noise a real sensor leaves).
    gen_noise = cv2.GaussianBlur(
        rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.2
    )
    smooth += 1.2 * gen_noise

    out = np.clip(smooth, 0, 255).astype(np.uint8)
    out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    # 3. Mild JPEG recompression.
    quality = int(rng.integers(70, 90))
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        out = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return out


def generate_ai_detection_dataset(
    ai_dir: str = "data/ai_generated_samples",
    real_dir: str = "data/real_captured_samples",
    n_each: int = 120,
    seed: int = 202,
) -> dict:
    """Write paired real / AI-generated sample sets for Stage 4.

    ``real`` samples are ``make_base_figure`` outputs (broadband sensor
    noise); ``ai`` samples are the same content pushed through
    :func:`apply_generative_artifacts`. Files are named ``real_NNN.png`` /
    ``ai_NNN.png``. Returns ``{"real": [...], "ai": [...]}``.
    """
    rng = np.random.default_rng(seed)
    os.makedirs(ai_dir, exist_ok=True)
    os.makedirs(real_dir, exist_ok=True)
    written = {"real": [], "ai": []}

    for i in range(n_each):
        size = (int(rng.integers(420, 560)), int(rng.integers(520, 700)))
        base = make_base_figure(rng, size=size)

        real_path = os.path.join(real_dir, f"real_{i:03d}.png")
        save_image(base, real_path)
        written["real"].append(real_path)

        ai_path = os.path.join(ai_dir, f"ai_{i:03d}.png")
        save_image(apply_generative_artifacts(base, rng), ai_path)
        written["ai"].append(ai_path)

    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="generate synthetic forgeries")
    parser.add_argument("--output", default="data/synthetic")
    parser.add_argument("--clean-dir", default="data/clean")
    parser.add_argument("--n-forged", type=int, default=12)
    parser.add_argument("--n-clean", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--corpus", action="store_true",
                        help="generate the Stage 3 figure corpus instead")
    parser.add_argument("--corpus-dir", default="data/figure_corpus")
    parser.add_argument("--ai", action="store_true",
                        help="generate the Stage 4 real-vs-AI dataset instead")
    parser.add_argument("--ai-dir", default="data/ai_generated_samples")
    parser.add_argument("--real-dir", default="data/real_captured_samples")
    parser.add_argument("--n-each", type=int, default=120)
    args = parser.parse_args()

    if args.ai:
        written = generate_ai_detection_dataset(
            args.ai_dir, args.real_dir, n_each=args.n_each, seed=args.seed
        )
        print(f"wrote {len(written['real'])} real -> {args.real_dir}, "
              f"{len(written['ai'])} AI-generated -> {args.ai_dir}")
    elif args.corpus:
        gt = generate_figure_corpus(args.corpus_dir, seed=args.seed)
        print(f"wrote corpus to {args.corpus_dir}: "
              f"{len(gt['clean'])} originals, {len(gt['pairs'])} reuse cases")
    else:
        result = generate_dataset(args.output, args.n_forged, args.n_clean,
                                  clean_dir=args.clean_dir, seed=args.seed)
        print(f"wrote {len(result['forged'])} forged -> {args.output}, "
              f"{len(result['clean'])} clean -> {args.clean_dir}")

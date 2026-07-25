#!/usr/bin/env python
"""Generate GENUINE diffusion-model figures for the AI-generation classifier.

Why this exists
---------------
``src/utils/synth.py --ai`` writes *stand-ins*: a real sample bilateral-denoised
with a checkerboard added, which its own docstring calls "for wiring/validation,
not a substitute for real diffusion data". A classifier trained on those learns
``cv2.bilateralFilter``, not a generator. This script produces the real thing —
Stable-Diffusion output — so ``colab/train_artifact_classifier.ipynb`` (or
``scripts/train_artifact_classifier.py``) has a defensible AI class.

Confound matching (the reason this is not just a bare pipeline call)
-------------------------------------------------------------------
Publisher figures reach us as ~700px JPEGs with a visible 8x8 grid; raw
diffusion output is a clean 1024px PNG. Train on that pair and the classifier
separates *resolution and compression*, not generator artifacts — the exact
failure the README documents for the forensic detector's compression baselines.
So every generated image is, before saving:

1. **resized** to a (width, height) drawn from the real class's own size
   distribution (measured from ``--real-dir``), and
2. **JPEG re-encoded** at the quality whose measured blockiness
   (``src.forensics.jpeg_quality.estimate_blockiness``) best matches a target
   drawn from the real class's blockiness distribution.

What survives that treatment is the generator's own signature: the missing
broadband sensor-noise floor and the decoder's periodic upsampling residue —
which is what the detector is supposed to key on.

A ``provenance.json`` sidecar records model, prompts, sampler settings, seed
and the matched statistics, so the set is reproducible and auditable.

Example:
    python scripts/generate_ai_figures.py --n 400
    python scripts/generate_ai_figures.py --n 64 --model stabilityai/sdxl-turbo \
        --steps 4 --guidance 0.0
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from src.forensics.jpeg_quality import estimate_blockiness  # noqa: E402

logger = logging.getLogger("scholarguard.data")

#: Subject prompts spanning the figure types the pipeline actually sees.
PROMPTS = [
    "a western blot membrane photograph, protein bands in lanes, grayscale scan",
    "an agarose gel electrophoresis photograph with DNA ladder lanes, grayscale",
    "a fluorescence microscopy image of cultured cells, DAPI nuclei stain, blue",
    "a confocal immunofluorescence micrograph, green GFP signal on dark field",
    "a hematoxylin and eosin stained tissue section, brightfield histology",
    "an immunohistochemistry stained tumor tissue section, brown DAB staining",
    "a transmission electron micrograph of a cell, grayscale, high magnification",
    "a scanning electron micrograph of bacterial cells, grayscale",
    "a phase contrast micrograph of a cell monolayer, grayscale",
    "a coomassie stained SDS-PAGE protein gel photograph, blue bands",
    "a tissue immunofluorescence panel, red and green channels merged",
    "a cell culture wound healing scratch assay micrograph, brightfield",
]

#: JPEG qualities searched when matching the real class's blockiness.
QUALITY_GRID = (95, 90, 85, 80, 75, 70, 65, 60, 55, 50)


def measure_real_class(real_dir: str) -> dict:
    """Size + blockiness distribution of the real figures we must match."""
    paths = sorted(glob.glob(os.path.join(real_dir, "*.jpg"))
                   + glob.glob(os.path.join(real_dir, "*.jpeg"))
                   + glob.glob(os.path.join(real_dir, "*.png")))
    sizes, blockiness = [], []
    for path in paths:
        gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape[:2]
        sizes.append((w, h))
        blockiness.append(estimate_blockiness(gray))
    if not sizes:
        raise RuntimeError(f"no readable images in {real_dir!r} to match against")
    logger.info("real class: n=%d, width med %d, height med %d, "
                "blockiness mean %.4f sd %.4f", len(sizes),
                int(np.median([s[0] for s in sizes])),
                int(np.median([s[1] for s in sizes])),
                float(np.mean(blockiness)), float(np.std(blockiness)))
    return {"n": len(sizes), "sizes": sizes, "blockiness": blockiness}


def match_and_save(rgb: np.ndarray, out_path: str, stats: dict,
                   rng: np.random.Generator) -> dict:
    """Resize + JPEG-encode one generated image to match the real class.

    Returns the realized ``{"size", "quality", "blockiness", "target"}`` so the
    provenance file can show how well the match landed.
    """
    width, height = stats["sizes"][int(rng.integers(len(stats["sizes"])))]
    resized = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR)

    target = float(stats["blockiness"][int(rng.integers(len(stats["blockiness"])))])
    best = None
    for quality in QUALITY_GRID:
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
        if not ok:
            continue
        decoded = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        got = estimate_blockiness(decoded)
        score = abs(got - target)
        if best is None or score < best[0]:
            best = (score, quality, got, buf)
    if best is None:
        raise RuntimeError("JPEG encoding failed for every quality in the grid")

    _score, quality, got, buf = best
    with open(out_path, "wb") as fh:
        fh.write(buf.tobytes())
    return {"size": [width, height], "quality": int(quality),
            "blockiness": round(got, 5), "blockiness_target": round(target, 5)}


def build_pipeline(args):
    """Load the diffusion pipeline onto the GPU in fp16."""
    import torch
    from diffusers import AutoencoderKL, AutoPipelineForText2Image

    if not torch.cuda.is_available():
        raise RuntimeError("no CUDA device: generation needs a GPU (this is the "
                           "one GPU-only step; everything else is CPU-only)")
    logger.info("loading %s onto %s", args.model, torch.cuda.get_device_name(0))
    extra = {}
    if args.vae:
        # SDXL's original VAE overflows in fp16, so diffusers silently upcasts it
        # to fp32 for every decode — which dominated the runtime (~3.4 img/min)
        # and pushed VRAM to the card's limit. The fp16-fix VAE is the same
        # architecture rescaled to stay in fp16 range: same decoder family, so
        # the upsampling artifacts the classifier learns are unchanged.
        extra["vae"] = AutoencoderKL.from_pretrained(
            args.vae, torch_dtype=torch.float16)
        logger.info("using fp16 VAE %s (avoids the fp32 decode upcast)", args.vae)
    pipe = AutoPipelineForText2Image.from_pretrained(
        args.model, torch_dtype=torch.float16, variant="fp16",
        use_safetensors=True, **extra)
    pipe = pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    if args.no_safety_checker and hasattr(pipe, "safety_checker"):
        # Scientific micrographs trip the NSFW heuristic and come back as black
        # frames, which would silently poison the training class.
        pipe.safety_checker = None
    return pipe


def run(args) -> int:
    import torch

    os.makedirs(args.out, exist_ok=True)
    stats = measure_real_class(args.real_dir)
    pipe = build_pipeline(args)
    rng = np.random.default_rng(args.seed)

    records: list[dict] = []
    generated = 0
    while generated < args.n:
        batch = min(args.batch_size, args.n - generated)
        prompts = [PROMPTS[(generated + i) % len(PROMPTS)] for i in range(batch)]
        gen = torch.Generator("cuda").manual_seed(args.seed + generated)
        images = pipe(prompt=prompts,
                      num_inference_steps=args.steps,
                      guidance_scale=args.guidance,
                      height=args.render_size, width=args.render_size,
                      generator=gen).images

        for i, image in enumerate(images):
            arr = np.asarray(image.convert("RGB"))
            if arr.max() == arr.min():           # blanked frame — never save it
                logger.warning("blank frame at index %d, skipped", generated + i)
                continue
            name = f"ai_{args.prefix}{generated + i:04d}.jpg"
            realized = match_and_save(arr, os.path.join(args.out, name), stats, rng)
            records.append({"file": name, "prompt": prompts[i], **realized})
        generated += batch
        logger.info("generated %d/%d", min(generated, args.n), args.n)

    provenance = {
        "generator": "genuine diffusion output (not src/utils/synth.py stand-ins)",
        "model": args.model,
        "vae": args.vae or "(pipeline default)",
        "num_inference_steps": args.steps,
        "guidance_scale": args.guidance,
        "render_size": args.render_size,
        "seed": args.seed,
        "prompts": PROMPTS,
        "confound_matching": {
            "matched_against": args.real_dir,
            "n_real_reference_images": stats["n"],
            "resized_to": "size sampled from the real class's size distribution",
            "jpeg_quality": "chosen per image to match a sampled real blockiness",
            "quality_grid": list(QUALITY_GRID),
            "real_blockiness_mean": round(float(np.mean(stats["blockiness"])), 5),
            "real_blockiness_sd": round(float(np.std(stats["blockiness"])), 5),
            "generated_blockiness_mean": round(
                float(np.mean([r["blockiness"] for r in records])), 5),
        },
        "images": records,
    }
    with open(os.path.join(args.out, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)

    print(f"\nWrote {len(records)} genuine diffusion figures -> {args.out}")
    print("  real blockiness      mean %.4f"
          % provenance["confound_matching"]["real_blockiness_mean"])
    print("  generated blockiness mean %.4f  (matched)"
          % provenance["confound_matching"]["generated_blockiness_mean"])
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=400, help="images to generate")
    p.add_argument("--out", default="data/ai_generated_real",
                   help="output dir (kept separate from the synthetic stand-ins "
                        "in data/ai_generated_samples/)")
    p.add_argument("--real-dir", default="data/clean",
                   help="real figures whose size/compression stats are matched")
    p.add_argument("--model", default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--vae", default="madebyollin/sdxl-vae-fp16-fix",
                   help="fp16-safe VAE, so decoding is not upcast to fp32 "
                        "(pass '' to use the pipeline's own VAE)")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--guidance", type=float, default=7.0)
    p.add_argument("--render-size", type=int, default=1024,
                   help="native render resolution before confound matching")
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--prefix", default="", help="filename prefix after 'ai_'")
    p.add_argument("--no-safety-checker", action="store_true", default=True,
                   help="micrographs trip the NSFW heuristic and return black "
                        "frames, which would poison the class")
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

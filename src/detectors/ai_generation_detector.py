"""AI-generation detector (Stage 4 orchestrator).

Flags whether a scientific figure was likely produced by a generative
model (GAN/diffusion) rather than captured by a real instrument. Combines
three signals:

    1. **Frequency anomaly**  (src.forensics.frequency_analysis) — CPU,
       training-free. Spectral falloff + periodic upsampling artifacts.
    2. **Noise-residual anomaly** (src.forensics.noise_residual) — CPU,
       training-free. PRNU-style sensor-noise statistics.
    3. **Learned classifier** (src.models.artifact_classifier) — optional;
       MobileNetV3-small fine-tuned on GPU (Colab) and loaded for inference.
       ``None`` when weights are not yet available.

Signal combination (documented, since it is a judgment call)
------------------------------------------------------------
The two forensic scores are averaged into ``forensic = 0.5*freq +
0.5*noise`` (they probe independent artifacts — spectrum vs. spatial noise
— so an unweighted mean is the honest default).

* **No classifier weights:** the verdict is a pure threshold on the
  forensic score. Calibrated on the Stage 4 sample set (real forensic
  ~0.17, synthetic ~0.55): ``< 0.35`` -> ``likely_real``; ``[0.35, 0.55)``
  -> ``suspicious``; ``>= 0.55`` -> ``likely_ai_generated``. Because the
  forensics cannot confidently catch every generator, many true synthetics
  land only in ``suspicious`` here — that is the honest ceiling of the
  training-free tier, and the reason the classifier exists.

* **With classifier weights:** the learned model is the primary signal
  (it can see artifacts the hand-crafted forensics miss). We blend
  ``combined = 0.6*p_ai + 0.4*forensic`` and threshold at 0.5 /
  ``suspicious`` band 0.4-0.6. The forensics still contribute so a
  confident forensic hit isn't fully overridden by a wrong classifier and
  vice-versa. When the classifier and forensics strongly *disagree* the
  verdict is pinned to ``suspicious`` and the disagreement is surfaced in
  the explanation, rather than silently trusting either.

Every verdict is a **lead for human review**, never an accusation.

CLI usage:
    python -m src.detectors.ai_generation_detector \
        --image path/to/figure.png --output outputs/stage4_results/
"""

from __future__ import annotations

import argparse
import json
import os

from src.forensics.frequency_analysis import analyze_frequency_spectrum
from src.forensics.jpeg_quality import compression_stratum
from src.forensics.noise_residual import analyze_noise_residual
from src.models.artifact_classifier import classify_artifact, weights_available
from src.utils.image_io import load_image

# Verdict labels.
LIKELY_REAL = "likely_real"
SUSPICIOUS = "suspicious"
LIKELY_AI = "likely_ai_generated"

# Forensic-only thresholds.
#
# RECALIBRATED 2026-07-11 against the REAL Stage-7 evaluation set.
# --------------------------------------------------------------------------
# The original thresholds (0.35 / 0.55) were calibrated on the small Stage-4
# *synthetic* sample, where "real" images scored a forensic ~0.17. On genuine
# published figures that assumption is wrong: real clean PMC figures score
# forensic mean 0.357, sd 0.107 (n=83) — the old 0.35 "suspicious" line sat
# essentially AT the mean of real clean images, so ~half of them tripped it
# (measured false-positive rate 0.518). Publisher figures are JPEG-compressed
# and downsampled, which weakens their sensor-noise residual and inflates the
# forensic score for reasons unrelated to AI generation.
#
# The bands below are now set by how far a score sits ABOVE the real clean
# baseline (a z-score), the same "observed vs. expected" logic the frequency
# detector uses internally: flag `suspicious` at ~2 sd above the real mean and
# `likely_ai_generated` at ~3 sd. mean + 2*sd = 0.571; mean + 3*sd = 0.678.
#
# ⚠ OVERFITTING CAVEAT: this baseline was measured on the SAME 25 papers the
# pipeline is evaluated against — the only real data available right now. That
# makes the post-recalibration false-positive numbers OPTIMISTIC, not an
# unbiased estimate. A genuine, unbiased figure requires a fresh real paper set
# the thresholds were NOT tuned on. See README "Recalibration & overfitting".
REAL_CLEAN_FORENSIC_MEAN = 0.357
REAL_CLEAN_FORENSIC_STD = 0.107
FORENSIC_LOW = 0.57   # ~ mean + 2*sd : below this reads as a normal real figure
FORENSIC_HIGH = 0.68  # ~ mean + 3*sd : unusually far above the real baseline

# COMPRESSION-CONDITIONED baselines (preferred over the absolute bands above).
# --------------------------------------------------------------------------
# The +2σ hike above exists because publisher JPEG compression destroys the
# sensor noise and high frequencies the forensics measure — real *compressed*
# figures score high for reasons unrelated to AI generation, and one global
# threshold must either flag half of them (old behaviour, FPR 0.518) or give
# up sensitivity on uncompressed images (current behaviour). Conditioning on
# an estimated compression stratum (src.forensics.jpeg_quality) turns that
# confound into a lookup: each image is z-scored against real figures at
# SIMILAR compression, and flagged only when unusually far above *that*
# baseline (z >= 2 suspicious, z >= 3 likely-AI).
#
# ⚠ PROVISIONAL NUMBERS: high_compression mean/std are the values measured on
# the (mostly JPEG) real PMC evaluation figures; low_compression comes from
# the small Stage-4 uncompressed sample. Both must be re-measured on a fresh
# figure set (and again after any change to the forensic sub-scores).
DEFAULT_BASELINES = {
    "high_compression": {"mean": 0.357, "std": 0.107},
    "low_compression": {"mean": 0.20, "std": 0.10},
}
Z_SUSPICIOUS = 2.0
Z_LIKELY_AI = 3.0
# Classifier-blended thresholds (unchanged; only used when weights exist, which
# is not the case in the current forensic-only deployment).
COMBINED_LOW = 0.40
COMBINED_HIGH = 0.60
# |p_ai - forensic| above this counts as a strong disagreement.
DISAGREEMENT_MARGIN = 0.5


def _forensic_verdict(forensic: float,
                      low: float = FORENSIC_LOW,
                      high: float = FORENSIC_HIGH) -> str:
    if forensic < low:
        return LIKELY_REAL
    if forensic < high:
        return SUSPICIOUS
    return LIKELY_AI


def _combined_verdict(combined: float) -> str:
    if combined < COMBINED_LOW:
        return LIKELY_REAL
    if combined < COMBINED_HIGH:
        return SUSPICIOUS
    return LIKELY_AI


def detect_ai_generation(image_path: str, weights_path: str | None = None,
                         forensic_low: float = FORENSIC_LOW,
                         forensic_high: float = FORENSIC_HIGH,
                         baselines: dict | None = None) -> dict:
    """Assess whether ``image_path`` is AI-generated.

    Verdict logic (forensics-only mode): the image's estimated JPEG
    compression stratum selects a real-figure baseline from ``baselines``
    (default :data:`DEFAULT_BASELINES`); the forensic score is z-scored
    against it and flagged at z >= 2 (suspicious) / z >= 3 (likely AI).
    Passing ``baselines={}`` (empty) disables conditioning and falls back
    to the absolute ``forensic_low`` / ``forensic_high`` bands.

    Returns:
    {
        "frequency_anomaly_score": float,       # 0..1
        "noise_residual_anomaly_score": float,  # 0..1
        "classifier_score": float | None,       # p(AI); None if no weights
        "combined_verdict": str,                # likely_real/suspicious/likely_ai_generated
        "explanation": str,                     # which signals fired
        "details": {...},                       # raw forensic feature dicts
    }
    """
    freq = analyze_frequency_spectrum(image_path)
    noise = analyze_noise_residual(image_path)
    freq_score = freq["anomaly_score"]
    noise_score = noise["anomaly_score"]
    forensic = 0.5 * freq_score + 0.5 * noise_score

    # Compression conditioning: which real-figure baseline does this image
    # get compared against?
    if baselines is None:
        baselines = DEFAULT_BASELINES
    stratum, blockiness, forensic_z = None, None, None
    if baselines:
        gray = load_image(image_path, grayscale=True)
        stratum, blockiness = compression_stratum(gray)
        base = baselines.get(stratum) or baselines.get("high_compression") \
            or next(iter(baselines.values()))
        forensic_z = (forensic - float(base["mean"])) / max(float(base["std"]), 1e-6)
        # Translate the z-bands into equivalent absolute bands so the
        # downstream explanation/threshold code stays unchanged.
        forensic_low = float(base["mean"]) + Z_SUSPICIOUS * float(base["std"])
        forensic_high = float(base["mean"]) + Z_LIKELY_AI * float(base["std"])

    classifier = classify_artifact(image_path, weights_path)
    reasons: list[str] = []

    # Describe the forensic signals in words.
    if freq_score >= forensic_high:
        reasons.append(f"frequency spectrum is anomalous ({freq_score:.2f}): "
                       f"periodicity={freq['periodicity']:.2f}, "
                       f"falloff_gap={freq['high_freq_falloff']:.1f}")
    if noise_score >= forensic_high:
        reasons.append(f"noise residual is unnatural ({noise_score:.2f}): "
                       f"autocorr={noise['autocorrelation']:.2f}, "
                       f"flatness={noise['spectral_flatness']:.2f}")

    if classifier is None:
        verdict = _forensic_verdict(forensic, forensic_low, forensic_high)
        classifier_score = None
        if not reasons:
            reasons.append(f"frequency ({freq_score:.2f}) and noise "
                           f"({noise_score:.2f}) signals within natural range"
                           if verdict == LIKELY_REAL else
                           f"forensic signals mildly elevated "
                           f"(freq {freq_score:.2f}, noise {noise_score:.2f})")
        if stratum is not None:
            reasons.append(
                f"compared against the real-figure baseline for its "
                f"compression level ({stratum}, blockiness {blockiness:.2f}): "
                f"forensic z={forensic_z:+.1f}")
        reasons.append("no classifier weights loaded — verdict from forensic "
                       "signals only (train via colab notebook for stronger calls)")
    else:
        classifier_score = classifier["p_ai_generated"]
        combined = 0.6 * classifier_score + 0.4 * forensic
        disagreement = abs(classifier_score - forensic)
        if disagreement >= DISAGREEMENT_MARGIN:
            verdict = SUSPICIOUS
            reasons.append(
                f"classifier (p_ai={classifier_score:.2f}) and forensics "
                f"(score={forensic:.2f}) strongly disagree — flagged for review")
        else:
            verdict = _combined_verdict(combined)
            reasons.append(f"classifier p_ai={classifier_score:.2f} "
                           f"(val_acc={classifier.get('val_accuracy')})")

    if not reasons:
        reasons.append("no anomalous signals detected")

    return {
        "frequency_anomaly_score": round(freq_score, 4),
        "noise_residual_anomaly_score": round(noise_score, 4),
        "classifier_score": (round(classifier_score, 4)
                             if classifier_score is not None else None),
        "combined_verdict": verdict,
        "explanation": "; ".join(reasons),
        "details": {
            "forensic_score": round(forensic, 4),
            "forensic_z": (round(forensic_z, 2) if forensic_z is not None else None),
            "compression_stratum": stratum,
            "blockiness": (round(blockiness, 4) if blockiness is not None else None),
            "frequency": freq,
            "noise_residual": noise,
            "classifier_available": classifier is not None,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ScholarGuard AI-generation detector")
    parser.add_argument("--image", required=True, help="figure image to assess")
    parser.add_argument("--output", default="outputs/stage4_results",
                        help="directory for the JSON report + spectrum heatmap")
    parser.add_argument("--weights", default=None,
                        help="path to artifact_classifier.pt (optional)")
    parser.add_argument("--no-heatmap", action="store_true")
    args = parser.parse_args(argv)

    result = detect_ai_generation(args.image, weights_path=args.weights)

    os.makedirs(args.output, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.image))[0]
    if not args.no_heatmap:
        analyze_frequency_spectrum(
            args.image, heatmap_path=os.path.join(args.output, f"{stem}_spectrum.png")
        )

    report = {k: v for k, v in result.items() if k != "details"}
    report["image"] = args.image
    report["classifier_weights_present"] = weights_available(args.weights)
    report["note"] = ("Verdicts are leads for human review, not proof. "
                       "Forensic-only mode cannot catch every generator.")
    report_path = os.path.join(args.output, f"{stem}_ai_generation_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))
    print(f"\nreport saved to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Image forensics primitives for AI-generation detection (Stage 4).

Two CPU-friendly, training-free analyses:

* :mod:`frequency_analysis` — FFT spectral-falloff / periodic-peak checks.
* :mod:`noise_residual` — PRNU-style noise residual statistics.

Both expose an ``analyze_*`` function returning an anomaly score in
``[0, 1]`` (higher == more likely synthetic) plus interpretable features.
"""

"""Forgery detectors. Stage 2 provides the classical copy-move detector.

Imports are lazy so ``python -m src.detectors.copy_move_detector`` doesn't
trigger the double-import RuntimeWarning from runpy.
"""

__all__ = ["detect_copy_move", "CopyMoveDetector", "DetectorConfig"]


def __getattr__(name):
    if name in __all__:
        from src.detectors import copy_move_detector

        return getattr(copy_move_detector, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

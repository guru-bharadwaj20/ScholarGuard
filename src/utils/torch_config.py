"""One place that decides how many threads torch may use.

Why this is shared rather than inlined
--------------------------------------
``torch.set_num_threads`` is **process-global**: the last caller wins for
everything that follows. The parallel benchmark runner
(:func:`src.evaluation.benchmark_runner._run_one_paper`) relies on that,
pinning every worker process to one thread via ``SCHOLARGUARD_TORCH_THREADS``
so that N processes do not each open a pool sized to all cores and thrash.

Two modules load torch models — :mod:`src.models.artifact_classifier` and
:mod:`src.indexing.feature_extractor`. Only the first honoured the environment
variable; the second called ``set_num_threads(cpu_count - 1)`` unconditionally,
and because cross-figure builds an index for every paper it ran in every
worker. The first ``FeatureExtractor`` in each process therefore undid the
pinning for that whole process, reproducing exactly the contention the runner
documents itself as preventing.

Both now call :func:`configure_torch_threads`, so the policy cannot drift again.
"""

from __future__ import annotations

import os

#: Workers set this to "1" so N processes do not each grab every core.
THREAD_ENV_VAR = "SCHOLARGUARD_TORCH_THREADS"


def resolve_thread_count() -> int:
    """How many threads torch should use in this process.

    ``SCHOLARGUARD_TORCH_THREADS`` when it holds a positive integer, else one
    fewer than the machine's cores so a single interactive run leaves something
    for the rest of the app. Always at least 1.
    """
    raw = os.environ.get(THREAD_ENV_VAR)
    if raw and raw.strip().isdigit() and int(raw) > 0:
        return int(raw)
    return max(1, (os.cpu_count() or 2) - 1)


def configure_torch_threads() -> int:
    """Apply :func:`resolve_thread_count` to torch. Returns the value set.

    Safe to call repeatedly; torch is imported lazily so importing this module
    never pulls torch in.
    """
    import torch

    threads = resolve_thread_count()
    torch.set_num_threads(threads)
    return threads

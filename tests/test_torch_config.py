"""The shared torch thread policy.

torch.set_num_threads is process-global, so the parallel benchmark runner pins
every worker to one thread via SCHOLARGUARD_TORCH_THREADS. Both torch-loading
modules must honour it; feature_extractor previously did not, and since
cross-figure indexes every paper it undid the pinning inside every worker.
"""

import os

import pytest

from src.utils import torch_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(torch_config.THREAD_ENV_VAR, raising=False)


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv(torch_config.THREAD_ENV_VAR, "1")
    assert torch_config.resolve_thread_count() == 1


def test_falls_back_to_one_below_cpu_count():
    expected = max(1, (os.cpu_count() or 2) - 1)
    assert torch_config.resolve_thread_count() == expected


@pytest.mark.parametrize("value", ["", "0", "-4", "many", "2.5"])
def test_unusable_values_fall_back(monkeypatch, value):
    monkeypatch.setenv(torch_config.THREAD_ENV_VAR, value)
    assert torch_config.resolve_thread_count() >= 1
    if value in ("0", "-4"):
        assert torch_config.resolve_thread_count() != 0


def test_both_torch_loaders_use_the_shared_policy():
    """Neither module may call set_num_threads with its own arithmetic."""
    import inspect

    from src.indexing import feature_extractor
    from src.models import artifact_classifier

    for module in (feature_extractor, artifact_classifier):
        source = inspect.getsource(module)
        assert "configure_torch_threads()" in source
        # A direct call, not a mention in a comment.
        assert "torch.set_num_threads(" not in source, (
            f"{module.__name__} sets torch threads directly; it must go "
            f"through src.utils.torch_config so the policy cannot drift")

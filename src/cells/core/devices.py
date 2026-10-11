"""Explicit execution placement; CPU and GPU may coexist in one process."""

from functools import cache
from importlib.metadata import PackageNotFoundError, version

import jax

from cells.core.specs import ConfigError


@cache
def cuda_installed():
    for package in ("jax-cuda13-plugin", "jax-cuda12-plugin"):
        try:
            version(package)
            return True
        except PackageNotFoundError:
            pass
    return False


def execution_device(backend="cpu"):
    if backend not in ("cpu", "gpu"):
        raise ConfigError("Execution backend must be cpu or gpu")
    jax.config.update("jax_enable_x64", True)
    if not cuda_installed():
        if backend == "gpu":
            raise ConfigError("Requested gpu unavailable: CUDA plugin missing; no CPU fallback")
        # Avoid probing unsupported CUDA in CPU-only installations. A CUDA
        # installation keeps both platforms available in the same process.
        jax.config.update("jax_platforms", "cpu")
    try:
        return jax.devices(backend)[0]
    except (RuntimeError, IndexError) as exc:
        raise ConfigError(f"Requested {backend} unavailable; no CPU fallback") from exc

"""Local workspace defaults with an explicit site scratch-root override."""

import os
from pathlib import Path


def output_root():
    root = Path(os.environ.get("CELLS_OUTPUT_ROOT", "/mnt/workspaces"))
    if not root.is_absolute() or root.resolve() == Path("/"):
        raise ValueError("CELLS_OUTPUT_ROOT must be an absolute dedicated output root")
    return root.resolve()


def within_output_root(path):
    path = Path(path).resolve()
    return output_root() in path.parents


def configure_caches():
    root = output_root() / "Cells"
    for name, relative in (
        ("TMPDIR", "tmp"),
        ("XDG_CACHE_HOME", "cache"),
        ("CUDA_CACHE_PATH", "cache/cuda"),
        ("JAX_COMPILATION_CACHE_DIR", "cache/jax"),
    ):
        chosen = Path(os.environ.get(name, str(root / relative))).resolve()
        if not within_output_root(chosen):
            chosen = root / relative
        chosen.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(chosen)
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

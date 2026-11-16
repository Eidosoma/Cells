"""Cells: explicit models, reproducible experiments, independent numerics."""

__version__ = "0.16.0.dev0"

from cells.core import blas_threads as _blas_threads  # noqa: E402

_blas_threads.pin_at_import()  # D190: every BLAS at 1 thread, so bits do not follow allocation.

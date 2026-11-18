"""Cells: explicit models, reproducible experiments, independent numerics."""

from cells.core import blas_threads as _blas_threads  # noqa: E402

# D190: every BLAS at 1 thread from `import cells`, so bits do not follow the CPU allocation.
# Its one home again (D198, R6'): no held law pins this file's bytes since the retire batch, and
# every engine path imports this package before any of its modules.
_blas_threads.pin_at_import()

__version__ = "0.16.0.dev0"

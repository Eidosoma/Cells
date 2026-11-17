"""Model specifications, numerical state, and orchestration."""

from cells.core import blas_threads as _blas_threads  # noqa: E402

# D190: every BLAS at 1 thread, so bits do not follow the CPU allocation. Here, not in
# cells/__init__.py, whose bytes a held legacy law pins (legacy/processes/charged_surface_work); every
# engine path (parse, models, runs, analysis) imports cells.core before any linear algebra.
_blas_threads.pin_at_import()

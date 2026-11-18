"""Numerical failures shared by models and the execution layer."""


class NumericalError(RuntimeError):
    """Evolution failed its declared invariants; no clipping or rescue."""

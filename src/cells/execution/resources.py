"""Conservative array-working estimates shared by scalar and batch execution.

A world's estimate counts its fixed storage, its bound layout, once per resident copy, and its saved
rows once per time point (FR-43, D315). trace_bytes(spec, steps, observation_count) is one resident
copy: fixed_bytes(spec), from the model's fixed_working_size (values; a model without one holds
none), plus row_bytes(spec, steps, observation_count), from working_size or the TRACE and
OBSERVATION columns (values per saved row). A caller that holds several copies of a world
(adjacent window results, checkpoints, each with its layout) adds one trace_bytes term per copy;
the vector windows' resident rows share one layout per world, so they take row_bytes per row and
fixed_bytes once.
"""

from cells.registry.models import get_model


def fixed_bytes(spec):
    """Bytes a world holds once per resident copy, never per saved row (its bound layout)."""
    model = get_model(spec.model)
    if not hasattr(model, "fixed_working_size"):
        return 0
    return 8 * model.fixed_working_size(spec)


def trace_bytes(spec, steps, observation_count=None):
    """One resident copy of a world: its fixed storage once, and its saved rows per time point."""
    return fixed_bytes(spec) + row_bytes(spec, steps, observation_count)


def row_bytes(spec, steps, observation_count=None):
    """Bytes of a world's saved rows: steps + 1 accepted rows and its observation rows."""
    model = get_model(spec.model)
    if observation_count is None:
        observation_count = len(spec.experiment.observation_times)
    if hasattr(model, "working_size"):
        # Variable species axes must enter the estimate before capacity allocation.
        columns = model.working_size(spec)
        return 8 * (columns * (steps + 1 + observation_count) + 4 * (steps + 1))
    values = (
        (
            model.TRACE_COLUMNS * spec.execution.capacity
            + model.TRACE_EDGE_COLUMNS * spec.execution.edge_capacity
        )
        * (steps + 1)
        + (
            model.OBSERVATION_COLUMNS * spec.execution.capacity
            + model.OBSERVATION_EDGE_COLUMNS * spec.execution.edge_capacity
        )
        * observation_count
        + 4 * (steps + 1)
    )
    return values * 8

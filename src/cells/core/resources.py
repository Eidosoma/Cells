"""Conservative array-working estimates shared by scalar and batch execution."""

from cells.models.registry import get_model


def trace_bytes(spec, steps, observation_count=None):
    model = get_model(spec.model)
    if observation_count is None:
        observation_count = len(spec.experiment.observation_times)
    if hasattr(model, "working_size") or hasattr(model, "working_columns"):
        # Variable species axes must enter the estimate before capacity allocation.
        if hasattr(model, "working_size"):
            columns = model.working_size(spec)
        else:
            cells, edges, membranes = model.working_columns(spec)
            columns = (
                cells * spec.execution.capacity
                + edges * spec.execution.edge_capacity
                + membranes * spec.execution.membrane_capacity
            )
        return 8 * (columns * (steps + 1 + observation_count) + 4 * (steps + 1))
    values = (
        (
            model.TRACE_COLUMNS * spec.execution.capacity
            + model.TRACE_EDGE_COLUMNS * spec.execution.edge_capacity
            + getattr(model, "TRACE_MEMBRANE_COLUMNS", 0) * spec.execution.membrane_capacity
        )
        * (steps + 1)
        + (
            model.OBSERVATION_COLUMNS * spec.execution.capacity
            + model.OBSERVATION_EDGE_COLUMNS * spec.execution.edge_capacity
            + getattr(model, "OBSERVATION_MEMBRANE_COLUMNS", 0) * spec.execution.membrane_capacity
        )
        * observation_count
        + 4 * (steps + 1)
    )
    return values * 8

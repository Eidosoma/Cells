"""Independent rational calendar interpretation; no Cells, JAX or NumPy."""

from fractions import Fraction


def event_label(parameters, index):
    """The independent rational label, rounded once for a scalar evaluator."""
    count = parameters["step_count"]
    if not 0 <= index < count:
        raise ValueError("Reference calendar is exhausted")
    if count == 1:
        return 0.0
    return float(Fraction(index, count - 1) * count * Fraction(parameters["dt_s"]))


def evaluate(parameters):
    count = parameters["step_count"]
    dt = Fraction(parameters["dt_s"])
    stride = Fraction(parameters["sample_stride"])
    # Preserve the source floating add/subtract before truncating a sample index.
    indices = []
    index = 0
    limit = Fraction(float(Fraction(count) - stride))
    while Fraction(index) < limit:
        index = int(float(Fraction(index) + stride))
        indices.append(index)
    selected = set(indices)
    return dict(
        call_index=list(range(count)),
        event_label_s=[event_label(parameters, i) for i in range(count)],
        elapsed_start_s=[float(i * dt) for i in range(count)],
        elapsed_end_s=[float((i + 1) * dt) for i in range(count)],
        duration_s=[float(dt)] * count,
        sampled=[i in selected for i in range(count)],
        events_enabled=[parameters["phase"] == "SIM"] * count,
        source_sample_indices=indices,
        requested_duration_count=(
            None
            if parameters.get("requested_duration_s") is None
            else int(float(Fraction(parameters["requested_duration_s"]) / dt))
        ),
    )

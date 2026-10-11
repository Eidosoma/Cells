"""Exact native display-label arithmetic; physical elapsed clocks are untouched."""

import math


def labels(duration, count, *, max_count=25600):
    """Scalar float64 linspace(0, duration, count), including its forced endpoint.

    BETSE sim.py::_plot_loop calls numpy.linspace. Its pinned implementation
    divides once, then multiplies the indices, then sets the last value to stop.
    This is not the physical clock i * dt and is not (i * duration) / (count - 1).
    """
    if type(duration) is not float or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Positive finite float duration required")
    if type(max_count) is not int or not 2 <= max_count <= 512000:
        raise ValueError("Registered maximum label extent required")
    if type(count) is not int or not 2 <= count <= max_count:
        raise ValueError("Registered label extent required")
    spacing = duration / (count - 1)
    result = [i * spacing for i in range(count)]
    result[-1] = duration
    return result


class ClockLedger:
    """Narrow dependency adapter; all non-label comparisons pass through unchanged."""

    def __init__(self, ledger, duration, count, exact, *, max_count=25600):
        self.ledger, self.duration, self.count, self.exact = ledger, duration, count, exact
        self.max_count = max_count
        self.calls = 0

    def compare(self, name, actual, expected, atol, rtol=2e-11):
        if name == "raw_labels_s":
            old = [i * self.duration / (self.count - 1) for i in range(self.count)]
            if self.calls or atol != 1e-18 or rtol != 0.0:
                raise ValueError("Unexpected inherited label check")
            self.exact().match(expected, old, "Inherited label formula")
            expected = labels(self.duration, self.count, max_count=self.max_count)
            self.exact().match(actual, expected, "Exact native raw labels")
            self.calls += 1
        self.ledger.compare(name, actual, expected, atol, rtol)


def inspect(
    original, exact, row, baseline, plan, variant, ledger, *, max_count=25600, progress=None
):
    adapter = ClockLedger(ledger, plan["duration_s"], row["steps"], exact, max_count=max_count)
    options = {} if progress is None else {"progress": progress}
    result = original.inspect(row, baseline, plan, variant, adapter, **options)
    if adapter.calls != 1:
        raise ValueError("Missing native label check")
    return dict(result, exact_raw_labels=row["steps"])

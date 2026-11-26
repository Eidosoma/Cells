"""Read-only observation of already accepted numerical states."""

import numpy as np


def sample_history(times, values, requested):
    """Interpolate on the time axis without assigning meaning to trailing axes."""
    shape = (len(requested), *values.shape[1:])
    columns = int(np.prod(values.shape[1:]))
    if not len(requested) or not columns:
        return np.empty(shape, dtype=np.float64)
    flat = values.reshape((len(times), columns))
    sampled = np.stack([np.interp(requested, times, flat[:, i]) for i in range(columns)], axis=1)
    return sampled.reshape(shape)

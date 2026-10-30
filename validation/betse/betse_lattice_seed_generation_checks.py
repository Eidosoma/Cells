"""Fixed saved-seed comparison budgets; no production numerical imports."""

import numpy as np


def numeric(values):
    if hasattr(values, "_asdict"):
        values = values._asdict()
    return {
        key: np.empty(tuple(value["empty_array_shape"]), dtype=np.float64)
        if isinstance(value, dict) and set(value) == {"empty_array_shape"}
        else np.asarray(value)
        for key, value in values.items()
        if value is not None
    }


def compare(actual, wanted, *, exact=False):
    a, b = numeric(actual), numeric(wanted)
    assert a.keys() == b.keys()
    maximum = 0.0
    for key, target in b.items():
        value = a[key]
        assert value.shape == target.shape, key
        if exact or key.endswith("uniforms"):
            if exact:
                assert value.dtype == target.dtype, (key, value.dtype, target.dtype)
            np.testing.assert_array_equal(value, target, err_msg=key)
        else:
            assert np.isfinite(value).all() and np.isfinite(target).all(), key
            fraction = float(np.max(abs(value - target) / (1e-27 + 6e-12 * abs(target)), initial=0))
            assert fraction <= 1, (key, fraction)
            maximum = max(maximum, fraction)
    return maximum

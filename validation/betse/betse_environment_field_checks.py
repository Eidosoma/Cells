"""Shared saved-column comparisons; no production arithmetic or imports."""

from collections.abc import Mapping

import numpy as np


def flat(value, prefix=""):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            result.update(flat(item, prefix + ("." if prefix else "") + key))
        return result
    return {} if value is None else {prefix: np.asarray(value)}


def data_frame(row):
    return dict(
        values=row["values"],
        smoothing_hodge=row["smoothing_hodge"],
        current_hodge=row["current_hodge"],
        current=row["current"]["values"],
    )


def budget(key, target, *, gross=None, factor=None):
    if key.startswith("current."):
        return factor * gross + 1e-30
    if key.startswith("geometry."):
        if "laplacian" in key or "inverse" in key:
            return 3e-13 + 6e-12 * abs(target)
        if key.endswith(("X_m", "Y_m", "grid_points_m")):
            return 8 * np.abs(np.spacing(target))
        return 64 * np.finfo(np.float64).eps * abs(target)
    absolute = (
        1e-30
        if key.endswith(("charge_C_m2", "charge_C_m3"))
        else 3e-14
        if key.endswith("_V")
        else 3e-18
        if key.endswith("magnetic_field_source")
        else 3e-13
    )
    return absolute + 6e-12 * abs(target)


def compare(actual, expected, *, exact=False, gross=None, factor=None):
    a, b = flat(actual), flat(expected)
    assert a.keys() == b.keys(), (a.keys() - b.keys(), b.keys() - a.keys())
    maximum = 0.0
    for key, target in b.items():
        value = a[key]
        assert value.shape == target.shape, key
        if exact:
            assert value.dtype == target.dtype, (key, value.dtype, target.dtype)
            np.testing.assert_array_equal(value, target, err_msg=key)
            continue
        assert np.isfinite(value).all() and np.isfinite(target).all(), key
        if key.startswith("geometry.") and key.endswith(
            ("shape", "index_ij", "cell_to_grid", "membrane_to_grid", "membranes_per_site")
        ):
            np.testing.assert_array_equal(value, target, err_msg=key)
            continue
        allowance = budget(
            key,
            target,
            gross=None
            if gross is None or not key.startswith("current.")
            else np.asarray(gross[key.removeprefix("current.")]),
            factor=factor,
        )
        difference = abs(value - target)
        # Zero geometric entries have an exact-zero budget, avoiding 0/0.
        fraction = np.divide(
            difference, allowance, out=np.zeros_like(difference, dtype=float), where=allowance != 0
        )
        assert np.all((allowance != 0) | (difference == 0)), key
        error = float(np.max(fraction, initial=0))
        assert error <= 1, (key, error, float(np.max(difference, initial=0)))
        maximum = max(maximum, error)
    return maximum


def prefix_factor(definition):
    g, ions = definition["current_definition"]["geometry"], definition["current_definition"]["ions"]
    return 32 * np.finfo(np.float64).eps * (len(g["membrane_ids"]) + len(ions["ids"]) + 16)


def source_arrays(proof):
    result = flat(dict(geometry=proof["geometry"], cache=proof["cache"]))
    for index, row in enumerate(proof["frames"]):
        result.update(flat(data_frame(row), "frame_" + str(index)))
    return result


def saved_columns(columns, category, names):
    return {name: columns[category + "__" + name.replace(".", "__")] for name in names}

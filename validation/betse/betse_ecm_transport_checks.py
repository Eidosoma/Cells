"""Fixed predeclared saved-array budgets; no production arithmetic/imports."""

from collections.abc import Mapping

import numpy as np

from validation.betse import betse_environment_field_checks as geometry_checks

flat = geometry_checks.flat
geometry_compare = geometry_checks.compare

LEDGERS = (
    "boundary_clamp_change_mol",
    "collocated_transport_change_mol",
    "smoothing_change_mol",
    "membrane_transfer_mol",
    "native_environment_exchange_mol",
    "conservative_environment_exchange_mol",
    "fast_exchange_defect_mol",
    "gap_net_outward_mol",
    "clipping_added_mol",
    "cell_change_mol",
    "environment_change_mol",
    "cell_accounting_residual_mol",
    "environment_accounting_residual_mol",
    "membrane_bulk_difference_mol_m3",
    "source_voltage_nonce_delta_V",
)


def get(value, key):
    return value[key] if isinstance(value, Mapping) else getattr(value, key)


def metadata(row):
    return [(get(frame, "stage"), get(frame, "ion_id")) for frame in get(row, "frames")]


def columns(row, *, ledgers=True):
    result = {}
    for index, frame in enumerate(get(row, "frames")):
        result.update(flat(get(frame, "values"), "frame_" + str(index)))
    for index, record in enumerate(get(row, "environment_records")):
        values = record if isinstance(record, Mapping) else record._asdict()
        result.update(
            flat(
                {key: value for key, value in values.items() if key != "ion_id"},
                "environment_" + str(index),
            )
        )
    candidate = get(row, "candidate")
    result.update(
        flat(candidate if isinstance(candidate, Mapping) else candidate.values, "candidate")
    )
    if ledgers:
        measurements = row["ledgers"] if isinstance(row, Mapping) else row.diagnostics
        result.update(flat({key: measurements[key] for key in LEDGERS}, "ledger"))
    return result


def budget(key, wanted):
    leaf = key.rsplit(".", 1)[-1]
    absolute = (
        3e-14
        if leaf.endswith("_mol")
        else 1e-40
        if leaf.endswith("_V")
        else 1e-18
        if "flux" in leaf
        else 1e-28
        if "junction_field" in leaf
        else 3e-20
        if "diffusion" in leaf
        else 3e-14
        if leaf in ("alpha", "gap_open")
        else 3e-13
    )
    return absolute + 6e-12 * abs(wanted)


def compare(actual, expected, *, exact=False):
    assert actual.keys() == expected.keys(), (
        actual.keys() - expected.keys(),
        expected.keys() - actual.keys(),
    )
    maximum = 0.0
    for key, raw in expected.items():
        value, wanted = np.asarray(actual[key]), np.asarray(raw)
        assert value.shape == wanted.shape, key
        if exact:
            assert value.dtype == wanted.dtype, (key, value.dtype, wanted.dtype)
            np.testing.assert_array_equal(value, wanted, err_msg=key)
            continue
        assert np.isfinite(value).all() and np.isfinite(wanted).all(), key
        error = float(np.max(abs(value - wanted) / budget(key, wanted), initial=0))
        assert error <= 1, (key, error, float(np.max(abs(value - wanted), initial=0)))
        maximum = max(maximum, error)
    return maximum


def saved(columns, category, names):
    return {key: columns[category + "__" + key.replace(".", "__")] for key in names}

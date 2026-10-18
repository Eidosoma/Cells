"""Independent temporal separation and unchanged feature-budget checks."""

import copy

import numpy as np
import pytest

from validation.assays import source_order_long_diagnostic as diagnostic


def example():
    rule = diagnostic.precision.protocol()
    rows = [r for r in diagnostic.assay.cases(rule) if r["arm"] == "joint"]
    maps = {}
    for panel, _ in diagnostic.SPANNING:
        values = {}
        for row in rows:
            # Late order effects lie exactly along the strength direction.
            # An earlier strength-only observation separates these quantities.
            order = 0 if panel == "middle128" else 0.2 * row["timing"]
            point = np.array([100 * row["amplitude"] + order, 10 * row["location"], 0, 0, 0])
            values[row["world_id"]] = np.tile(point, 3)
        maps[0, panel] = {"voltage": values}
    return rows, maps, rule


def test_independent_time_point_separates_known_strength_order_ambiguity():
    rows, maps, rule = example()
    old = diagnostic.reader.evaluate(rows, maps[0, "long512"]["voltage"], margin=0.006)
    assert old["arms"]["joint"]["tasks"]["timing"]["metrics"]["resolved_fraction"] == 0
    before = copy.deepcopy(maps)
    features = diagnostic.spanning_features(rows, maps, 0, rule)
    new = diagnostic.reader.evaluate(rows, features, margin=0.006)
    assert new["feature_count"] == old["feature_count"] == 15
    assert new["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    assert (
        new["arms"]["joint"]["calibration"]["world_ids"]
        == old["arms"]["joint"]["calibration"]["world_ids"]
    )
    for key, modes in maps.items():
        for identity, value in modes["voltage"].items():
            np.testing.assert_array_equal(value, before[key]["voltage"][identity])


def test_time_and_cell_identity_survive_without_scaling_or_metadata_leakage():
    rows, maps, rule = example()
    for panel, _ in diagnostic.SPANNING:
        times = rule["observation_times_us"][panel]
        for values in maps[0, panel]["voltage"].values():
            values[:] = [t * 100 + cell for t in times for cell in (2, 3, 5, 6, 7)]
    identities = [{"world_id": r["world_id"]} for r in reversed(rows)]
    features = diagnostic.spanning_features(identities, maps, 0, rule)
    expected = [t * 100 + cell for t in (128, 256, 512) for cell in (2, 3, 5, 6, 7)]
    for value in features.values():
        np.testing.assert_array_equal(value, expected)


@pytest.mark.parametrize("corruption", ["source_cells", "time", "width", "nonfinite"])
def test_changed_observation_support_is_rejected(corruption):
    rows, maps, rule = example()
    identity = rows[0]["world_id"]
    if corruption == "source_cells":
        rule["readout"]["cell_ids"][0] = 1
    elif corruption == "time":
        rule["observation_times_us"]["middle128"][-1] = 112
    elif corruption == "width":
        maps[0, "long256"]["voltage"][identity] = np.zeros(21)
    else:
        maps[0, "long512"]["voltage"][identity][0] = np.nan
    with pytest.raises(ValueError):
        diagnostic.spanning_features(rows, maps, 0, rule)

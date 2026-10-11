"""Topology, labels and population extent are data, independent of frozen assays."""

import copy
from dataclasses import replace

import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from tests.finite_extracellular_fixtures import definition, load_cases


def small(name):
    case = next(c for c in load_cases()[1] if c.id == name)
    return replace(case, horizon_s=0.002, controls=(case.controls[0],))


def test_species_labels_and_physical_ids_are_not_kernel_selectors():
    raw = definition(small("star_mono"))
    renamed = {"Na": "cation_A", "K": "cation_B", "Cl": "anion_C"}
    objects = [raw["model"]["extracellular"], *raw["model"]["junctions"]]
    for c in raw["model"]["cells"]:
        objects += [c["cell"], c["membrane"]]
        if c["channel"] is not None:
            objects.append(c["channel"])
        if c["membrane"]["pump"] is not None:
            objects.append(c["membrane"]["pump"])
    renamed.update({o["id"]: "renamed_" + o["id"] for o in objects})

    def rename(value):
        if isinstance(value, dict):
            return {renamed.get(k, k): rename(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rename(v) for v in value]
        return renamed.get(value, value) if isinstance(value, str) else value

    a, b = run(parse_spec(raw)), run(parse_spec(rename(raw)))
    for actual, expected in zip(a.history, b.history, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_species_axis_permutation_preserves_physics():
    raw = definition(small("star_mono"))
    a = run(parse_spec(raw))
    order = [2, 0, 1]
    raw["model"]["species"] = [raw["model"]["species"][i] for i in order]
    b = run(parse_spec(raw))
    for field in a.history._fields:
        actual, expected = getattr(b.history, field), getattr(a.history, field)
        if field in (
            "amount_increment",
            "leak_transferred",
            "junction_transferred",
            "extracellular_amount_increment",
        ):
            expected = expected[:, order]
        np.testing.assert_allclose(actual, expected, atol=1e-14, rtol=1e-12)
    np.testing.assert_allclose(
        b.observations.voltage_V, a.observations.voltage_V, atol=1e-14, rtol=1e-12
    )


@pytest.mark.parametrize("count", [1, 5])
def test_population_extent_and_extensive_outside_scale_are_data(count):
    raw = definition(small("single_mono"))
    baseline = run(parse_spec(raw))
    cell, channel_control, membrane_control = (
        copy.deepcopy(raw["model"]["cells"][0]),
        copy.deepcopy(raw["experiment"]["channel_controls"][0]),
        copy.deepcopy(raw["experiment"]["membrane_controls"][0]),
    )
    raw["model"]["cells"] = []
    raw["experiment"]["channel_controls"] = []
    raw["experiment"]["membrane_controls"] = []
    for i in range(count):
        c = copy.deepcopy(cell)
        c["cell"]["id"] = f"c{i}"
        c["membrane"].update(id=f"m{i}", inside=f"c{i}")
        c["membrane"]["pump"]["id"] = f"p{i}"
        c["channel"].update(id=f"k{i}", membrane_id=f"m{i}")
        raw["model"]["cells"].append(c)
        raw["experiment"]["channel_controls"].append(channel_control | {"channel_id": f"k{i}"})
        raw["experiment"]["membrane_controls"].append(membrane_control | {"membrane_id": f"m{i}"})
    outside = raw["model"]["extracellular"]
    outside["volume_pL"] *= count
    outside["fixed_charge_equivalent_fmol"] *= count
    outside["initial_amount_fmol"] = {
        s: n * count for s, n in outside["initial_amount_fmol"].items()
    }
    raw["execution"].update(
        capacity=count + 2, membrane_capacity=count + 3, channel_capacity=count + 1
    )
    result = run(parse_spec(raw))
    for i in range(count):
        np.testing.assert_allclose(
            result.history.amount_increment[..., i],
            baseline.history.amount_increment[..., 0],
            atol=1e-14,
            rtol=1e-12,
        )
    np.testing.assert_allclose(
        result.history.extracellular_amount_increment / count,
        baseline.history.extracellular_amount_increment,
        atol=1e-14,
        rtol=1e-12,
    )


@pytest.mark.parametrize("field", ["volume", "charge_sum"])
def test_derived_extreme_arithmetic_is_a_configuration_refusal(field):
    raw = definition(small("single_mono"))
    outside = raw["model"]["extracellular"]
    if field == "volume":
        outside["volume_pL"] = 5e-324
    else:
        outside["initial_amount_fmol"] = {"Na": 1e308, "K": 1e308, "Cl": 1e308}
    with pytest.raises(ConfigError):
        parse_spec(raw)

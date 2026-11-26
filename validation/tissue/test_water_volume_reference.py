"""Analytic and thermodynamic checks of the independent water reference."""

import sys
from copy import deepcopy

import numpy as np
import pytest

from validation.tissue import water_volume_reference as ref
from validation.tissue.water_volume_reference import case


def test_decimal_gradient_and_closed_water_energy_identity():
    raw = case()
    raw["bulk_modulus_Pa"] = [12345.0, 23456.0]
    raw["pressure_offset_Pa"] = [150.0, -70.0]
    volume = np.asarray([1.1, 2.9])
    before = deepcopy(raw)
    actual = ref.evaluate(raw, volume)
    assert raw == before
    assert actual["edge_flow_pL_s"][0] < 0  # Higher intracellular osmolarity draws water in.
    assert actual["volume_rate_pL_s"][0] > 0
    assert actual["volume_balance_pL_s"] == 0
    assert abs(actual["energy_balance_pJ_s"]) < 1e-65
    assert actual["free_energy_rate_pJ_s"] < 0
    for node in (0, 1):
        offset = np.eye(2)[node] * 2e-5
        gradient = (
            ref.evaluate(raw, volume + offset)["free_energy_pJ"]
            - ref.evaluate(raw, volume - offset)["free_energy_pJ"]
        ) / (4e-5)
        np.testing.assert_allclose(
            gradient, 1e-3 * actual["water_potential_Pa"][node], rtol=2e-9, atol=1e-8
        )


def test_zero_pressure_osmotic_equilibrium_has_analytic_volume_partition():
    raw = case()
    expected = np.asarray([4 / 3, 8 / 3])  # 300:600 osmoles divide the closed 4-pL volume.
    actual = ref.two_compartment_equilibrium(raw)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=3e-14)
    assert abs(ref.evaluate(raw, actual)["edge_flow_pL_s"][0]) < 3e-14
    shifted = deepcopy(raw)
    shifted["pressure_offset_Pa"] = [100000.0, 100000.0]
    np.testing.assert_allclose(ref.two_compartment_equilibrium(shifted), actual, rtol=0, atol=1e-14)
    np.testing.assert_array_equal(
        ref.evaluate(raw)["edge_flow_pL_s"], ref.evaluate(shifted)["edge_flow_pL_s"]
    )


@pytest.mark.parametrize("initial", [[1.0, 3.0], [1.8, 2.2]])
def test_swelling_and_shrinking_conserve_material_and_decay_free_energy(initial):
    raw = case()
    raw["initial_volume_pL"] = initial
    times = np.linspace(0, 40, 81)
    result = ref.integrate(raw, times)
    volume = result["volume_pL"]
    np.testing.assert_allclose(volume.sum(axis=1), 4.0, rtol=0, atol=3e-14)
    expected = np.broadcast_to(np.asarray(raw["amount_fmol"]), (len(times), 2, 2))
    np.testing.assert_allclose(
        result["concentration_mM"] * volume[:, None, :], expected, rtol=2e-16, atol=2e-14
    )
    transfer = result["edge_transferred_pL"][:, 0]
    np.testing.assert_allclose(volume[:, 0], initial[0] - transfer, rtol=0, atol=3e-14)
    np.testing.assert_allclose(volume[:, 1], initial[1] + transfer, rtol=0, atol=3e-14)
    assert np.all(np.diff(volume[:, 0]) * (4 / 3 - initial[0]) >= -2e-14)
    np.testing.assert_allclose(volume[-1], ref.two_compartment_equilibrium(raw), atol=3e-10, rtol=0)
    energy = result["free_energy_pJ"]
    assert np.max(np.diff(energy)) < 4e-12
    assert np.min(result["edge_dissipated_energy_pJ"]) >= 0
    np.testing.assert_allclose(
        energy - energy[0] + result["edge_dissipated_energy_pJ"].sum(axis=1),
        0,
        rtol=0,
        atol=3e-9,
    )


def test_pure_water_matches_exact_elastic_pair_and_tighter_reference():
    raw = case()
    raw.update(
        amount_fmol=[[0.0, 0.0]],
        impermeant_amount_fmol=[0.0, 0.0],
        initial_volume_pL=[1.3, 2.7],
        bulk_modulus_Pa=[1200.0, 500.0],
        pressure_offset_Pa=[25.0, -15.0],
    )
    raw["edges"][0]["hydraulic_permeability_m_per_Pa_s"] = 1e-9
    times = np.linspace(0, 12, 25)
    exact = ref.exact_mechanical_pair(raw, times)
    result, tight = (ref.integrate(raw, times, refinement=r) for r in (1, 4))
    np.testing.assert_allclose(result["volume_pL"], exact, rtol=2e-12, atol=3e-13)
    np.testing.assert_allclose(tight["volume_pL"], exact, rtol=4e-13, atol=8e-14)
    np.testing.assert_allclose(result["volume_pL"], tight["volume_pL"], rtol=2e-12, atol=3e-13)
    assert ref.evaluate(raw)["mixing_energy_pJ"] == 0
    np.testing.assert_allclose(
        result["free_energy_pJ"]
        - result["free_energy_pJ"][0]
        + result["edge_dissipated_energy_pJ"].sum(axis=1),
        0,
        atol=2e-12,
        rtol=0,
    )


def test_edge_reversal_and_interface_subdivision_preserve_physics():
    raw = case()
    reversed_case, split = deepcopy(raw), deepcopy(raw)
    reversed_case["edges"][0].update(sender=1, receiver=0)
    split["edges"] *= 2
    split["edges"] = [dict(e, area_m2=e["area_m2"] / 2) for e in split["edges"]]
    times = np.linspace(0, 5, 21)
    base = ref.integrate(raw, times)
    for modified, sign in ((reversed_case, -1), (split, 1)):
        result = ref.integrate(modified, times)
        np.testing.assert_allclose(result["volume_pL"], base["volume_pL"], rtol=2e-12, atol=3e-13)
        for field, coefficient in (("edge_transferred_pL", sign), ("edge_dissipated_energy_pJ", 1)):
            np.testing.assert_allclose(
                result[field].sum(axis=1),
                coefficient * base[field].sum(axis=1),
                rtol=3e-12,
                atol=3e-12,
            )


def test_sealed_membrane_and_disconnected_node_remain_unchanged():
    raw = case()
    raw["edges"][0]["hydraulic_permeability_m_per_Pa_s"] = 0
    result = ref.integrate(raw, [0, 1, 2])
    np.testing.assert_array_equal(result["volume_pL"], [raw["initial_volume_pL"]] * 3)
    assert np.all(result["edge_transferred_pL"] == 0)
    assert np.all(result["edge_dissipated_energy_pJ"] == 0)
    raw = case()
    raw["initial_volume_pL"].append(2.0)
    raw["reference_volume_pL"].append(2.0)
    raw["impermeant_amount_fmol"].append(37.0)
    raw["bulk_modulus_Pa"].append(100.0)
    raw["pressure_offset_Pa"].append(-77.0)
    for row in raw["amount_fmol"]:
        row.append(25.0)
    result = ref.integrate(raw, [0, 1, 2])
    np.testing.assert_array_equal(result["volume_pL"][:, 2], [2.0, 2.0, 2.0])
    np.testing.assert_allclose(result["volume_pL"][:, :2].sum(axis=1), 4, atol=3e-14, rtol=0)


@pytest.mark.parametrize(
    "fault",
    [
        "zero_volume",
        "negative_amount",
        "negative_modulus",
        "negative_conductance",
        "self_edge",
        "nan",
    ],
)
def test_invalid_domain_rejects_without_clipping(fault):
    raw = case()
    if fault == "zero_volume":
        raw["initial_volume_pL"][0] = 0
    elif fault == "negative_amount":
        raw["amount_fmol"][0][0] = -1
    elif fault == "negative_modulus":
        raw["bulk_modulus_Pa"][0] = -1
    elif fault == "negative_conductance":
        raw["edges"][0]["hydraulic_permeability_m_per_Pa_s"] = -1
    elif fault == "self_edge":
        raw["edges"][0]["receiver"] = 0
    else:
        raw["impermeant_amount_fmol"][0] = float("nan")
    with pytest.raises(ValueError):
        ref.evaluate(raw)


def test_the_reference_imports_no_production_code():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)

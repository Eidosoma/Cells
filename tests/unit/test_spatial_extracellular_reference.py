"""Instantaneous spatial design checks; no trajectory or production claims."""

import copy
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from tests import reference_multispecies as ion
from tests import reference_spatial_extracellular as ref

ROOT = Path(__file__).resolve().parents[2]
PANEL = json.loads((ROOT / "configs/reference/spatial_extracellular_v1.json").read_text())
CASES = PANEL["cases"]
IDS = [c["id"] for c in CASES]


def case(name="binary_unequal"):
    return copy.deepcopy(next(c for c in CASES if c["id"] == name))


def near(actual, expected, atol=1e-12):
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=atol)


@pytest.mark.parametrize("raw", CASES, ids=IDS)
def test_owned_material_charge_and_power(raw):
    g = ref.resolve(raw)
    r = ref.evaluate(g)
    rate = r["amount_rate_fmol_per_s"]
    near(np.sum(rate, axis=0), 0)
    near(g.p.T @ r["charge_C"], 0, 1e-20)
    near(g.p.T @ r["charge_rate_A"], 0, 1e-23)
    near(r["capacitor_residual_C"], 0, 1e-20)
    near(r["component_current_residual_A"], 0, 1e-23)
    near(r["stored_energy_rate_W"], -r["dissipation_W"], 1e-23)
    assert r["dissipation_W"] >= -1e-23
    # Literal endpoints are an independent check on both incidence signs/owners.
    literal = np.zeros_like(rate)
    for pairs, flux in (
        (g.membrane_pairs, r["membrane_flux_fmol_per_s"]),
        (g.face_pairs, r["face_flux_fmol_per_s"]),
    ):
        for (u, v), values in zip(pairs, flux, strict=True):
            literal[u] -= values
            literal[v] += values
    near(rate, literal)


@pytest.mark.parametrize("raw", CASES, ids=IDS)
def test_one_gauge_changes_no_physics(raw):
    g = ref.resolve(raw)
    original = ref.evaluate(g)
    shifted = ref.evaluate(g, gauge_id=g.ids[0], gauge_voltage=0.137)
    near(
        shifted["potential_V"] - original["potential_V"], 0.137 - original["potential_V"][0], 1e-10
    )
    for key in (
        "membrane_voltage_V",
        "amount_rate_fmol_per_s",
        "face_flux_fmol_per_s",
        "membrane_flux_fmol_per_s",
    ):
        near(original[key], shifted[key])
    near(original["dissipation_W"], shifted["dissipation_W"], 1e-23)


@pytest.mark.parametrize("raw", CASES, ids=IDS)
def test_species_order_is_data(raw):
    changed = copy.deepcopy(raw)
    for key in ("species_ids", "valence"):
        changed[key].reverse()
    for owner in changed["compartments"]:
        owner["initial_amount_fmol"].reverse()
    for owner in changed["membranes"]:
        owner["permeability_m_per_s"].reverse()
    for owner in changed["faces"]:
        owner["diffusivity_m2_per_s"].reverse()
    original, permuted = ref.evaluate(ref.resolve(raw)), ref.evaluate(ref.resolve(changed))
    near(original["potential_V"], permuted["potential_V"], 1e-10)
    near(original["amount_rate_fmol_per_s"], permuted["amount_rate_fmol_per_s"][:, ::-1])


@pytest.mark.parametrize("raw", CASES, ids=IDS)
def test_compartment_order_and_labels_are_not_physics(raw):
    changed = copy.deepcopy(raw)
    names = {c["id"]: "renamed_" + str(i) for i, c in enumerate(raw["compartments"])}
    for c in changed["compartments"]:
        c["id"] = names[c["id"]]
    changed["compartments"].reverse()
    for m in changed["membranes"]:
        m["inside"], m["outside"] = names[m["inside"]], names[m["outside"]]
    for f in changed["faces"]:
        f["left"], f["right"] = names[f["left"]], names[f["right"]]
    g = ref.resolve(raw)
    original = ref.evaluate(g)
    permuted = ref.evaluate(ref.resolve(changed), gauge_id=names[g.ids[-1]])
    near(original["potential_V"], permuted["potential_V"][::-1], 1e-10)
    near(original["amount_rate_fmol_per_s"], permuted["amount_rate_fmol_per_s"][::-1])


@pytest.mark.parametrize(
    "raw", [c for c in CASES if c["faces"]], ids=[c["id"] for c in CASES if c["faces"]]
)
def test_face_orientation_is_bookkeeping(raw):
    changed = copy.deepcopy(raw)
    for f in changed["faces"]:
        f["left"], f["right"] = f["right"], f["left"]
    original, flipped = ref.evaluate(ref.resolve(raw)), ref.evaluate(ref.resolve(changed))
    near(original["potential_V"], flipped["potential_V"], 1e-10)
    near(original["face_flux_fmol_per_s"], -flipped["face_flux_fmol_per_s"])
    near(original["amount_rate_fmol_per_s"], flipped["amount_rate_fmol_per_s"])


@pytest.mark.parametrize("name", ["binary_unequal", "binary_equal", "pure_bulk"])
def test_binary_salt_against_closed_form(name):
    raw = case(name)
    g = ref.resolve(raw)
    r = ref.evaluate(g)
    u, v = g.face_pairs[0]
    cu, cv = g.initial[[u, v], 0] / g.volume[[u, v]]
    f = raw["faces"][0]
    dp, dm = f["diffusivity_m2_per_s"]
    voltage = -ref.R * g.temperature / ref.F * (dp - dm) / (dp + dm) * math.log(cu / cv)
    salt = f["area_m2"] / (ref.A * f["length_m"]) * 2 * dp * dm / (dp + dm) * (cu - cv)
    near(r["potential_V"][u] - r["potential_V"][v], voltage, 1e-10)
    near(r["face_flux_fmol_per_s"][0], [salt, salt])
    near(r["face_current_A"], 0, 1e-23)
    if dp != dm:
        assert abs(voltage) > 1e-3
        # Explicit wrong-closure witness; this is not used to evolve state.
        zero_voltage_current = ref.F * f["area_m2"] / f["length_m"] * (dp - dm) * (cu - cv)
        assert abs(zero_voltage_current) > 1e-12


def test_single_outside_reduces_to_existing_charge_anchor_and_passive_law():
    raw = case("single_outside")
    g = ref.resolve(raw)
    r = ref.evaluate(g)
    m = raw["membranes"][0]
    assert len(g.groups) == 1 and not g.face_pairs
    near(r["membrane_voltage_V"], m["initial_voltage_V"], 1e-10)
    ci, co = g.initial / g.volume[:, None]
    expected = [
        -ion.passive_flux(
            int(z), float(i), float(o), m["initial_voltage_V"], g.temperature, m["area_m2"], p
        )
        for z, i, o, p in zip(g.z, ci, co, m["permeability_m_per_s"], strict=True)
    ]
    near(r["membrane_flux_fmol_per_s"][0], expected)
    assert r["charge_C"][0] != 0  # Do not erase membrane-associated charge.


def test_uniform_outside_has_exactly_zero_bulk_flux():
    r = ref.evaluate(ref.resolve(case("uniform_outside")))
    np.testing.assert_array_equal(r["face_flux_fmol_per_s"], 0)


def test_loop_requires_node_balance_not_zero_current_on_every_face():
    r = ref.evaluate(ref.resolve(case("ternary_loop")))
    near(r["component_current_residual_A"], 0, 1e-23)
    assert np.max(np.abs(r["face_current_A"])) > 1e-18
    near(r["face_current_A"], r["face_current_A"][0], 1e-23)


def test_bulk_node_needs_no_fictitious_capacitance():
    g = ref.resolve(case("pure_bulk"))
    r = ref.evaluate(g)
    assert not g.membrane_pairs
    np.testing.assert_array_equal(g.lc, 0)
    np.testing.assert_array_equal(r["charge_C"], 0)
    assert np.max(np.abs(r["potential_V"])) > 1e-3


def test_blocked_membrane_does_not_block_outside_transport():
    g = ref.resolve(case())
    r = ref.evaluate(g, membrane_availability=0)
    np.testing.assert_array_equal(r["membrane_flux_fmol_per_s"], 0)
    np.testing.assert_array_equal(r["amount_rate_fmol_per_s"][0], 0)
    assert np.max(np.abs(r["face_flux_fmol_per_s"])) > 1
    all_off = ref.evaluate(ref.resolve(case("uniform_outside")), membrane_availability=0)
    np.testing.assert_array_equal(all_off["amount_rate_fmol_per_s"], 0)


def test_explicit_finite_increments_keep_anchors_and_change_feedback():
    g = ref.resolve(case())
    delta = np.zeros_like(g.initial)
    delta[0, 0], delta[1, 0] = 1e-6, -1e-6  # One conservative membrane transfer.
    delta[1] -= 1e-3
    delta[2] += 1e-3  # Neutral salt transfer, both outside inventories explicit.
    r = ref.evaluate(g, delta)
    near(r["membrane_voltage_V"][0], -0.065 + ref.A * ref.F * 1e-6 / 1e-11, 1e-10)
    near(r["stored_energy_rate_W"], -r["dissipation_W"], 1e-23)
    np.testing.assert_array_equal(r["amount_fmol"], g.initial + delta)
    assert not np.array_equal(r["face_flux_fmol_per_s"], ref.evaluate(g)["face_flux_fmol_per_s"])
    assert not g.initial.flags.writeable


def test_global_neutrality_does_not_fix_component_incompatibility():
    g = ref.resolve(case())
    delta = np.zeros_like(g.initial)
    delta[1, 0], delta[2, 0] = -0.01, 0.01
    assert np.sum(delta @ g.z) == 0
    with pytest.raises(ValueError, match="capacitance components"):
        ref.evaluate(g, delta)


@pytest.mark.parametrize(
    "left,right",
    [
        (1.0, 1.0),
        (120.0, math.nextafter(120.0, math.inf)),
        (120.0, 120.000001),
        (1e-12, 1e6),
        (120.0, 60.0),
    ],
)
def test_log_mean_against_high_precision(left, right):
    value, log_ratio = ref.log_mean(left, right)
    with localcontext() as ctx:
        ctx.prec = 70
        a, b = Decimal(left), Decimal(right)
        logs = a.ln() - b.ln()
        wanted = a if a == b else (a - b) / logs
    near(value, float(wanted), 1e-26)
    near(log_ratio, float(logs), 1e-26)
    near(value * log_ratio, left - right)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "1"])
def test_invalid_concentration_has_no_floor(value):
    with pytest.raises((ValueError, TypeError)):
        ref.log_mean(value, 1.0)


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("faces", "area_m2", 0),
        ("faces", "length_m", -1),
        ("faces", "diffusivity_m2_per_s", [0, 0]),
        ("faces", "diffusivity_m2_per_s", [-1, 1]),
        ("faces", "diffusivity_m2_per_s", [float("nan"), 1]),
        ("faces", "left", "cell"),
        ("faces", "right", "missing"),
        ("faces", "right", "near"),
        ("membranes", "capacitance_F", 0),
        ("membranes", "outside", "cell"),
        ("compartments", "volume_pL", 0),
        ("compartments", "initial_amount_fmol", [0, 10]),
        ("compartments", "fixed_charge_equivalent_fmol", 0),
    ],
)
def test_invalid_geometry_or_initial_charge_is_refused(target, key, value):
    raw = case()
    raw[target][0][key] = value
    with pytest.raises((ValueError, TypeError)):
        ref.resolve(raw)


@pytest.mark.parametrize("mutation", ["disconnected", "duplicate", "unknown", "two_membranes"])
def test_unsupported_topologies_are_not_silently_repaired(mutation):
    raw = case()
    if mutation == "disconnected":
        raw["faces"] = []
    elif mutation == "duplicate":
        raw["faces"].append(dict(raw["faces"][0], id="duplicate"))
    elif mutation == "unknown":
        raw["electrode_current"] = 1
    else:
        raw["membranes"].append(dict(raw["membranes"][0], id="extra"))
    with pytest.raises(ValueError):
        ref.resolve(raw)


@pytest.mark.parametrize(
    "delta",
    [np.zeros((2, 2)), np.full((3, 2), np.nan), np.full((3, 2), np.inf), np.full((3, 2), -1000)],
)
def test_invalid_state_is_refused(delta):
    with pytest.raises(ValueError):
        ref.evaluate(ref.resolve(case()), delta)


@pytest.mark.parametrize("factor", [0.1, 2.0, 10.0])
def test_bulk_geometry_scaling_does_not_change_diffusion_potential(factor):
    raw = case()
    original = ref.evaluate(ref.resolve(raw))
    raw["faces"][0]["area_m2"] *= factor
    scaled = ref.evaluate(ref.resolve(raw))
    near(original["potential_V"], scaled["potential_V"], 1e-10)
    near(original["face_flux_fmol_per_s"] * factor, scaled["face_flux_fmol_per_s"])


def test_volume_and_amount_are_separate_owners():
    raw = case()
    original = ref.evaluate(ref.resolve(raw))
    for owner in raw["compartments"]:
        owner["volume_pL"] *= 2
        owner["initial_amount_fmol"] = [2 * n for n in owner["initial_amount_fmol"]]
    doubled = ref.evaluate(ref.resolve(raw))
    near(original["amount_fmol"] * 2, doubled["amount_fmol"])
    near(original["potential_V"], doubled["potential_V"], 1e-10)
    near(original["amount_rate_fmol_per_s"], doubled["amount_rate_fmol_per_s"])

"""Independent shared-catalog wiring checks; no long clocks or production imports."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.channels import leak_channels_reference as leaks
from validation.channels import potassium_catalog_reference as potassium
from validation.channels import sodium_catalog_reference as sodium
from validation.tissue import surface_kinetic_reference as ref
from validation.tissue.test_water_kinetic_reference import case as water_case

LAWS = tuple(ref.CATALOG_PERMEABILITIES)
ADDED = (*ref.ADDED_SODIUM_LAWS, *ref.ADDED_POTASSIUM_LAWS, *ref.ADDED_LEAK_LAWS)
FIXTURE_ARMS = ("open", "blocked", "release", "reordered")
FROZEN_INPUTS = pytest.mark.skipif(
    "CELLS_CATALOG_FIXTURE_INPUTS" not in os.environ,
    reason="Coordinator fixture checks require separately serialized, hashed raw JSON inputs",
)


def coordinator_case(arm):
    # The legacy fixture builder imports production field helpers. Read only its
    # serialized inputs so no production implementation enters this worker.
    return json.loads(
        (Path(os.environ["CELLS_CATALOG_FIXTURE_INPUTS"]) / f"{arm}.json").read_text()
    )


def evidence(name, value):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def case(laws=LAWS, *, multiple=False):
    """Reference-local finite compartments; route metadata is explicit raw input."""
    raw = water_case(multiple=multiple)
    m, e = raw["model"], raw["experiment"]
    m["id"] = ref.CATALOG_MODEL
    m.pop("water_compartments")
    m.pop("water_membranes")
    e.pop("water_controls")
    m["channels"] = [
        dict(
            id=f"catalog_{j}",
            membrane_id=m["membranes"][j % len(m["membranes"])]["id"],
            kinetic_law=law,
            permeant_ions=[
                dict(species_id=species, relative_permeability=weight)
                for species, weight in ref.CATALOG_PERMEABILITIES[law]
            ],
            max_permeability_m_per_s=3e-10,
            abundance=0.5 + 0.01 * j,
            initial_gate=[0.2 + 0.01 * j, 0.7 - 0.01 * j],
        )
        for j, law in enumerate(laws)
    ]
    e["channel_controls"] = [
        dict(
            channel_id=channel["id"],
            schedule=[dict(time=0.0, availability=0.6), dict(time=7.1e-6, availability=0.0)],
        )
        for channel in m["channels"]
    ]
    raw["execution"]["channel_capacity"] = len(m["channels"])
    return raw


def state(c, changed):
    d = ref.unpack(c, ref.initial(c))
    if changed:
        species = [v["id"] for v in c["raw"]["model"]["species"]]
        # Neutral salt plus a small conservative charge displacement; both
        # concentrations and membrane voltage change without an external source.
        for name, amount in (("K", 0.02), ("Cl", 0.02), ("Na", 1e-5)):
            s = species.index(name)
            d["amount_increment"][s, 0] += amount
            d["extracellular_amount_increment"][s, 0] -= amount
        d["channel_gate"][:] = np.array([[0.31], [0.63]])
    return ref.flatten(c, d)


def physical_balance(c, y, slope, phi):
    fields, rate = ref.unpack(c, y), ref.unpack(c, slope)
    ci = (c["ai"] + fields["amount_increment"]) / c["vi"]
    co = (c["ao"] + fields["extracellular_amount_increment"]) / c["vo"]
    z = np.asarray(c["layout"]["valence"])
    n = len(c["vi"])
    # dEcap = sum(phi*dq); all gate state is phenomenological, without an
    # independently declared gate-energy store. Maintained ATP work is external.
    mu_in = ref.R * 298.15 * np.log(ci) + ref.F * z * phi[:n]
    mu_out = ref.R * 298.15 * np.log(co) + ref.F * z * phi[n:]
    free = 1e-3 * (
        np.sum(mu_in * rate["amount_increment"])
        + np.sum(mu_out * rate["extracellular_amount_increment"])
    )
    heat = sum(v.sum() for k, v in rate.items() if k.endswith("dissipated_energy_pJ"))
    supply = sum(
        rate[k].sum() for k in ("metabolic_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    material = (
        rate["amount_increment"].sum(axis=1)
        + rate["extracellular_amount_increment"].sum(axis=1)
        - rate["reservoir_supplied"].sum(axis=1)
    )
    return dict(
        material_residual_fmol_s=material.tolist(),
        physical_energy_residual_pJ_s=float(free + heat - supply),
    )


def expected_gates(law, voltage, gates):
    if law == "betse_kv1p5_mh@1":
        target, tau = ref.channel_kinetics(float(voltage))
        opened = np.prod(gates)
    elif law == "betse_kir2p1_mh2@1":
        target, tau = ref.kir_reference.kinetics(float(voltage))
        opened = float(ref.kir_reference.opening(gates))
    elif law == "betse_nav1p2_m3h_regularized@1":
        target, tau = ref.sodium_reference.kinetics(float(voltage))
        opened = float(ref.sodium_reference.opening(gates))
    elif law.startswith("betse_hcn"):
        target, tau = ref.hcn_reference.kinetics(float(voltage), int(law[9]))
        opened = float(ref.hcn_reference.opening(gates))
    elif law in ref.kv1_reference.LAWS:
        family = ref.kv1_reference.LAWS[law]
        target, tau = ref.kv1_reference.kinetics(float(voltage), family)
        opened = float(ref.kv1_reference.opening(gates, family))
    elif law in ref.cav_reference.LAWS:
        family = ref.cav_reference.LAWS[law]
        target, tau = ref.cav_reference.kinetics(float(voltage), family)
        opened = float(ref.cav_reference.opening(gates, family))
    else:
        oracle, family = next(
            (oracle, mapping[law])
            for oracle, mapping in (
                (sodium, ref.ADDED_SODIUM_LAWS),
                (potassium, ref.ADDED_POTASSIUM_LAWS),
                (leaks, ref.ADDED_LEAK_LAWS),
            )
            if law in mapping
        )
        values = oracle.kinetics(float(voltage), family)
        target, tau = values["target"], values["tau_s"]
        opened = oracle.opening(gates, family)
    return (np.asarray(target, dtype=float) - gates) / np.asarray(tau, dtype=float), opened


@pytest.mark.parametrize("law", LAWS)
@pytest.mark.parametrize("changed", [False, True])
def test_each_law_keeps_species_population_routes_and_full_physical_balance(law, changed):
    assert len(LAWS) == 35 and len(ADDED) == 17
    raw = case((law,))
    c = ref.bind(raw)
    y = state(c, changed)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    d, rate = ref.unpack(c, y), ref.unpack(c, slope)
    assert len(c["shapes"]) == 19
    assert c["shapes"]["channel_transferred"] == (4, 1)
    assert c["shapes"]["channel_dissipated_energy_pJ"] == (4, 1)
    ch = raw["model"]["channels"][0]
    gate_rate, opened = expected_gates(law, phi[0] - phi[1], d["channel_gate"][:, 0])
    np.testing.assert_allclose(rate["channel_gate"][:, 0], gate_rate, rtol=3e-15, atol=1e-12)
    expected = np.zeros(4)
    species = [v["id"] for v in raw["model"]["species"]]
    ci, co = (
        (c["ai"] + d["amount_increment"])[:, 0] / c["vi"][0],
        (c["ao"] + d["extracellular_amount_increment"])[:, 0] / c["vo"][0],
    )
    for route in ch["permeant_ions"]:
        s = species.index(route["species_id"])
        expected[s] = ref.transport.decimal_flux(
            ci[s],
            co[s],
            phi[0] - phi[1],
            c["layout"]["valence"][s][0],
            298.15,
            raw["model"]["membranes"][0]["area_m2"],
            ch["max_permeability_m_per_s"] * ch["abundance"] * route["relative_permeability"],
            1.0,
            0.6 * opened,
            {"F": ref.F, "R": ref.R},
        )
    np.testing.assert_array_equal(rate["channel_transferred"][:, 0], expected)
    delta_mu = ref.R * 298.15 * np.log(ci / co) + ref.F * np.asarray(c["layout"]["valence"])[
        :, 0
    ] * (phi[0] - phi[1])
    np.testing.assert_allclose(
        rate["channel_dissipated_energy_pJ"][:, 0],
        1e-3 * expected * delta_mu,
        rtol=3e-14,
        atol=1e-16,
    )
    assert np.all(rate["channel_dissipated_energy_pJ"] >= 0)
    # Independent channel removal makes the owned material scatter observable.
    bare = deepcopy(raw)
    bare["model"]["channels"], bare["experiment"]["channel_controls"] = [], []
    b = ref.bind(bare)
    before = ref.unpack(b, ref.evaluate(b, ref.flatten(b, d), 0)[0])
    np.testing.assert_allclose(
        rate["amount_increment"] - before["amount_increment"],
        -expected[:, None],
        rtol=3e-13,
        atol=3e-16,
    )
    np.testing.assert_allclose(
        rate["extracellular_amount_increment"] - before["extracellular_amount_increment"],
        expected[:, None],
        rtol=3e-13,
        atol=3e-16,
    )
    balances = physical_balance(c, y, slope, phi)
    np.testing.assert_allclose(balances["material_residual_fmol_s"], 0, rtol=0, atol=3e-14)
    assert abs(balances["physical_energy_residual_pJ_s"]) < 3e-12
    evidence(
        f"law-{LAWS.index(law)}-{changed}",
        dict(
            inputs=raw,
            state=y.tolist(),
            slope=slope.tolist(),
            potential_V=phi.tolist(),
            field_proof=proof,
            balances=balances,
        ),
    )


@pytest.mark.parametrize("changed", [False, True])
def test_all_populations_share_multiple_owners_with_one_control_per_population(changed):
    raw = case(multiple=True)
    c = ref.bind(raw)
    y = state(c, changed)
    slope, phi, proof = ref.evaluate(c, y, 0)
    d = ref.unpack(c, slope)
    blocked, blocked_phi, _ = ref.evaluate(c, y, 7.1e-6)
    b = ref.unpack(c, blocked)
    np.testing.assert_array_equal(phi, blocked_phi)
    np.testing.assert_array_equal(d["channel_gate"], b["channel_gate"])
    assert np.any(b["channel_gate"] != 0)
    assert not np.any(b["channel_transferred"])
    assert not np.any(b["channel_dissipated_energy_pJ"])
    expected = np.zeros((4, len(c["vi"]) + len(c["vo"])))
    patches = {row["id"]: row for row in raw["model"]["membranes"]}
    owners = [row["id"] for row in (*raw["model"]["cells"], *raw["model"]["extracellular"])]
    for j, channel in enumerate(raw["model"]["channels"]):
        patch = patches[channel["membrane_id"]]
        expected[:, owners.index(patch["inside"])] -= d["channel_transferred"][:, j]
        expected[:, owners.index(patch["outside"])] += d["channel_transferred"][:, j]
    np.testing.assert_allclose(
        np.c_[
            d["amount_increment"] - b["amount_increment"],
            d["extracellular_amount_increment"] - b["extracellular_amount_increment"],
        ],
        expected,
        rtol=3e-13,
        atol=3e-15,
    )
    balances = physical_balance(c, y, slope, phi)
    np.testing.assert_allclose(balances["material_residual_fmol_s"], 0, rtol=0, atol=3e-14)
    assert abs(balances["physical_energy_residual_pJ_s"]) < 2e-11
    evidence(
        f"shared-multi-owner-{changed}",
        dict(
            inputs=raw,
            state=y.tolist(),
            slope=slope.tolist(),
            potential_V=phi.tolist(),
            field_proof=proof,
            balances=balances,
        ),
    )


def test_leak_route_metadata_retains_zero_calcium_and_auxiliary_clock():
    raw = case(tuple(ref.ADDED_LEAK_LAWS))
    c = ref.bind(raw)
    y = ref.initial(c)
    d = ref.unpack(c, ref.evaluate(c, y, 0)[0])
    assert raw["model"]["channels"][1]["permeant_ions"] == [
        dict(species_id="Na", relative_permeability=1),
        dict(species_id="K", relative_permeability=1),
        dict(species_id="Ca", relative_permeability=0),
    ]
    assert d["channel_transferred"][3, 1] == d["channel_dissipated_energy_pJ"][3, 1] == 0
    assert d["channel_transferred"][3, 2] != 0
    assert d["channel_transferred"][2, 0] != 0  # Cl uses its actual -1 valence.
    np.testing.assert_array_equal(d["channel_gate"], 1 - ref.unpack(c, y)["channel_gate"])
    shifted = ref.unpack(c, y.copy())
    shifted["channel_gate"][:] = 0
    after = ref.unpack(c, ref.evaluate(c, ref.flatten(c, shifted), 0)[0])
    np.testing.assert_array_equal(after["channel_transferred"], d["channel_transferred"])
    np.testing.assert_array_equal(after["channel_gate"], 1)


def test_original_eighteen_laws_retain_exact_previous_branch_results():
    raw = case(tuple(law for law in LAWS if law not in ADDED), multiple=True)
    c = ref.bind(raw)
    y = state(c, True)
    expanded = ref.evaluate(c, y, 0)
    raw["model"]["id"] = "resolved_tissue@7"
    prior = ref.evaluate(ref.bind(raw), y, 0)
    for actual, expected in zip(expanded[:2], prior[:2], strict=True):
        np.testing.assert_array_equal(actual, expected)
    assert expanded[2] == prior[2]


@FROZEN_INPUTS
@pytest.mark.parametrize("arm", FIXTURE_ARMS)
@pytest.mark.parametrize("changed", [False, True])
def test_coordinator_multi_owner_fixture_and_distinct_event_controls(arm, changed):
    raw = coordinator_case(arm)
    assert {row["kinetic_law"] for row in raw["model"]["channels"]} == set(LAWS)
    c = ref.bind(raw)
    assert c["shapes"]["channel_gate"] == (2, 39)
    assert c["shapes"]["channel_transferred"] == (4, 39)
    y = state(c, changed)
    times = (0.0, 0.0005, 0.000525, 0.001, 0.001025) if arm == "release" else (0.0,)
    proofs = []
    for time in times:
        slope, phi, field = ref.evaluate(c, y, time)
        values = ref.unpack(c, slope)
        balance = physical_balance(c, y, slope, phi)
        np.testing.assert_allclose(balance["material_residual_fmol_s"], 0, rtol=0, atol=3e-13)
        assert abs(balance["physical_energy_residual_pJ_s"]) < 3e-11
        for j, channel in enumerate(raw["model"]["channels"]):
            if ref.availability(c, "channel", channel["id"], time) == 0:
                assert not np.any(values["channel_transferred"][:, j])
                assert not np.any(values["channel_dissipated_energy_pJ"][:, j])
        proofs.append(dict(time=time, field=field, balances=balance))
    evidence(f"fixture-{arm}-{changed}", dict(inputs=raw, state=y.tolist(), proofs=proofs))


@FROZEN_INPUTS
def test_species_and_population_reordering_preserves_owned_rates():
    raw, reordered = (coordinator_case(arm) for arm in ("open", "reordered"))
    a, b = ref.bind(raw), ref.bind(reordered)
    sa, pa, _ = ref.evaluate(a, state(a, True), 0)
    sb, pb, _ = ref.evaluate(b, state(b, True), 0)
    da, db = ref.unpack(a, sa), ref.unpack(b, sb)
    np.testing.assert_allclose(pa, pb, rtol=3e-13, atol=3e-14)
    for name in (
        "amount_increment",
        "extracellular_amount_increment",
        "membrane_transferred",
        "junction_transferred",
        "face_transferred",
        "reservoir_supplied",
    ):
        np.testing.assert_allclose(da[name], db[name][::-1], rtol=3e-13, atol=3e-14, err_msg=name)
    for name in ("channel_transferred", "channel_dissipated_energy_pJ"):
        np.testing.assert_allclose(
            da[name], db[name][::-1, ::-1], rtol=3e-13, atol=3e-14, err_msg=name
        )
    np.testing.assert_allclose(
        da["channel_gate"], db["channel_gate"][:, ::-1], rtol=3e-13, atol=3e-11
    )


@pytest.mark.parametrize(
    "fault",
    [
        "law",
        "temperature",
        "missing_zero_ca",
        "route_order",
        "valence",
        "duplicate",
        "negative_permeability",
        "gate",
        "control_missing",
        "control_range",
    ],
)
def test_catalog_declaration_guards(fault):
    raw = case(("betse_catleak_na_k@1",))
    m, e = raw["model"], raw["experiment"]
    ch = m["channels"][0]
    if fault == "law":
        ch["kinetic_law"] = "unknown"
    elif fault == "temperature":
        m["temperature_K"] = 310
    elif fault == "missing_zero_ca":
        ch["permeant_ions"].pop()
    elif fault == "route_order":
        ch["permeant_ions"].reverse()
    elif fault == "valence":
        m["species"][0]["valence"] = -1
    elif fault == "duplicate":
        m["channels"].append(deepcopy(ch))
    elif fault == "negative_permeability":
        ch["max_permeability_m_per_s"] = -1
    elif fault == "gate":
        ch["initial_gate"][1] = 1.01
    elif fault == "control_missing":
        e["channel_controls"] = []
    elif fault == "control_range":
        e["channel_controls"][0]["schedule"][0]["availability"] = 1.01
    with pytest.raises(ValueError):
        ref.bind(raw)


@pytest.mark.parametrize(
    "fault", ["unused_gate", "negative_gate", "nonfinite", "exhausted_ion", "voltage", "levels"]
)
def test_blocking_never_bypasses_the_active_state_domain(fault):
    raw = case(("betse_catleak_na_k@1",))
    if fault == "voltage":
        capacitance = raw["model"]["membranes"][0]["capacitance_F"]
        raw["model"]["cells"][0]["initial_charge_C"] = -0.121 * capacitance
        raw["model"]["extracellular"][0]["initial_charge_C"] = 0.121 * capacitance
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    if fault == "unused_gate":
        d["channel_gate"][1, 0] = 1.01
    elif fault == "negative_gate":
        d["channel_gate"][0, 0] = -1e-3
    elif fault == "nonfinite":
        d["channel_gate"][0, 0] = np.nan
    elif fault == "exhausted_ion":
        d["amount_increment"][3, 0] = -c["ai"][3, 0]
    with pytest.raises(ValueError):
        ref.evaluate(
            c, ref.flatten(c, d), 7.1e-6, channel_levels=[1.1] if fault == "levels" else None
        )


def test_reference_does_not_import_production_or_jax():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)

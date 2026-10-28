"""Independent active-water balances, controls and adaptive refinement checks."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue import surface_water_kinetic_reference as ref
from validation.tissue import water_volume_reference as water


def evidence(name, value):
    if location := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        path = Path(location)
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def case(*, multiple=False):
    """Synthetic raw inputs; no production fixture, parser or model imports."""
    species = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}

    def owner(name, volume, concentration):
        return dict(
            id=name,
            volume_pL=volume,
            initial_amount_fmol={
                k: v * volume for k, v in zip(species, concentration, strict=True)
            },
            initial_charge_C=0.0,
            fixed_charge_equivalent_fmol=0.0,
        )

    cells = [owner("cell_0", 2.0, [12.0, 140.0, 10.0, 0.0001])]
    outside = [owner("outside_0", 4.0, [145.0, 4.0, 120.0, 2.0])]
    routes = [(0, 0, 4e-10, True)]
    if multiple:
        cells.append(owner("cell_1", 1.5, [15.0, 130.0, 12.0, 0.0002]))
        outside.append(owner("outside_1", 3.0, [140.0, 4.5, 125.0, 1.8]))
        routes.extend([(0, 1, 2e-10, False), (1, 1, 4e-10, True), (0, 0, 1e-10, False)])
    for v in outside:
        v.update(reservoir=False, boundary_potential_V=0.0)
    membranes = []
    for j, (i, o, area, pumping) in enumerate(routes):
        pump = None
        if pumping:
            pump = dict(
                id=f"pump_{j}",
                law="nak_atp_mass_action_positive@1",
                roles=dict(sodium="Na", potassium="K"),
                stoichiometry=dict(Na=-3, K=2),
                capacity_fmol_per_s=0.02,
                km_na_mM=12.0,
                km_k_mM=0.2,
                km_atp_mM=0.5,
                metabolism=dict(
                    kind="maintained_chemical_reservoirs@1",
                    atp_mM=1.5,
                    adp_mM=0.1,
                    pi_mM=0.1,
                    delta_g0_J_per_mol=-37000.0,
                ),
            )
        membranes.append(
            dict(
                id=f"membrane_{j}",
                inside=cells[i]["id"],
                outside=outside[o]["id"],
                area_m2=area,
                capacitance_F=area * 0.01,
                permeability_m_per_s=dict(Na=1e-9, K=2e-9, Cl=8e-10, Ca=2e-11),
                law="constant_field@1",
                pump=pump,
            )
        )
    channels = [
        dict(
            id=name,
            membrane_id="membrane_0",
            permeant_ions=[dict(species_id=k, relative_permeability=v) for k, v in ions.items()],
            kinetic_law=law,
            max_permeability_m_per_s=3e-10,
            abundance=1.0,
            initial_gate=gate,
        )
        for name, law, ions, gate in (
            ("kv", "betse_kv1p5_mh@1", {"K": 1.0}, [0.2, 0.7]),
            ("hcn", "betse_hcn4_m@1", {"Na": 0.2, "K": 1.0}, [0.3, 1.0]),
            ("cav", "betse_cav1p2_m2h@1", {"Ca": 1.0}, [0.1, 0.8]),
        )
    ]
    owners = [*cells, *outside]
    owner_ids = [v["id"] for v in owners]
    potentials = [-0.04, -0.03, 0.0, 0.002] if multiple else [-0.04, 0.0]
    for patch in membranes:
        i, o = (owner_ids.index(patch[k]) for k in ("inside", "outside"))
        charge = patch["capacitance_F"] * (potentials[i] - potentials[o])
        owners[i]["initial_charge_C"] += charge
        owners[o]["initial_charge_C"] -= charge
    for v in owners:
        v["fixed_charge_equivalent_fmol"] = v["initial_charge_C"] / (1e-15 * ref.F) - sum(
            species[k] * amount for k, amount in v["initial_amount_fmol"].items()
        )
    model = dict(
        id="resolved_water@2",
        temperature_K=298.15,
        species=[dict(id=k, valence=v) for k, v in species.items()],
        cells=cells,
        extracellular=outside,
        membranes=membranes,
        channels=channels,
        junctions=[],
        faces=[],
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1", gauge_reference="outside_0"
        ),
        water_compartments=[
            dict(
                compartment_id=v["id"],
                reference_volume_pL=v["volume_pL"] + 0.1,
                minimum_volume_pL=v["volume_pL"] * 0.5,
                maximum_volume_pL=v["volume_pL"] * 1.5,
                impermeant_amount_fmol=300.0 if v in cells else 0.0,
                bulk_modulus_Pa=5e5,
                pressure_offset_Pa=1000.0 if v in cells else -500.0,
            )
            for v in owners
        ],
        water_membranes=[
            dict(membrane_id=v["id"], hydraulic_permeability_m_per_Pa_s=1e-10) for v in membranes
        ],
    )
    if multiple:
        model["junctions"] = [
            dict(
                id="junction_0",
                sender="cell_0",
                receiver="cell_1",
                area_m2=1e-11,
                permeability_m_per_s={k: 1e-9 for k in species},
                law="constant_field@1",
                gate=dict(
                    law="betse_rate_junction_relaxation@1",
                    threshold_voltage_V=0.015,
                    minimum_open_fraction=0.1,
                    initial_gate=0.6,
                ),
            )
        ]
        model["faces"] = [
            dict(
                id="face_0",
                sender="outside_0",
                receiver="outside_1",
                area_m2=1e-10,
                length_m=1e-5,
                diffusivity_m2_per_s={k: 1e-14 for k in species},
                law="logmean_electrodiffusion@1",
            )
        ]
    experiment = dict(
        end_time=50e-6,
        observation_times=[0.0, 7.9e-6, 13.3e-6, 17.1e-6, 23.7e-6, 31.1e-6, 39.1e-6, 50e-6],
    )
    times = dict(membrane=7.9e-6, junction=17.1e-6, channel=31.1e-6, pump=23.7e-6, water=13.3e-6)
    for kind, rows in (
        ("membrane", membranes),
        ("junction", model["junctions"]),
        ("channel", channels),
        ("pump", [v["pump"] for v in membranes if v["pump"] is not None]),
        ("water", membranes),
    ):
        experiment[kind + "_controls"] = [
            {
                ("membrane_id" if kind == "water" else kind + "_id"): v["id"],
                "schedule": [
                    dict(time=0.0, availability=1.0),
                    dict(time=times[kind], availability=0.0),
                    *([dict(time=39.1e-6, availability=0.8)] if kind == "water" else []),
                ],
            }
            for v in rows
        ]
    return dict(
        schema_version=1,
        model=model,
        experiment=experiment,
        execution=dict(
            dt=1.25e-6,
            capacity=len(cells),
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            channel_capacity=len(channels),
            edge_capacity=len(model["junctions"]),
            face_capacity=len(model["faces"]),
            backend="cpu",
            jit=False,
            precision="float64",
            solver="rk4",
            field_solver="capacitive_reduction_gauged_damped_newton@1",
            max_steps=128,
            max_trace_bytes=2**26,
            material_balance_atol_fmol={k: 2e-11 for k in species},
        ),
    )


def test_current_volumes_feed_all_ionic_routes_without_context_mutation():
    raw = case()
    c = ref.bind(raw)
    assert len(c["shapes"]) == 23 and len(c["ionic"]["shapes"]) == 19
    fields = ref.unpack(c, ref.initial(c))
    fields["volume_increment_pL"][0] = 0.1
    fields["extracellular_volume_increment_pL"][0] = -0.1
    slope, phi, proof = ref.evaluate(c, ref.flatten(c, fields), 0.0)
    current = dict(c["ionic"], vi=c["vi"] + 0.1, vo=c["vo"] - 0.1)
    expected, wanted_phi, _ = ionic.evaluate(current, ionic.flatten(c["ionic"], fields), 0.0)
    actual = ref.unpack(c, slope)
    np.testing.assert_array_equal(ref.flatten(c["ionic"], actual), expected)
    np.testing.assert_array_equal(phi, wanted_phi)
    np.testing.assert_array_equal(c["ionic"]["vi"], [2.0])
    np.testing.assert_array_equal(c["ionic"]["vo"], [4.0])
    old = ionic.unpack(c["ionic"], ionic.evaluate(c["ionic"], ionic.initial(c["ionic"]), 0)[0])
    for name in ("membrane_transferred", "channel_transferred", "pump_cycles"):
        assert np.max(np.abs(actual[name] - old[name])) > 1e-8
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    evidence("current-volume-stage", dict(inputs=raw, proof=proof))


def test_canonical_atp_drive_is_counted_once_and_not_an_osmolyte_pool():
    raw = case()
    c = ref.bind(raw)
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0)
    fields = ref.unpack(c, slope)
    meta = raw["model"]["membranes"][0]["pump"]["metabolism"]
    delta_g = meta["delta_g0_J_per_mol"] + ref.R * raw["model"]["temperature_K"] * np.log(
        meta["adp_mM"] * meta["pi_mM"] / (1000 * meta["atp_mM"])
    )
    np.testing.assert_allclose(
        fields["metabolic_work_pJ"], -1e-3 * fields["pump_cycles"] * delta_g, rtol=2e-15
    )
    assert proof["maintained_metabolic_power_pJ_s"] > 0.1
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    alternative = deepcopy(raw)
    alternative["model"]["membranes"][0]["pump"]["metabolism"]["atp_mM"] *= 2
    other = ref.bind(alternative)
    changed = ref.unpack(other, ref.evaluate(other, ref.initial(other), 0)[0])
    np.testing.assert_array_equal(fields["water_transferred_pL"], changed["water_transferred_pL"])
    assert np.any(fields["pump_cycles"] != changed["pump_cycles"])
    evidence("canonical-atp-drive", dict(chemical_drive_J_mol=float(delta_g), proof=proof))


@pytest.mark.parametrize("kind", ref.CONTROL_KINDS)
def test_all_control_clocks_are_right_continuous_and_independent(kind):
    c = ref.bind(case(multiple=kind == "junction"))
    event = c["raw"]["experiment"][kind + "_controls"][0]["schedule"][1]["time"]
    state = ref.initial(c)
    before = ref.unpack(c, ref.evaluate(c, state, np.nextafter(event, 0))[0])
    after = ref.unpack(c, ref.evaluate(c, state, event)[0])
    name = {
        "membrane": "membrane_transferred",
        "junction": "junction_transferred",
        "channel": "channel_transferred",
        "pump": "pump_cycles",
        "water": "water_transferred_pL",
    }[kind]
    assert np.any(before[name]) and np.all(after[name] == 0)
    if kind == "water":
        for name in c["ionic"]["shapes"]:
            np.testing.assert_array_equal(before[name], after[name])
    else:
        for name in ref.WATER_FIELDS:
            np.testing.assert_array_equal(before[name], after[name])
    np.testing.assert_array_equal(before["channel_gate"], after["channel_gate"])
    np.testing.assert_array_equal(before["junction_gate"], after["junction_gate"])


def test_sealed_water_reduces_exactly_to_original_nineteen_field_reference():
    raw = case()
    for row in raw["model"]["water_membranes"]:
        row["hydraulic_permeability_m_per_Pa_s"] = 0
    c = ref.bind(raw)
    slope, phi, _ = ref.evaluate(c, ref.initial(c), 0)
    expected, wanted_phi, _ = ionic.evaluate(c["ionic"], ionic.initial(c["ionic"]), 0)
    fields = ref.unpack(c, slope)
    np.testing.assert_array_equal(ref.flatten(c["ionic"], fields), expected)
    np.testing.assert_array_equal(phi, wanted_phi)
    for name in ref.WATER_FIELDS:
        assert np.all(fields[name] == 0)


def test_absent_channels_and_pumps_have_empty_or_zero_ledgers():
    raw = case()
    raw["model"]["channels"] = []
    raw["model"]["membranes"][0]["pump"] = None
    raw["experiment"]["channel_controls"] = []
    raw["experiment"]["pump_controls"] = []
    c = ref.bind(raw)
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0)
    fields = ref.unpack(c, slope)
    assert fields["channel_gate"].shape == (2, 0)
    assert fields["channel_transferred"].shape == (4, 0)
    for name in ("pump_cycles", "pump_dissipated_energy_pJ", "metabolic_work_pJ"):
        assert np.all(fields[name] == 0)
    assert proof["maintained_metabolic_power_pJ_s"] == 0
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10


def test_production_example_raw_inputs_are_supported_without_production_imports():
    raw = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/resolved_water_kinetic_tissue.json"
        ).read_text()
    )
    c = ref.bind(raw)
    events = sorted(
        {
            row["time"]
            for kind in ref.CONTROL_KINDS
            for group in raw["experiment"][kind + "_controls"]
            for row in group["schedule"]
        }
    )
    proofs = [ref.evaluate(c, ref.initial(c), t)[2] for t in events]
    assert len(c["shapes"]) == 23
    assert max(abs(p["physical_energy_balance_pJ_s"]) for p in proofs) < 2e-10
    evidence("production-example-stages", dict(inputs=raw, times=events, proofs=proofs))


def test_closed_shared_owners_preserve_local_material_volume_and_energy():
    raw = case(multiple=True)
    c = ref.bind(raw)
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0)
    fields = ref.unpack(c, slope)
    m = raw["model"]
    owners = [v["id"] for v in (*m["cells"], *m["extracellular"])]
    ids = [v["id"] for v in m["species"]]
    material = np.zeros((len(ids), len(owners)))
    volumes = np.zeros(len(owners))

    def move(a, b, flux):
        material[:, owners.index(a)] -= flux
        material[:, owners.index(b)] += flux

    for j, route in enumerate(m["membranes"]):
        move(route["inside"], route["outside"], fields["membrane_transferred"][:, j])
        volumes[owners.index(route["inside"])] -= fields["water_transferred_pL"][j]
        volumes[owners.index(route["outside"])] += fields["water_transferred_pL"][j]
        if route["pump"] is not None:
            flux = np.zeros(len(ids))
            flux[ids.index("Na")] = 3 * fields["pump_cycles"][j]
            flux[ids.index("K")] = -2 * fields["pump_cycles"][j]
            move(route["inside"], route["outside"], flux)
    for j, channel in enumerate(m["channels"]):
        route = next(v for v in m["membranes"] if v["id"] == channel["membrane_id"])
        move(route["inside"], route["outside"], fields["channel_transferred"][:, j])
    for kind in ("junction", "face"):
        for j, route in enumerate(m[kind + "s"]):
            move(route["sender"], route["receiver"], fields[kind + "_transferred"][:, j])
    np.testing.assert_allclose(
        np.c_[fields["amount_increment"], fields["extracellular_amount_increment"]],
        material,
        rtol=2e-15,
        atol=2e-17,
    )
    np.testing.assert_allclose(
        np.r_[fields["volume_increment_pL"], fields["extracellular_volume_increment_pL"]],
        volumes,
        rtol=2e-15,
        atol=2e-15,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    for name, value in fields.items():
        if name.endswith("dissipated_energy_pJ"):
            assert np.min(value, initial=0) >= 0
    assert np.all(fields["reservoir_supplied"] == 0)
    assert np.all(fields["electrode_charge_transferred_C"] == 0)
    evidence("closed-shared-owners", dict(inputs=raw, proof=proof))


@pytest.mark.parametrize("fault", ["reservoir", "finite_atp", "temperature", "volume", "zero_ion"])
def test_invalid_scope_or_stage_fails_without_repair(fault):
    raw = case()
    if fault == "reservoir":
        raw["model"]["extracellular"][0]["reservoir"] = True
    elif fault == "finite_atp":
        raw["model"]["membranes"][0]["pump"]["metabolism"]["kind"] = "finite_pool"
    elif fault == "temperature":
        raw["model"]["temperature_K"] = 310.0
    if fault in ("reservoir", "finite_atp", "temperature"):
        with pytest.raises(ValueError):
            ref.bind(raw)
        return
    c = ref.bind(raw)
    fields = ref.unpack(c, ref.initial(c))
    if fault == "volume":
        fields["volume_increment_pL"][0] = c["minimum_volume_pL"][0] - c["vi"][0]
    else:
        fields["amount_increment"][0, 0] = -c["ai"][0, 0]
    with pytest.raises(ValueError):
        ref.evaluate(c, ref.flatten(c, fields), 0)


def test_full_adaptive_history_refines_and_closes_energy_with_metabolic_work():
    raw = case()
    c = ref.bind(raw)
    coarse, tight = (ref.integrate(raw, refinement=r) for r in (1, 4))
    assert tight["max_step_s"] == coarse["max_step_s"] / 4
    assert tight["evaluations"] > coarse["evaluations"]
    a, b = (ref.unpack(c, value["state"]) for value in (coarse, tight))
    for name in a:
        np.testing.assert_allclose(
            a[name],
            b[name],
            rtol=3e-9,
            atol=3e-28 if name.endswith("_C") else 3e-13,
            err_msg=name,
        )
    np.testing.assert_allclose(
        a["amount_increment"].sum(axis=-1) + a["extracellular_amount_increment"].sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        a["volume_increment_pL"].sum(axis=-1) + a["extracellular_volume_increment_pL"].sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    start, stop = (coarse["times"].index(t) for t in (13.3e-6, 39.1e-6))
    for name in ref.WATER_FIELDS:
        np.testing.assert_array_equal(a[name][start], a[name][stop])
    assert abs(a["volume_increment_pL"][-1, 0]) > 1e-5
    assert abs(a["pump_cycles"][-1, 0]) > 1e-8
    assert np.max(np.abs(a["channel_gate"][-1] - a["channel_gate"][0])) > 1e-5
    energy, balances = [], []
    for i, phi in enumerate(coarse["potential_V"]):
        volume = np.r_[
            c["vi"] + a["volume_increment_pL"][i],
            c["vo"] + a["extracellular_volume_increment_pL"][i],
        ]
        amount = np.c_[
            c["ai"] + a["amount_increment"][i], c["ao"] + a["extracellular_amount_increment"][i]
        ]
        energy.append(
            water.evaluate(c["water_case"], volume, amount)["free_energy_pJ"]
            + 0.5e12 * raw["model"]["membranes"][0]["capacitance_F"] * (phi[0] - phi[1]) ** 2
        )
        balances.append(
            ref.evaluate(c, coarse["state"][i], coarse["times"][i])[2][
                "physical_energy_balance_pJ_s"
            ]
        )
    dissipated = sum(
        value.sum(axis=tuple(range(1, value.ndim)))
        for name, value in a.items()
        if name.endswith("dissipated_energy_pJ")
    )
    residual = np.asarray(energy) - energy[0] + dissipated - a["metabolic_work_pJ"].sum(axis=-1)
    np.testing.assert_allclose(residual, 0, rtol=0, atol=3e-9)
    assert np.max(np.abs(balances)) < 2e-10
    assert set(coarse["event_times"]) == {0.0, 7.9e-6, 13.3e-6, 23.7e-6, 31.1e-6, 39.1e-6, 50e-6}
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)
    evidence(
        "adaptive-history",
        dict(
            inputs=raw,
            times=coarse["times"],
            state=coarse["state"].tolist(),
            potential_V=coarse["potential_V"].tolist(),
            refined_state=tight["state"].tolist(),
            evaluations=[coarse["evaluations"], tight["evaluations"]],
            energy_balance_pJ=residual.tolist(),
            physical_energy_balance_pJ_s=balances,
            production_imports=False,
        ),
    )

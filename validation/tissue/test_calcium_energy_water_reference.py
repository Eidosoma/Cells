"""Independent joint finite-pool/chemical cytosol/water scientific contracts."""

import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import calcium_energy_water_reference as ref
from validation.tissue import surface_calcium_energy_reference as parent
from validation.tissue.test_calcium_energy_reference import ownership_checks

pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_ENERGY_WATER_INPUTS" not in os.environ,
    reason="Require frozen raw serialized joint calcium/finite-energy/water inputs",
)


def inputs():
    root = os.environ.get("CELLS_CALCIUM_ENERGY_WATER_INPUTS")
    if not root:
        return {}
    result = {}
    for path in sorted(Path(root).glob("*.json")):
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and raw.get("model", {}).get("id") == ref.MODEL_ID:
            result[path.stem] = raw
    return result


def case():
    values = inputs()
    return deepcopy(next(raw for name, raw in values.items() if "open" in name))


def evidence(name, value):
    if destination := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def test_smoke_public_43field_reference_api():
    raw = case()
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    assert len(c["shapes"]) == 43
    assert np.isfinite(slope).all() and np.isfinite(phi).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    evidence(
        "smoke",
        dict(
            inputs=raw,
            state=y.tolist(),
            derivative=slope.tolist(),
            potential_V=phi.tolist(),
            proof=proof,
        ),
    )


def changed(c):
    d = ref.unpack(c, ref.initial(c))
    for i, store in enumerate(c["stores"]):
        extent = 0.1 * float(c["energy_initial"][:, i].min())
        d["energy_amount_increment_fmol"][:, i] = extent * np.array([-1, 1, 1])
        d["chemical_amount_increment"][
            i, [store.ids.index(k) for k in ("Ca", "B", "CaB")], store.cy
        ] += 1e-4 * np.array([-1, -1, 1])
    for j, channel in enumerate(c["raw"]["model"]["ionic"]["channels"]):
        count = len(channel["initial_gate"])
        d["channel_gate"][:, j] = [0.31 if count else 0.0, 0.63 if count == 2 else 0.0]
    edge = c["water_case"]["edges"][0]
    owner, outside = edge["sender"], edge["receiver"] - len(c["vi"])
    extent = 0.05 * min(c["vi"][owner], c["vo"][outside])
    d["volume_increment_pL"][owner] = extent
    d["extracellular_volume_increment_pL"][outside] = -extent
    d["water_transferred_pL"][0] = -extent
    return ref.flatten(c, d)


def accounting(c, y, slope, proof):
    d, r = ref.unpack(c, y), ref.unpack(c, slope)
    volume = ref.volumes(c, d)
    pool = c["energy_initial"] + d["energy_amount_increment_fmol"]
    n = len(c["cell_ids"])
    demand, work, regen, ports = (np.zeros(n) for _ in range(4))
    for family, energy_name, owners in (
        ("pump_cycles", "metabolic_work_pJ", c["patch_owners"]),
        ("plasma_pump_cycles", "plasma_metabolic_work_pJ", c["plasma_owners"]),
        ("er_pump_transferred", "er_metabolic_work_pJ", range(n)),
    ):
        for j, i in enumerate(owners):
            demand[i] += r[family][j, 0] if family == "er_pump_transferred" else r[family][j]
            work[i] += r[energy_name][j]
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        regen[i] += r["regeneration_cycles_fmol"][j]
        ports[i] += (
            r["regeneration_dissipated_energy_pJ"][j] - r["regeneration_supplied_work_pJ"][j]
        )
    np.testing.assert_allclose(
        r["energy_amount_increment_fmol"],
        np.array([-1, 1, 1])[:, None] * (demand - regen),
        rtol=3e-14,
        atol=3e-15,
    )
    scales, internal = [], []
    for i in range(n):
        thermo = chemistry.thermodynamics(
            pool[:, i], volume[i], c["temperature"], c["energy_delta_g0"][i]
        )
        chemical = 1e-3 * np.dot(
            thermo["chemical_potential_J_mol"], r["energy_amount_increment_fmol"][:, i]
        )
        expected_volume = thermo["volume_derivative_pJ_per_pL"] * r["volume_increment_pL"][i]
        np.testing.assert_allclose(
            r["pool_volume_work_pJ"][i], expected_volume, rtol=3e-15, atol=3e-14
        )
        np.testing.assert_allclose(
            work[i],
            -1e-3 * thermo["hydrolysis_free_energy_J_mol"] * demand[i],
            rtol=3e-14,
            atol=3e-14,
        )
        scale = (
            abs(work[i])
            + abs(ports[i])
            + np.sum(
                np.abs(
                    1e-3
                    * np.asarray(thermo["chemical_potential_J_mol"])
                    * r["energy_amount_increment_fmol"][:, i]
                )
            )
        )
        budget = 3e-12 + 8 * np.finfo(float).eps * scale
        residual = chemical + work[i] + ports[i]
        assert abs(residual) <= budget
        scales.append(dict(component_scale_pJ_s=float(scale), budget_pJ_s=float(budget)))
        internal.append(float(residual))
        a, b, p = r["energy_amount_increment_fmol"][:, i]
        assert abs(a + b) < 3e-15 and abs(math.fsum((a, a, a, b, b, p))) < 3e-15
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert (
        abs(r["volume_increment_pL"].sum() + r["extracellular_volume_increment_pL"].sum()) < 3e-14
    )
    chemical = ref.chemical_water.particles(c["chemical_water"], d)
    expected = (
        ref.R
        * c["temperature"]
        * (
            chemical.sum(axis=0)
            + c["water_case"]["impermeant_amount_fmol"]
            + np.r_[pool.sum(axis=0), np.zeros(len(c["vo"]))]
        )
        / volume
    )
    np.testing.assert_allclose(proof["osmotic_pressure_Pa"], expected, rtol=3e-15, atol=3e-10)
    physical = ownership_checks(c["energy"]["calcium"], ref.flatten(c["energy"]["calcium"], r))
    return dict(
        pool_internal_residual_pJ_s=internal,
        cancellation_budgets=scales,
        physical_ownership=physical,
        signed_pump_demand_fmol_s=demand.tolist(),
        signed_regeneration_fmol_s=regen.tolist(),
    )


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("perturbed", [False, True])
def test_frozen_43field_stages_and_chemical_pool_volume_invariants(name, perturbed):
    raw = inputs()[name]
    c = ref.bind(raw)
    assert len(c["shapes"]) == 43 and len(c["energy"]["shapes"]) == 38
    y = changed(c) if perturbed else ref.initial(c)
    if name.startswith("sealed-") and perturbed:
        with pytest.raises(ValueError, match="sealed"):
            ref.evaluate(c, y, 0.0)
        evidence("sealed-" + name, dict(inputs=raw, state=y.tolist(), expected_rejection=True))
        return
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    record = dict(
        inputs=raw,
        state=y.tolist(),
        derivative=slope.tolist(),
        potential_V=phi.tolist(),
        proof=proof,
    )
    evidence(f"stage-{name}-{perturbed}", record)
    record["checks"] = accounting(c, y, slope, proof)
    evidence(f"stage-{name}-{perturbed}", record)


def test_live_fuel_owner_and_volume_refresh_all_three_pump_families():
    c = ref.bind(case())
    baseline, phi0, _ = ref.evaluate(c, ref.initial(c), 0.0)
    d = ref.unpack(c, ref.initial(c))
    d["energy_amount_increment_fmol"][:, 0] = (
        0.2 * c["energy_initial"][:, 0].min() * np.array([-1, 1, 1])
    )
    slope, phi1, _ = ref.evaluate(c, ref.flatten(c, d), 0.0)
    before, after = ref.unpack(c, baseline), ref.unpack(c, slope)
    np.testing.assert_array_equal(phi0, phi1)
    for name, owners in (
        ("pump_cycles", c["patch_owners"]),
        ("plasma_pump_cycles", c["plasma_owners"]),
        ("er_pump_transferred", list(range(len(c["vi"])))),
    ):
        mask = np.array(owners) == 0
        assert np.any(before[name][mask] != after[name][mask])
        np.testing.assert_array_equal(before[name][~mask], after[name][~mask])
    for name in ("plasma_exchange_cycles", "channel_gate", "calcium_gate", "channel_transferred"):
        np.testing.assert_array_equal(before[name], after[name])
    y = changed(c)
    fields = ref.unpack(c, y)
    current = ref.current_energy_context(c, fields)
    stale = dict(current, energy_volumes=c["vi"])
    right = ref.unpack(c, ref.evaluate(c, y, 0.0)[0])
    wrong = parent.unpack(stale, parent.evaluate(stale, parent.flatten(stale, fields), 0.0)[0])
    for name in ("pump_cycles", "plasma_pump_cycles", "er_pump_transferred"):
        assert np.any(right[name] != wrong[name])
    for i, store in enumerate(current["calcium"]["stores"]):
        assert store.volume[store.cy] == current["energy_volumes"][i]
        assert store.volume[store.er] == c["stores"][i].volume[store.er]
    np.testing.assert_array_equal(c["energy"]["energy_volumes"], c["vi"])
    evidence(
        "live-fuel-volume",
        dict(
            state=y.tolist(),
            live_pump_cycles={
                k: right[k].tolist()
                for k in ("pump_cycles", "plasma_pump_cycles", "er_pump_transferred")
            },
            stale_pump_cycles={
                k: wrong[k].tolist()
                for k in ("pump_cycles", "plasma_pump_cycles", "er_pump_transferred")
            },
        ),
    )


def test_bound_complex_and_fuel_particle_changes_cancel_once_without_charging():
    c = ref.bind(case())
    d = ref.unpack(c, ref.initial(c))
    _, phi0, first = ref.evaluate(c, ref.flatten(c, d), 0.0)
    extent = 1e-4
    store = c["stores"][0]
    d["chemical_amount_increment"][
        0, [store.ids.index(k) for k in ("Ca", "B", "CaB")], store.cy
    ] += extent * np.array([-1, -1, 1])
    d["energy_amount_increment_fmol"][:, 0] = extent * np.array([-1, 1, 1])
    _, phi1, second = ref.evaluate(c, ref.flatten(c, d), 0.0)
    assert not np.any(d["amount_increment"])
    assert np.dot(store.z, d["chemical_amount_increment"][0, :, store.cy]) == 0
    owners = c["layout"]["membrane_cell"]
    outside = len(c["vi"]) + np.asarray(c["layout"]["membrane_outside"])
    np.testing.assert_allclose(
        phi0[owners] - phi0[outside], phi1[owners] - phi1[outside], rtol=0, atol=3e-14
    )
    np.testing.assert_allclose(
        second["osmotic_pressure_Pa"], first["osmotic_pressure_Pa"], rtol=0, atol=3e-10
    )


@pytest.mark.parametrize("perturbed", [False, True])
def test_endpoint_free_energy_directional_derivative(perturbed):
    c = ref.bind(case())
    y = changed(c) if perturbed else ref.initial(c)
    slope, _, proof = ref.evaluate(c, y, 0.0)
    target = proof["physical_free_energy_rate_pJ_s"]
    observed = []
    fields, rates = ref.unpack(c, y), ref.unpack(c, slope)
    interior = []
    for key in ("channel_gate", "calcium_gate"):
        gate, rate = fields[key], rates[key]
        active = rate != 0
        interior.extend(
            (np.minimum(gate[active], 1 - gate[active]) / np.abs(rate[active])).tolist()
        )
    inventories = [
        (
            c["energy_initial"] + fields["energy_amount_increment_fmol"],
            rates["energy_amount_increment_fmol"],
        ),
        (
            c["energy"]["calcium"]["ao"] + fields["extracellular_amount_increment"],
            rates["extracellular_amount_increment"],
        ),
    ]
    for i, store in enumerate(c["stores"]):
        inventories.append(
            (
                store.n0 + fields["chemical_amount_increment"][i],
                rates["chemical_amount_increment"][i],
            )
        )
    for amount, rate in inventories:
        active = rate != 0
        interior.extend((amount[active] / np.abs(rate[active])).tolist())
    volume = ref.volumes(c, fields)
    volume_rate = np.r_[rates["volume_increment_pL"], rates["extracellular_volume_increment_pL"]]
    active = volume_rate != 0
    margin = np.minimum(volume - c["minimum_volume_pL"], c["maximum_volume_pL"] - volume)
    interior.extend((margin[active] / np.abs(volume_rate[active])).tolist())
    coarse = min(6.4e-6, 0.25 * min(interior))
    steps = tuple(coarse / 2**i for i in range(12))
    for step in steps:
        gradient = (
            ref.free_energy_change(c, y + step * slope)
            - ref.free_energy_change(c, y - step * slope)
        ) / (2 * step)
        observed.append(float(gradient))
    errors = np.abs(np.asarray(observed) - target)
    budget = 2e-5 + 2e-10 * abs(target)
    windows = [i for i in range(len(steps) - 2) if np.all(errors[i : i + 3] <= budget)]
    evidence(
        "endpoint-direction-" + str(perturbed),
        dict(
            state=y.tolist(),
            endpoint_G_pJ=ref.free_energy_change(c, y),
            expected_power_pJ_s=target,
            numerical_power_pJ_s=observed,
            step_s=list(steps),
            absolute_errors_pJ_s=errors.tolist(),
            acceptance_budget_pJ_s=budget,
            adjacent_passing_windows=windows,
            coarse_convergence_order=float(np.log2(errors[0] / errors[1])),
        ),
    )
    # Three independently evaluated differences must resolve the same gradient.
    # Finer steps remain in the evidence: rounded bulk amounts eventually
    # amplify endpoint quantization as 1/h, rather than improving accuracy.
    assert windows
    assert errors[0] > errors[2] and errors[0] / errors[1] > 3
    np.testing.assert_allclose(observed[windows[0] : windows[0] + 3], target, rtol=2e-10, atol=2e-5)


@pytest.mark.parametrize("fault", ["missing_fuel", "duplicate_ions", "bad_standard_state"])
def test_negative_controls_break_declared_energy(fault, monkeypatch):
    if fault == "bad_standard_state":
        original = parent._legacy_calcium_pump

        def wrong(pump, concentrations, delta, temperature, er):
            value = original(pump, concentrations, delta, temperature, er)
            value["delta_g0_J_per_mol"] = float(delta)
            return value

        monkeypatch.setattr(parent, "_legacy_calcium_pump", wrong)
    else:
        original = ref.water.evaluate

        def wrong(case, volume, amount):
            indices = [
                c["stores"][0].ids.index(ion["id"]) for ion in c["raw"]["model"]["ionic"]["species"]
            ]
            counterfactual = (
                amount[:-3] if fault == "missing_fuel" else np.vstack((amount, amount[indices]))
            )
            return original(case, volume, counterfactual)

        monkeypatch.setattr(ref.water, "evaluate", wrong)
    c = ref.bind(case())
    y = changed(c)
    _, _, proof = ref.evaluate(c, y, 0.0)
    assert abs(proof["physical_energy_balance_pJ_s"]) > 1e-7
    evidence("negative-" + fault, dict(state=y.tolist(), proof=proof, expected_nonzero=True))


@pytest.mark.parametrize("direction", [-1, 1])
def test_signed_pool_volume_work_is_internal(direction):
    raw = case()
    raw["model"]["water_compartments"][0]["pressure_offset_Pa"] += direction * 2e6
    c = ref.bind(raw)
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0.0)
    r = ref.unpack(c, slope)
    assert np.sign(r["pool_volume_work_pJ"][0]) == direction
    assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) < 3e-12
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8


@pytest.mark.parametrize(
    "kind",
    [
        "exhausted",
        "nonfinite",
        "minimum",
        "maximum",
        "instantaneous",
        "dynamic_h",
        "free_calcium",
        "state_size",
        "water_heat",
        "regeneration_heat",
    ],
)
def test_invalid_complete_state_rejects_even_when_blocked(kind):
    raw = case()
    for family, groups in raw["experiment"].items():
        if family.endswith("_controls") and family != "store_controls":
            for row in groups:
                for change in row["schedule"]:
                    for key in change:
                        if key != "time":
                            change[key] = 0.0
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    if kind == "exhausted":
        d["energy_amount_increment_fmol"][0, 0] = -c["energy_initial"][0, 0]
    elif kind == "nonfinite":
        d["pool_volume_work_pJ"][0] = np.nan
    elif kind in ("minimum", "maximum"):
        boundary = c["minimum_volume_pL"][0] if kind == "minimum" else c["maximum_volume_pL"][0]
        d["volume_increment_pL"][0] = boundary - c["vi"][0]
    elif kind == "free_calcium":
        store = c["stores"][0]
        d["chemical_amount_increment"][0, store.ca, store.cy] = -store.n0[store.ca, store.cy]
    elif kind in ("instantaneous", "dynamic_h"):
        count = 0 if kind == "instantaneous" else 1
        slot = next(
            i
            for i, p in enumerate(raw["model"]["ionic"]["channels"])
            if len(p["initial_gate"]) == count
        )
        d["channel_gate"][0 if count == 0 else 1, slot] = 1e-20
    elif kind in ("water_heat", "regeneration_heat"):
        d[
            "water_dissipated_energy_pJ"
            if kind == "water_heat"
            else "regeneration_dissipated_energy_pJ"
        ][0] = -1e-8
    y = ref.flatten(c, d)
    if kind == "state_size":
        y = y[:-1]
    with pytest.raises(ValueError):
        ref.evaluate(c, y, 0.0)


@pytest.mark.parametrize(
    "field", ["pool_volume_work_pJ", "water_transferred_pL", "water_dissipated_energy_pJ"]
)
def test_sealed_ports_cannot_own_transport_history(field):
    raw = deepcopy(next(v for name, v in inputs().items() if name.startswith("sealed-")))
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    d[field][0] = 1e-20
    with pytest.raises(ValueError, match="water"):
        ref.evaluate(c, ref.flatten(c, d), 0.0)


@pytest.mark.parametrize(
    "fault",
    ["chemical_coupling", "fuel_coupling", "overlap", "shared_volume", "er_water", "cross_owner"],
)
def test_explicit_particle_and_owner_contract(fault):
    raw = case()
    m = raw["model"]
    if fault in ("chemical_coupling", "fuel_coupling"):
        m[
            "chemical_osmotic_coupling"
            if fault == "chemical_coupling"
            else "energy_osmotic_coupling"
        ] = "implicit@1"
    elif fault == "overlap":
        m["stores"][0]["model"]["species"][0]["id"] = "ATP"
    elif fault == "shared_volume":
        store = m["stores"][0]["model"]
        next(v for v in store["compartments"] if v["id"] == store["membrane"]["cytosol"])[
            "volume_pL"
        ] *= 1.1
    elif fault == "er_water":
        m["water_compartments"][0]["compartment_id"] = "er"
    else:
        m["plasma_transport"]["membranes"][0]["pump"]["metabolism"]["pool_id"] = m["energy_pools"][
            1
        ]["id"]
    with pytest.raises(ValueError):
        ref.bind(raw)


def test_no_production_cells_or_jax_modules_imported():
    assert not any(
        name == "cells" or name.startswith("cells.") or name == "jax" or name.startswith("jax.")
        for name in sys.modules
    )


def test_short_43field_adaptive_refinement_and_integrated_energy():
    raw = deepcopy(inputs()["probe"])
    horizon = 2 * raw["execution"]["dt"]
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [v for v in row[key] if v["time"] <= horizon]
    for name, fraction in (
        ("channel_controls", 0.44),
        ("regeneration_controls", 0.52),
        ("water_controls", 0.68),
    ):
        raw["experiment"][name][0]["schedule"] = [
            raw["experiment"][name][0]["schedule"][0],
            dict(time=fraction * horizon, availability=0.0),
        ]
    raw["experiment"].update(
        end_time=horizon,
        observation_times=[fraction * horizon for fraction in (0, 0.44, 0.52, 0.68, 1)],
    )
    first = ref.integrate(raw, refinement=1, max_step_s=raw["execution"]["dt"])
    second = ref.integrate(raw, refinement=2, max_step_s=raw["execution"]["dt"])
    c = ref.bind(raw)
    budget = ref.flatten(
        c,
        {
            key: np.full(shape, 3e-26 if key.endswith("_C") else 3e-11)
            for key, shape in c["shapes"].items()
        },
    )
    ratio = float(
        np.max(
            np.abs(first["state"] - second["state"])
            / (budget[None, :] + 3e-9 * np.abs(second["state"]))
        )
    )
    assert ratio < 1
    energy, internal = [], []
    for time, y in zip(second["times"], second["state"], strict=True):
        d = ref.unpack(c, y)
        heat = sum(
            float(np.sum(v)) for key, v in d.items() if key.endswith("_dissipated_energy_pJ")
        )
        supply = float(
            np.sum(d["regeneration_supplied_work_pJ"])
            + np.sum(d["reservoir_work_pJ"])
            + np.sum(d["electrode_work_pJ"])
        )
        energy.append(ref.free_energy_change(c, y, time) + heat - supply)
        work = np.zeros(len(c["vi"]))
        for key, owners in (
            ("metabolic_work_pJ", c["patch_owners"]),
            ("plasma_metabolic_work_pJ", c["plasma_owners"]),
            ("er_metabolic_work_pJ", range(len(c["vi"]))),
        ):
            for j, i in enumerate(owners):
                work[i] += d[key][j]
        for j, port in enumerate(raw["model"]["regeneration_ports"]):
            i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
            work[i] += (
                d["regeneration_dissipated_energy_pJ"][j] - d["regeneration_supplied_work_pJ"][j]
            )
        volume = ref.volumes(c, d)
        fuel = c["energy_initial"] + d["energy_amount_increment_fmol"]
        residual = []
        for i in range(len(c["vi"])):
            g = chemistry.free_energy_change(
                c["energy_initial"][:, i],
                fuel[:, i],
                c["vi"][i],
                volume[i],
                c["temperature"],
                c["energy_delta_g0"][i],
            )
            residual.append(float(g + work[i] - d["pool_volume_work_pJ"][i]))
        internal.append(residual)
        np.testing.assert_allclose(
            fuel[0] + fuel[1], c["energy_initial"][0] + c["energy_initial"][1], rtol=0, atol=2e-12
        )
        np.testing.assert_allclose(
            np.array([3, 2, 1]) @ fuel,
            np.array([3, 2, 1]) @ c["energy_initial"],
            rtol=0,
            atol=2e-12,
        )
        assert (
            abs(d["volume_increment_pL"].sum() + d["extracellular_volume_increment_pL"].sum())
            < 2e-12
        )
    np.testing.assert_allclose(energy, 0, rtol=0, atol=1e-9)
    np.testing.assert_allclose(internal, 0, rtol=0, atol=1e-9)
    evidence(
        "short-43-refinement",
        dict(
            inputs=raw,
            horizon_s=horizon,
            max_error_over_budget=ratio,
            times_s=second["times"],
            coarse=first["state"].tolist(),
            fine=second["state"].tolist(),
            evaluations=[first["evaluations"], second["evaluations"]],
            joint_energy_residual_pJ=energy,
            pool_internal_residual_pJ=internal,
            scope="Short full43 coupling/refinement; not full-system settling",
        ),
    )


def test_actual_regeneration_water_pair_physical_relaxation():
    from time import monotonic

    from scipy.integrate import solve_ivp
    from scipy.optimize import brentq
    from scipy.special import expit

    raw = case()
    c = ref.bind(raw)
    port = raw["model"]["regeneration_ports"][0]
    owner = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
    index, edge = next(
        (i, e)
        for i, e in enumerate(c["water_case"]["edges"])
        if e["sender"] == owner and e["hydraulic_permeability_m_per_Pa_s"] > 0
    )
    nodes = [owner, edge["receiver"]]
    initial_volume = np.r_[c["vi"], c["vo"]][nodes]
    total_volume = initial_volume.sum()
    initial_pool = c["energy_initial"][:, owner]
    adenylate, ATP_Pi = initial_pool[0] + initial_pool[1], initial_pool[0] + initial_pool[2]
    upper_atp = min(adenylate, ATP_Pi)
    lower_v = max(c["minimum_volume_pL"][nodes[0]], total_volume - c["maximum_volume_pL"][nodes[1]])
    upper_v = min(c["maximum_volume_pL"][nodes[0]], total_volume - c["minimum_volume_pL"][nodes[1]])
    nonpool = (
        ref.chemical_water.particles(c["chemical_water"], ref.unpack(c, ref.initial(c)))[
            :, nodes
        ].sum(axis=0)
        + c["water_case"]["impermeant_amount_fmol"][nodes]
    )
    reference_v = c["water_case"]["reference_volume_pL"][nodes]
    modulus = c["water_case"]["bulk_modulus_Pa"][nodes]
    pressure_offset = c["water_case"]["pressure_offset_Pa"][nodes]
    level = c["regeneration_controls"][port["id"]][0]["availability"]
    water_level = c["water_controls"][index][0]["availability"]
    capacity = port["capacity_fmol_per_s"] * level
    conductance = 1e15 * edge["area_m2"] * edge["hydraulic_permeability_m_per_Pa_s"] * water_level
    rt = ref.R * c["temperature"]
    delta = c["energy_delta_g0"][owner]
    supplied = port["supplied_energy_J_per_mol"]
    assert capacity > 0 and conductance > 0

    def fuel(atp):
        return np.array([atp, adenylate - atp, ATP_Pi - atp])

    def equilibrium_atp(volume):
        k = 1000 * volume * np.exp((-supplied - delta) / rt)
        denominator = (
            adenylate
            + ATP_Pi
            + k
            + np.sqrt((adenylate - ATP_Pi) ** 2 + k * (2 * (adenylate + ATP_Pi) + k))
        )
        return 2 * adenylate * ATP_Pi / denominator

    def potential(volume, atp):
        v = np.array([volume, total_volume - volume])
        return (
            modulus * (v / reference_v - 1)
            + pressure_offset
            - rt * (nonpool + np.array([fuel(atp).sum(), 0.0])) / v
        )

    equilibrium_v = brentq(
        lambda v: np.diff(potential(v, equilibrium_atp(v)))[0],
        np.nextafter(lower_v, upper_v),
        np.nextafter(upper_v, lower_v),
        xtol=5e-15,
        rtol=1e-14,
    )
    equilibrium_pool = fuel(equilibrium_atp(equilibrium_v))
    equilibrium_volumes = np.array([equilibrium_v, total_volume - equilibrium_v])
    slopes = (
        modulus / reference_v
        + rt * (nonpool + np.array([equilibrium_pool.sum(), 0])) / equilibrium_volumes**2
    )
    jacobian = np.array(
        [
            [-conductance * slopes.sum(), -conductance * rt / equilibrium_v],
            [-capacity / (2 * equilibrium_v), -capacity * 0.5 * np.sum(1 / equilibrium_pool)],
        ]
    )
    eigenvalues = np.linalg.eigvals(jacobian)
    assert np.all(eigenvalues.real < 0) and np.max(np.abs(eigenvalues.imag)) < 1e-12
    slow_tau = float(max(-1 / eigenvalues.real))
    transit = 2 * abs(equilibrium_pool[0] - initial_pool[0]) / capacity
    horizon = transit + 12 * slow_tau
    times = np.linspace(0, horizon, 129)
    start = [
        np.log((initial_volume[0] - lower_v) / (upper_v - initial_volume[0])),
        np.log(initial_pool[0] / (upper_atp - initial_pool[0])),
        0,
        0,
        0,
        0,
        0,
    ]
    results = []

    def coordinates(y):
        v = lower_v + (upper_v - lower_v) * expit(y[0])
        atp = upper_atp * expit(y[1])
        return np.array([v, total_volume - v]), fuel(atp)

    def rhs(t, y):
        volume, amount = coordinates(y)
        try:
            affinity = (
                delta
                + rt * math.log(amount[1] * amount[2] / (1000 * amount[0] * volume[0]))
                + supplied
            )
            synthesis = capacity * math.tanh(affinity / (2 * rt))
            drive = potential(volume[0], amount[0])
            flow = conductance * (drive[0] - drive[1])
            volume_rate = -flow
            return [
                volume_rate / ((volume[0] - lower_v) * (upper_v - volume[0]) / (upper_v - lower_v)),
                synthesis / (amount[0] * (1 - amount[0] / upper_atp)),
                synthesis,
                1e-3 * flow * (drive[0] - drive[1]),
                1e-3 * synthesis * affinity,
                1e-3 * synthesis * supplied,
                -1e-3 * rt * amount.sum() / volume[0] * volume_rate,
            ]
        except Exception:
            evidence(
                "physical-pair-failed-state",
                dict(
                    time_s=float(t),
                    state=y.tolist(),
                    volume_pL=volume.tolist(),
                    pool_fmol=amount.tolist(),
                ),
            )
            raise

    maximum_step = min(horizon / 64, 0.5 / np.max(np.abs(eigenvalues.real)))
    evidence(
        "physical-time-plan",
        dict(
            source_input=raw,
            port=port,
            water_edge=edge,
            availability=level,
            water_availability=water_level,
            initial_volume_pL=initial_volume.tolist(),
            initial_pool_fmol=initial_pool.tolist(),
            nonfuel_particles_fmol=nonpool.tolist(),
            jacobian_per_s=jacobian.tolist(),
            eigenvalues_per_s=eigenvalues.real.tolist(),
            equilibrium_volume_pL=equilibrium_volumes.tolist(),
            equilibrium_pool_fmol=equilibrium_pool.tolist(),
            slow_tau_s=slow_tau,
            transit_allowance_s=float(transit),
            tau_multiples=12,
            horizon_s=float(horizon),
            maximum_step_s=float(maximum_step),
        ),
    )
    chemical_particles = ref.chemical_water.particles(
        c["chemical_water"], ref.unpack(c, ref.initial(c))
    )[:, nodes]
    water_case = dict(
        temperature_K=c["temperature"],
        initial_volume_pL=initial_volume,
        reference_volume_pL=reference_v,
        impermeant_amount_fmol=c["water_case"]["impermeant_amount_fmol"][nodes],
        bulk_modulus_Pa=modulus,
        pressure_offset_Pa=pressure_offset,
        edges=[
            dict(
                edge,
                sender=0,
                receiver=1,
                hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
                * water_level,
            )
        ],
    )
    for refinement in (1, 2):
        started = monotonic()
        solved = solve_ivp(
            rhs,
            (0, horizon),
            start,
            method="DOP853",
            t_eval=times,
            rtol=4e-12 / refinement,
            atol=np.array([1e-13, 1e-13, 2e-14, 2e-14, 2e-14, 2e-14, 2e-14]) / refinement,
            max_step=maximum_step / refinement,
        )
        assert solved.success, solved.message
        volume = np.array([coordinates(y)[0] for y in solved.y.T])
        pool = np.array([coordinates(y)[1] for y in solved.y.T])
        energy, internal = [], []
        initial_extension = initial_volume - reference_v
        for j, (v, n) in enumerate(zip(volume, pool, strict=True)):
            dilution = -1e-3 * rt * np.dot(nonpool, np.log(v / initial_volume))
            extension = v - reference_v
            elastic = 1e-3 * np.sum(
                0.5 * modulus / reference_v * (extension**2 - initial_extension**2)
                + pressure_offset * (v - initial_volume)
            )
            pool_g = chemistry.free_energy_change(
                initial_pool, n, initial_volume[0], v[0], c["temperature"], delta
            )
            energy.append(
                float(
                    dilution + elastic + pool_g + solved.y[3, j] + solved.y[4, j] - solved.y[5, j]
                )
            )
            internal.append(float(pool_g + solved.y[4, j] - solved.y[5, j] - solved.y[6, j]))
        record = dict(
            volume_pL=volume.tolist(),
            pool_fmol=pool.tolist(),
            state=solved.y.T.tolist(),
            joint_energy_residual_pJ=energy,
            pool_internal_residual_pJ=internal,
            evaluations=solved.nfev,
            execute_seconds=monotonic() - started,
            method="DOP853; independent float algebra verified against Decimal checkpoints",
        )
        evidence("physical-profile-" + str(refinement), record)
        np.testing.assert_allclose(energy, 0, rtol=0, atol=1e-9)
        np.testing.assert_allclose(internal, 0, rtol=0, atol=1e-9)
        np.testing.assert_allclose(pool[:, 0] + pool[:, 1], adenylate, rtol=0, atol=3e-15)
        np.testing.assert_allclose(
            pool @ np.array([3, 2, 1]), initial_pool @ np.array([3, 2, 1]), rtol=0, atol=6e-15
        )
        np.testing.assert_allclose(pool[:, 0] - initial_pool[0], solved.y[2], rtol=0, atol=2e-12)
        assert (
            np.all(pool > 0)
            and np.all(volume > c["minimum_volume_pL"][nodes])
            and np.all(volume < c["maximum_volume_pL"][nodes])
        )
        assert np.min(np.diff(solved.y[3:5], axis=1)) >= -1e-12
        np.testing.assert_allclose(volume[-1], equilibrium_volumes, atol=1e-8, rtol=0)
        np.testing.assert_allclose(pool[-1], equilibrium_pool, atol=1e-9, rtol=0)
        deviations = []
        for j, (v, n) in enumerate(zip(volume, pool, strict=True)):
            derivative = np.array(rhs(times[j], solved.y[:, j]))
            wanted = chemistry.regeneration(
                n, v[0], c["temperature"], delta, port["capacity_fmol_per_s"], supplied, level
            )
            hydraulic = ref.water.evaluate(
                dict(
                    water_case,
                    amount_fmol=np.c_[chemical_particles, np.empty((len(chemical_particles), 0))],
                ),
                v,
                np.vstack((chemical_particles, np.c_[n, np.zeros(3)])),
            )
            np.testing.assert_allclose(
                derivative[2], wanted["synthesis_fmol_s"], atol=3e-15, rtol=3e-14
            )
            np.testing.assert_allclose(
                derivative[4:6],
                [wanted["dissipated_power_pJ_s"], wanted["supplied_power_pJ_s"]],
                atol=3e-13,
                rtol=3e-14,
            )
            np.testing.assert_allclose(
                derivative[3], hydraulic["edge_dissipation_pJ_s"][0], atol=3e-10, rtol=3e-14
            )
            rate = derivative[0] * (v[0] - lower_v) * (upper_v - v[0]) / (upper_v - lower_v)
            np.testing.assert_allclose(
                rate, hydraulic["volume_rate_pL_s"][0], atol=3e-12, rtol=3e-14
            )
            deviations.append(
                [
                    float(derivative[2] - wanted["synthesis_fmol_s"]),
                    float(rate - hydraulic["volume_rate_pL_s"][0]),
                ]
            )
        record["decimal_checkpoint_deviations"] = deviations
        evidence("physical-profile-" + str(refinement), record)
        results.append(record)
    np.testing.assert_allclose(
        results[0]["volume_pL"], results[1]["volume_pL"], atol=2e-11, rtol=2e-11
    )
    np.testing.assert_allclose(
        results[0]["pool_fmol"], results[1]["pool_fmol"], atol=2e-11, rtol=2e-11
    )
    evidence(
        "actual-port-water-physical-time",
        dict(
            source_input=raw,
            port=port,
            water_edge=edge,
            availability=level,
            water_availability=water_level,
            nonfuel_particles_fmol=nonpool.tolist(),
            equilibrium_volume_pL=equilibrium_volumes.tolist(),
            equilibrium_pool_fmol=equilibrium_pool.tolist(),
            jacobian_per_s=jacobian.tolist(),
            eigenvalues_per_s=eigenvalues.real.tolist(),
            slow_tau_s=slow_tau,
            transit_allowance_s=float(transit),
            tau_multiples=12,
            horizon_s=float(horizon),
            times_s=times.tolist(),
            results=results,
            scope=(
                "Reduced actual-port fuel/water pair with frozen chemical particles and fixed ER, "
                "pumps absent; positive coordinate transform, no clipping; "
                "separate from full43 settling"
            ),
        ),
    )

"""Independent 53-law finite energy/water with explicit thermodynamic ownership.

Short coupled windows validate wiring and refinement. Actual-port pool
relaxation and previously frozen water relaxation remain separate components.
"""

import hashlib
import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from scipy.special import expit

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_energy_reference as energy
from validation.tissue import surface_energy_water_reference as coupled
from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue import water_volume_reference as water
from validation.tissue.test_calcium_catalog_v2_reference import evidence, frozen_module
from validation.tissue.test_morris_lecar_catalog_reference import ml_routes, sensor_routes

MODELS = {
    "energy": (energy, "resolved_energy@2", 23),
    "water": (coupled, "resolved_energy_water@2", 28),
}
pytestmark = pytest.mark.skipif(
    "CELLS_ML_ENERGY_WATER_INPUTS" not in os.environ,
    reason="Require frozen raw serialized energy/water inputs",
)


def inputs():
    directory = os.environ.get("CELLS_ML_ENERGY_WATER_INPUTS")
    if not directory:
        return {}
    result = {}
    for path in sorted(Path(directory).glob("*.json")):
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and raw.get("model", {}).get("id") in {
            row[1] for row in MODELS.values()
        }:
            result[path.stem] = raw
    return result


def case(kind="water", arm="open"):
    return deepcopy(inputs()[kind + "-" + arm])


def state(kind, c, changed=False):
    module = MODELS[kind][0]
    d = module.unpack(c, module.initial(c))
    if changed:
        for i in range(len(c["vi"])):
            d["energy_amount_increment_fmol"][:, i] = (
                0.1 * c["energy_initial"][:, i].min() * np.array([-1, 1, 1])
            )
        for j, ch in enumerate(c["raw"]["model"]["channels"]):
            law = ch["kinetic_law"]
            if law == ionic.CALCIUM_ACTIVATED_LAW or (
                law in ionic.MORRIS_LECAR_LAWS and law not in ionic.ML_DYNAMIC_LAWS
            ):
                d["channel_gate"][:, j] = 0
            elif law in ionic.ML_DYNAMIC_LAWS:
                d["channel_gate"][:, j] = [0.31, 0.0]
            else:
                d["channel_gate"][:, j] = [0.31, 0.63]
        if kind == "water":
            edge = c["water_case"]["edges"][0]
            i, o = edge["sender"], edge["receiver"]
            volume = np.r_[c["vi"], c["vo"]]
            delta = min(
                0.05 * min(volume[i], volume[o]),
                0.25 * (c["maximum_volume_pL"][i] - volume[i]),
                0.25 * (volume[o] - c["minimum_volume_pL"][o]),
            )
            d["volume_increment_pL"][i] = delta
            d["extracellular_volume_increment_pL"][o - len(c["vi"])] = -delta
            d["water_transferred_pL"][0] = -delta
    return module.flatten(c, d)


def values(kind, c, y):
    d = ionic.unpack(c, y)
    volume = np.r_[c["vi"], c["vo"]].copy()
    if kind == "water":
        volume += np.r_[d["volume_increment_pL"], d["extracellular_volume_increment_pL"]]
    ions = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    pools = c["energy_initial"] + d["energy_amount_increment_fmol"]
    return d, volume, ions, pools


def accounting(kind, c, y, slope, phi, proof, time=0):
    d, volume, ions, pools = values(kind, c, y)
    r, n = ionic.unpack(c, slope), len(c["vi"])
    demand, work, regen, port_power = (np.zeros(n) for _ in range(4))
    for j, patch in enumerate(c["raw"]["model"]["membranes"]):
        i = c["cell_ids"].index(patch["inside"])
        demand[i] += r["pump_cycles"][j]
        work[i] += r["metabolic_work_pJ"][j]
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        level = ionic.availability(c, "regeneration", port["id"], time)
        oracle = chemistry.regeneration(
            pools[:, i],
            volume[i],
            298.15,
            c["energy_delta_g0"][i],
            port["capacity_fmol_per_s"],
            port["supplied_energy_J_per_mol"],
            level,
        )
        np.testing.assert_allclose(
            r["regeneration_cycles_fmol"][j], oracle["synthesis_fmol_s"], rtol=3e-15, atol=3e-17
        )
        np.testing.assert_allclose(
            r["regeneration_dissipated_energy_pJ"][j],
            oracle["dissipated_power_pJ_s"],
            rtol=3e-15,
            atol=3e-15,
        )
        regen[i] += r["regeneration_cycles_fmol"][j]
        port_power[i] += (
            r["regeneration_dissipated_energy_pJ"][j] - r["regeneration_supplied_work_pJ"][j]
        )
    expected = np.array([-1, 1, 1])[:, None] * (demand - regen)
    np.testing.assert_allclose(r["energy_amount_increment_fmol"], expected, rtol=3e-14, atol=3e-15)
    internal = []
    for i in range(n):
        thermo = chemistry.thermodynamics(pools[:, i], volume[i], 298.15, c["energy_delta_g0"][i])
        np.testing.assert_allclose(
            work[i],
            -1e-3 * thermo["hydrolysis_free_energy_J_mol"] * demand[i],
            rtol=3e-14,
            atol=3e-13,
        )
        chemical = 1e-3 * np.dot(
            thermo["chemical_potential_J_mol"], r["energy_amount_increment_fmol"][:, i]
        )
        internal.append(float(chemical + work[i] + port_power[i]))
        a, b, p = r["energy_amount_increment_fmol"][:, i]
        assert abs(a + b) < 3e-15
        assert abs(math.fsum((a, a, a, b, b, p))) < 3e-15
        if kind == "water":
            expected_wvol = thermo["volume_derivative_pJ_per_pL"] * r["volume_increment_pL"][i]
            np.testing.assert_allclose(
                r["pool_volume_work_pJ"][i], expected_wvol, rtol=3e-15, atol=3e-14
            )
            initial = c["energy_initial"][:, i]
            upper = 2 * initial[0] + initial[1] + initial[2]
            assert pools[:, i].sum() < upper
    np.testing.assert_allclose(internal, 0, rtol=0, atol=3e-12)
    np.testing.assert_allclose(
        r["amount_increment"].sum(axis=1) + r["extracellular_amount_increment"].sum(axis=1),
        0,
        rtol=0,
        atol=3e-13,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    if kind == "water":
        expected_pressure = (
            ionic.R
            * 298.15
            * (
                ions.sum(axis=0)
                + c["water_case"]["impermeant_amount_fmol"]
                + np.r_[pools.sum(axis=0), np.zeros(len(c["vo"]))]
            )
            / volume
        )
        np.testing.assert_allclose(
            proof["osmotic_pressure_Pa"], expected_pressure, rtol=3e-15, atol=3e-10
        )
        np.testing.assert_allclose(
            proof["pool_internal_transfer_balance_pJ_s"], internal, rtol=0, atol=3e-12
        )
        np.testing.assert_allclose(
            r["volume_increment_pL"].sum() + r["extracellular_volume_increment_pL"].sum(),
            0,
            rtol=0,
            atol=3e-14,
        )
    base = c["energy"]["ionic"] if kind == "water" else c["ionic"]
    current = dict(base, vi=volume[:n], vo=volume[n:])
    old_y, old_rate = ionic.flatten(current, d), ionic.flatten(current, r)
    return dict(
        internal_pool_residual_pJ_s=internal,
        volume_pL=volume.tolist(),
        pool_amount_fmol=pools.tolist(),
        ML=ml_routes("tissue", current, current["raw"], old_y, old_rate, phi, time),
        CaK=sensor_routes("tissue", current, current["raw"], old_y, old_rate, phi, time),
    )


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("changed", [False, True])
def test_complete_53_law_energy_water_stages(name, changed):
    raw = inputs()[name]
    kind = next(k for k, v in MODELS.items() if raw["model"]["id"] == v[1])
    module, _, count = MODELS[kind]
    c = module.bind(raw)
    assert len(c["shapes"]) == count
    y = state(kind, c, changed)
    if kind == "water" and name.endswith("sealed") and changed:
        evidence(
            "sealed-counterfactual", dict(inputs=raw, state=y.tolist(), expected_rejection=True)
        )
        with pytest.raises(ValueError, match="Permanently sealed"):
            module.evaluate(c, y, 0)
        return
    slope, phi, proof = module.evaluate(c, y, 0)
    saved = dict(
        inputs=raw,
        state=y.tolist(),
        derivative=slope.tolist(),
        potential_V=phi.tolist(),
        proof=proof,
    )
    evidence(f"stage-{name}-{changed}", saved)
    saved["checks"] = accounting(kind, c, y, slope, phi, proof)
    evidence(f"stage-{name}-{changed}", saved)


def test_live_volume_dilutes_ions_pools_and_metabolic_drive_without_mutating_context():
    c = coupled.bind(case())
    y = state("water", c, True)
    slope, phi, proof = coupled.evaluate(c, y, 0)
    d, volume, _, pools = values("water", c, y)
    n = len(c["vi"])
    current = dict(
        c["energy"],
        vi=volume[:n],
        vo=volume[n:],
        energy_volumes=volume[:n],
        ionic=dict(c["energy"]["ionic"], vi=volume[:n], vo=volume[n:]),
    )
    expected, wanted_phi, _ = energy.evaluate(current, energy.flatten(current, d), 0)
    np.testing.assert_array_equal(energy.flatten(current, coupled.unpack(c, slope)), expected)
    np.testing.assert_array_equal(phi, wanted_phi)
    stale = dict(current, energy_volumes=c["vi"])
    wrong = energy.unpack(stale, energy.evaluate(stale, energy.flatten(stale, d), 0)[0])
    right = coupled.unpack(c, slope)
    assert np.max(np.abs(right["pump_cycles"] - wrong["pump_cycles"])) > 1e-12
    assert (
        np.max(np.abs(right["regeneration_cycles_fmol"] - wrong["regeneration_cycles_fmol"]))
        > 1e-12
    )
    for i in range(n):
        live = chemistry.thermodynamics(pools[:, i], volume[i], 298.15, c["energy_delta_g0"][i])
        old = chemistry.thermodynamics(pools[:, i], c["vi"][i], 298.15, c["energy_delta_g0"][i])
        np.testing.assert_allclose(
            live["hydrolysis_free_energy_J_mol"] - old["hydrolysis_free_energy_J_mol"],
            -ionic.R * 298.15 * np.log(volume[i] / c["vi"][i]),
            rtol=2e-13,
            atol=3e-11,
        )
    checks = accounting("water", c, y, slope, phi, proof)
    changed_sensor = False
    for row in checks["CaK"]:
        i = row["cell_owner"]
        if volume[i] != c["vi"][i]:
            from validation.channels import calcium_activated_potassium_reference as sensor

            old_ca = row["free_calcium_mM"] * volume[i] / c["vi"][i]
            wrong_open = sensor.evaluate(row["voltage_V"], old_ca, 298.15)["opening"]
            assert abs(row["opening"] - wrong_open) > 1e-13
            changed_sensor = True
    assert changed_sensor
    np.testing.assert_array_equal(c["energy"]["energy_volumes"], c["vi"])
    np.testing.assert_array_equal(c["energy"]["ionic"]["vi"], c["vi"])
    evidence(
        "live-dilution",
        dict(
            inputs=c["raw"],
            state=y.tolist(),
            checks=checks,
            stale_pump_fmol_s=wrong["pump_cycles"].tolist(),
            stale_supply_fmol_s=wrong["regeneration_cycles_fmol"].tolist(),
        ),
    )


def test_pool_reaction_changes_pressure_without_charging_or_directly_gating():
    c = coupled.bind(case())
    y = coupled.initial(c)
    a, phi0, p0 = coupled.evaluate(c, y, 0)
    d = coupled.unpack(c, y.copy())
    extent = 0.1 * c["energy_initial"][:, 0].min()
    d["energy_amount_increment_fmol"][:, 0] = extent * np.array([-1, 1, 1])
    b, phi1, p1 = coupled.evaluate(c, coupled.flatten(c, d), 0)
    np.testing.assert_array_equal(phi0, phi1)
    delta = np.zeros(len(c["vi"]) + len(c["vo"]))
    delta[0] = ionic.R * 298.15 * extent / c["vi"][0]
    np.testing.assert_allclose(
        np.asarray(p1["osmotic_pressure_Pa"]) - p0["osmotic_pressure_Pa"],
        delta,
        rtol=3e-12,
        atol=2e-10,
    )
    ra, rb = coupled.unpack(c, a), coupled.unpack(c, b)
    for name in ("channel_gate", "channel_transferred", "membrane_transferred"):
        np.testing.assert_array_equal(ra[name], rb[name])
    assert np.any(ra["water_transferred_pL"] != rb["water_transferred_pL"])
    accounting("water", c, coupled.flatten(c, d), b, phi1, p1)


def test_energy_identity_detects_missing_pool_particles(monkeypatch):
    original = water.evaluate

    def missing(case, volume, amount):
        return original(case, volume, amount[:-3])

    monkeypatch.setattr(water, "evaluate", missing)
    c = coupled.bind(case())
    y = state("water", c, True)
    _, _, proof = coupled.evaluate(c, y, 0)
    evidence(
        "omitted-pool-negative-control", dict(state=y.tolist(), proof=proof, expected_nonzero=True)
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) > 1e-9


@pytest.mark.parametrize("contraction", [False, True])
def test_pool_volume_work_keeps_its_signed_internal_role(contraction):
    raw = case()
    cell = raw["model"]["cells"][0]["id"]
    next(v for v in raw["model"]["water_compartments"] if v["compartment_id"] == cell)[
        "pressure_offset_Pa"
    ] += 2e6 if contraction else -2e6
    c = coupled.bind(raw)
    slope, _, proof = coupled.evaluate(c, coupled.initial(c), 0)
    r = coupled.unpack(c, slope)
    expected = (
        -1e-3
        * ionic.R
        * 298.15
        * c["energy_initial"].sum(axis=0)
        / c["vi"]
        * r["volume_increment_pL"]
    )
    np.testing.assert_allclose(r["pool_volume_work_pJ"], expected, rtol=3e-15, atol=3e-14)
    evidence(
        f"manufactured-signed-volume-work-{contraction}",
        dict(
            inputs=raw,
            state=coupled.initial(c).tolist(),
            derivative=slope.tolist(),
            proof=proof,
            scope="Manufactured pressure offsets explicitly select expansion or contraction",
        ),
    )
    assert r["pool_volume_work_pJ"][0] > 0 if contraction else r["pool_volume_work_pJ"][0] < 0
    assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) < 3e-12
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8


@pytest.mark.parametrize("kind", MODELS)
@pytest.mark.parametrize("category", ["CaK", "dynamic", "instantaneous", "exhausted", "nonfinite"])
def test_invalid_complete_states_reject(kind, category):
    raw, module = case(kind), MODELS[kind][0]
    c = module.bind(raw)
    d = module.unpack(c, module.initial(c))
    if category == "exhausted":
        d["energy_amount_increment_fmol"][0, 0] = -c["energy_initial"][0, 0]
    elif category == "nonfinite":
        d["regeneration_supplied_work_pJ"][0] = np.nan
    else:
        law = (
            ionic.CALCIUM_ACTIVATED_LAW
            if category == "CaK"
            else next(
                v
                for v in ionic.MORRIS_LECAR_LAWS
                if (v in ionic.ML_DYNAMIC_LAWS) == (category == "dynamic")
            )
        )
        j = next(j for j, ch in enumerate(raw["model"]["channels"]) if ch["kinetic_law"] == law)
        d["channel_gate"][1 if category == "dynamic" else 0, j] = 1e-20
    with pytest.raises(ValueError):
        module.evaluate(c, module.flatten(c, d), 0)


@pytest.mark.parametrize("field", ["water_transferred_pL", "water_dissipated_energy_pJ"])
def test_zero_lp_history_rejects(field):
    c = coupled.bind(case("water", "sealed"))
    d = coupled.unpack(c, coupled.initial(c))
    d[field][0] = 1e-20
    with pytest.raises(ValueError, match="Permanently sealed"):
        coupled.evaluate(c, coupled.flatten(c, d), 0)


@pytest.mark.parametrize("kind", MODELS)
@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("old_version", [False, True])
def test_old_energy18_projection_is_bitwise_unchanged(kind, changed, old_version):
    root = Path(os.environ["CELLS_ML_ENERGY_WATER_BASELINE"])
    old_i = frozen_module("old_pool_ionic", root / "validation/tissue/surface_kinetic_reference.py")
    old_e = frozen_module("old_pool_energy", root / "validation/tissue/surface_energy_reference.py")
    old_e.ionic = old_i
    old_w = frozen_module(
        "old_pool_water", root / "validation/tissue/surface_energy_water_reference.py"
    )
    old_w.energy = old_e
    old = old_e if kind == "energy" else old_w
    raw = case(kind)
    allowed = (
        set(ionic.CATALOG_PERMEABILITIES)
        - set(ionic.ADDED_SODIUM_LAWS)
        - set(ionic.ADDED_POTASSIUM_LAWS)
        - set(ionic.ADDED_LEAK_LAWS)
    )
    raw["model"]["channels"] = [v for v in raw["model"]["channels"] if v["kinetic_law"] in allowed]
    names = {v["id"] for v in raw["model"]["channels"]}
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] in names
    ]
    previous = deepcopy(raw)
    previous["model"]["id"] = "resolved_energy@1" if kind == "energy" else "resolved_energy_water@1"
    if old_version:
        raw["model"]["id"] = previous["model"]["id"]
    module = MODELS[kind][0]
    c, before = module.bind(raw), old.bind(previous)
    y = state(kind, c, changed)
    actual, wanted = module.evaluate(c, y, 0), old.evaluate(before, y, 0)
    np.testing.assert_array_equal(actual[0], wanted[0])
    np.testing.assert_array_equal(actual[1], wanted[1])
    assert actual[2] == wanted[2]
    evidence(
        f"old-exact-{kind}-{old_version}-{changed}",
        dict(
            inputs=raw,
            state=y.tolist(),
            derivative=actual[0].tolist(),
            potential_V=actual[1].tolist(),
            proof=actual[2],
        ),
    )


def test_actual_regeneration_port_relaxes_to_independent_equilibrium():
    raw = case("energy")
    c = energy.bind(raw)
    port = raw["model"]["regeneration_ports"][0]
    owner = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
    initial = c["energy_initial"][:, owner]
    volume, delta = c["vi"][owner], c["energy_delta_g0"][owner]
    level = ionic.availability(c, "regeneration", port["id"], 0)
    capacity = port["capacity_fmol_per_s"] * level
    assert capacity > 0
    adenylate, ATP_plus_Pi = initial[0] + initial[1], initial[0] + initial[2]
    upper = min(adenylate, ATP_plus_Pi)

    def amount(u):
        atp = upper * expit(u)
        return np.array([atp, adenylate - atp, ATP_plus_Pi - atp])

    u0 = np.log(initial[0] / (upper - initial[0]))

    def affinity(u):
        return (
            chemistry.thermodynamics(amount(u), volume, 298.15, delta)[
                "hydrolysis_free_energy_J_mol"
            ]
            + port["supplied_energy_J_per_mol"]
        )

    equilibrium_u = brentq(affinity, -32, 32, xtol=1e-12, rtol=1e-14)
    equilibrium = amount(equilibrium_u)
    tau_s = 2 / (capacity * np.sum(1 / equilibrium))
    horizon = 2 * abs(equilibrium[0] - initial[0]) / capacity + 12 * tau_s
    times = np.linspace(0, horizon, 65)
    results = []
    for refinement in (1, 2):

        def rhs(t, y, refinement=refinement):
            n = amount(y[0])
            try:
                value = chemistry.regeneration(
                    n,
                    volume,
                    298.15,
                    delta,
                    port["capacity_fmol_per_s"],
                    port["supplied_energy_J_per_mol"],
                    level,
                )
                flow = value["synthesis_fmol_s"]
                return [
                    flow / (n[0] * (1 - n[0] / upper)),
                    flow,
                    value["dissipated_power_pJ_s"],
                    value["supplied_power_pJ_s"],
                ]
            except Exception:
                evidence(
                    "pool-relaxation-failed-state",
                    dict(
                        time_s=float(t),
                        state=y.tolist(),
                        amount_fmol=n.tolist(),
                        refinement=refinement,
                    ),
                )
                raise

        solved = solve_ivp(
            rhs,
            (0, horizon),
            [u0, 0, 0, 0],
            method="DOP853",
            t_eval=times,
            rtol=2e-11 / refinement,
            atol=np.array([1e-12, 2e-15, 2e-15, 2e-15]) / refinement,
            max_step=horizon / (32 * refinement),
        )
        assert solved.success, solved.message
        amounts = np.stack([amount(u) for u in solved.y[0]])
        energy_residual = (
            np.array(
                [
                    chemistry.free_energy_change(initial, n, volume, volume, 298.15, delta)
                    for n in amounts
                ]
            )
            + solved.y[2]
            - solved.y[3]
        )
        np.testing.assert_allclose(energy_residual, 0, rtol=0, atol=5e-11)
        np.testing.assert_allclose(amounts[:, 0] + amounts[:, 1], adenylate, rtol=0, atol=3e-18)
        np.testing.assert_allclose(
            amounts @ np.array([3, 2, 1]), initial @ np.array([3, 2, 1]), rtol=0, atol=1e-17
        )
        assert np.all(amounts > 0)
        assert (
            abs(amounts[-1, 0] - equilibrium[0])
            <= abs(initial[0] - equilibrium[0]) * np.exp(-12) + 2e-13
        )
        results.append(
            dict(
                amount_fmol=amounts.tolist(),
                state=solved.y.T.tolist(),
                energy_residual_pJ=energy_residual.tolist(),
                evaluations=solved.nfev,
            )
        )
    np.testing.assert_allclose(
        results[0]["amount_fmol"], results[1]["amount_fmol"], rtol=3e-10, atol=3e-14
    )
    evidence(
        "actual-port-relaxation",
        dict(
            port=port,
            source_pool=c["pools"][port["pool_id"]],
            volume_pL=float(volume),
            availability=level,
            times_s=times.tolist(),
            equilibrium_amount_fmol=equilibrium.tolist(),
            equilibrium_tau_s=float(tau_s),
            horizon_s=float(horizon),
            results=results,
            scope=(
                "Actual fixed-volume regeneration-only pool with pumps absent; positive logit "
                "reaction coordinate, no clipping; separate from full tissue settling"
            ),
        ),
    )


@pytest.mark.parametrize("kind", MODELS)
def test_short_coupled_refinement_and_internal_volume_work(kind):
    raw = case(kind)
    e = raw["experiment"]
    times = [0.0, 1.1e-6, 1.7e-6, 2.5e-6]
    if kind == "water":
        times.insert(1, 0.7e-6)
    e.update(end_time=2.5e-6, observation_times=times)
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                group["schedule"] = [v for v in group["schedule"] if v["time"] == 0]
    e["channel_controls"][-1]["schedule"].append(dict(time=1.1e-6, availability=0.0))
    e["regeneration_controls"][0]["schedule"].append(dict(time=1.7e-6, availability=0.0))
    if kind == "water":
        e["water_controls"][0]["schedule"].append(dict(time=0.7e-6, availability=0.0))
    module = MODELS[kind][0]
    c = module.bind(raw)
    ordinary, refined = (module.integrate(raw, refinement=r) for r in (1, 2))
    a, b = (module.unpack(c, v["state"]) for v in (ordinary, refined))
    for name in a:
        np.testing.assert_allclose(
            a[name], b[name], rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    stored, pool_residuals = [], []
    for time, y, phi in zip(
        ordinary["times"], ordinary["state"], ordinary["potential_V"], strict=True
    ):
        d, volume, ions, pools = values(kind, c, y)
        slope, _, proof = module.evaluate(c, y, time)
        accounting(kind, c, y, slope, phi, proof, time)
        physical = (
            water.evaluate(c["water_case"], volume, ions)["free_energy_pJ"]
            if kind == "water"
            else 1e-3 * ionic.R * 298.15 * np.sum(ions * (np.log(ions / volume) - 1))
        )
        internal = []
        for i in range(len(c["vi"])):
            physical += chemistry.thermodynamics(
                pools[:, i], volume[i], 298.15, c["energy_delta_g0"][i]
            )["free_energy_pJ"]
            change = chemistry.free_energy_change(
                c["energy_initial"][:, i],
                pools[:, i],
                c["vi"][i],
                volume[i],
                298.15,
                c["energy_delta_g0"][i],
            )
            transfer = sum(
                d["metabolic_work_pJ"][j]
                for j, patch in enumerate(raw["model"]["membranes"])
                if patch["inside"] == c["cell_ids"][i]
            )
            for j, port in enumerate(raw["model"]["regeneration_ports"]):
                if c["pools"][port["pool_id"]]["cell_id"] == c["cell_ids"][i]:
                    transfer += (
                        d["regeneration_dissipated_energy_pJ"][j]
                        - d["regeneration_supplied_work_pJ"][j]
                    )
            internal.append(
                change + transfer - (d["pool_volume_work_pJ"][i] if kind == "water" else 0.0)
            )
        for j, patch in enumerate(raw["model"]["membranes"]):
            i, o = (
                c["layout"]["membrane_cell"][j],
                len(c["vi"]) + c["layout"]["membrane_outside"][j],
            )
            physical += 0.5e12 * patch["capacitance_F"] * (phi[i] - phi[o]) ** 2
        stored.append(physical)
        pool_residuals.append(internal)
    heat = sum(
        value.sum(axis=tuple(range(1, value.ndim)))
        for name, value in a.items()
        if name.endswith("dissipated_energy_pJ")
    )
    residual = (
        np.asarray(stored) - stored[0] + heat - a["regeneration_supplied_work_pJ"].sum(axis=-1)
    )
    np.testing.assert_allclose(residual, 0, rtol=0, atol=3e-9)
    np.testing.assert_allclose(pool_residuals, 0, rtol=0, atol=3e-12)
    evidence(
        "short-history-" + kind,
        dict(
            inputs=raw,
            times=times,
            state=ordinary["state"].tolist(),
            refined_state=refined["state"].tolist(),
            energy_residual_pJ=residual.tolist(),
            pool_internal_residual_pJ=pool_residuals,
            evaluations=[ordinary["evaluations"], refined["evaluations"]],
            scope="2.5-us coupled wiring/refinement; component relaxation remains separate",
        ),
    )


def test_bound_component_receipts_are_separate_and_source_matched():
    root = Path(os.environ["CELLS_ML_ENERGY_COMPONENTS"])
    fuel = json.loads((root / "finite-energy-contracts.json").read_text())
    water_record = json.loads((root / "water-relaxation-handoff.json").read_text())

    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    assert fuel["status"] == "passed" and fuel["tests"]["tests"] == 80
    assert fuel["source_sha256"]["validation/chemistry/finite_energy_reference.py"] == sha(
        chemistry.__file__
    )
    assert water_record["status"] == "complete"
    assert water_record["pre_extension_source_sha256"][
        "validation/tissue/water_volume_reference.py"
    ] == sha(water.__file__)
    assert water_record["physical_results"]["isolated_water_horizon_s"] > 0.6
    assert water_record["physical_results"]["isolated_water_final_equilibrium_distance_pL"] < 1e-8


def test_no_production_imports():
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)

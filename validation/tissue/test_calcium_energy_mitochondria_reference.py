"""Independent organelle ownership, charge, physical energy and response checks."""

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from validation.organelles import betse_mitochondria_reference as native
from validation.tissue import calcium_energy_mitochondria_fixtures as fixtures
from validation.tissue import calcium_energy_mitochondria_reference as ref


def evidence(name, report, arrays=None):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)
        (path / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def case(arm="active"):
    return fixtures.definition(arm, padded=False)


def changed(c):
    y = ref.initial(c)
    slope, _, _ = ref.evaluate(c, y, 0)
    y += 1e-9 * slope
    d = ref.unpack(c, y)
    if any(v > 0 for row in c["mitochondrial_rows"] for v in row["diffusivity_m2_per_s"].values()):
        i, s = 0, c["network_species"].index("Ca")
        store = c["stores"][i]
        d["mitochondrial_amount_increment_fmol"][s, i] += 1e-5
        d["mitochondrial_transferred_fmol"][s, i] += 1e-5
        d["chemical_amount_increment"][i, store.ids.index("Ca"), store.cy] -= 1e-5
    for i in range(len(c["cell_ids"])):
        d["energy_amount_increment_fmol"][:, i] += (
            np.array([-1, 1, 1]) * 0.01 * c["energy_initial"][:, i].min()
        )
    return ref.flatten(c, d)


def separate(c, y, time=0):
    actual, phi, proof = ref.evaluate(c, y, time)
    expected, old_phi, old_proof = ref.parent.evaluate(
        c["parent"], ref.flatten(c["parent"], ref.unpack(c, y)), time
    )
    extra = ref.unpack(c, actual)
    for key, value in ref.unpack(c["parent"], expected).items():
        extra[key] -= value
    np.testing.assert_array_equal(phi, old_phi)
    return extra, phi, proof, old_proof


def test_declared_disjoint_inventories_and_full45_state():
    c = ref.bind(case())
    assert len(c["shapes"]) == 45 and tuple(c["shapes"])[-3:] == ref.EXTRA_FIELDS
    assert not any(n == "cells" or n.startswith(("cells.", "jax")) for n in sys.modules)
    d = ref.unpack(c, ref.initial(c))
    np.testing.assert_array_equal(d["chemical_amount_increment"], 0)
    np.testing.assert_array_equal(d["amount_increment"], 0)
    np.testing.assert_array_equal(
        c["mitochondrial_initial_cytosol_countercharge_C"],
        -c["mitochondrial_capacitance"] * c["mitochondrial_initial_voltage"],
    )
    q = (
        ref.F
        * 1e-15
        * np.sum(c["mitochondrial_valence"][:, None] * c["mitochondrial_initial"], axis=0)
    )
    np.testing.assert_allclose(
        q + c["mitochondrial_fixed_charge_C"] + c["mitochondrial_initial_cytosol_countercharge_C"],
        0,
        rtol=0,
        atol=2e-24,
    )
    assert np.any(
        c["mitochondrial_initial"]
        != np.stack(
            [
                store.n0[[store.ids.index(s) for s in c["network_species"]], store.cy]
                for store in c["stores"]
            ],
            axis=1,
        )
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("nonzero", [False, True])
def test_complete_stages_move_actual_chemical_ions_without_external_charge_or_atp(arm, nonzero):
    c = ref.bind(case(arm))
    y = changed(c) if nonzero else ref.initial(c)
    extra, _, proof, _ = separate(c, y)
    for key in c["parent"]["shapes"]:
        if key != "chemical_amount_increment":
            np.testing.assert_array_equal(extra[key], 0)
    flux = extra["mitochondrial_transferred_fmol"]
    np.testing.assert_array_equal(extra["mitochondrial_amount_increment_fmol"], flux)
    assert np.all(extra["mitochondrial_dissipated_energy_pJ"] >= 0)
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        expected[[store.ids.index(s) for s in c["network_species"]], store.cy] = -flux[:, i]
        np.testing.assert_allclose(
            extra["chemical_amount_increment"][i], expected, rtol=3e-12, atol=3e-14
        )
        np.testing.assert_allclose(
            np.sum(store.z[:, None] * extra["chemical_amount_increment"][i])
            + np.dot(c["mitochondrial_valence"], flux[:, i]),
            0,
            atol=3e-14,
        )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert np.max(np.abs(proof["mitochondrial_energy_balance_pJ_s"]), initial=0) < 3e-14
    if arm in ("blocked", "zero-diffusion"):
        np.testing.assert_array_equal(flux, 0)
    evidence(
        f"stage-{arm}-{nonzero}",
        dict(status="passed", state=y, proof=proof, direct_plasma_or_atp_demand=False),
        dict(extra_slope=ref.flatten(c, extra)),
    )


@pytest.mark.parametrize("arm", ["blocked", "zero-diffusion"])
def test_exact_parent_reduction_with_blocked_organelle_rates(arm):
    c = ref.bind(case(arm))
    y = ref.initial(c)
    actual, phi, _ = ref.evaluate(c, y, 0)
    expected, old_phi, _ = ref.parent.evaluate(c["parent"], ref.parent.initial(c["parent"]), 0)
    np.testing.assert_array_equal(ref.flatten(c["parent"], ref.unpack(c, actual)), expected)
    np.testing.assert_array_equal(phi, old_phi)


def test_charged_internal_transfer_changes_free_calcium_without_direct_plasma_voltage():
    c = ref.bind(case())
    y = ref.initial(c)
    old, phi, _ = ref.evaluate(c, y, 0)
    d = ref.unpack(c, y.copy())
    i = 0
    s = c["network_species"].index("Ca")
    store = c["stores"][i]
    amount = 1e-5
    d["mitochondrial_amount_increment_fmol"][s, i] = amount
    d["mitochondrial_transferred_fmol"][s, i] = amount
    d["chemical_amount_increment"][i, store.ids.index("Ca"), store.cy] -= amount
    current = ref.flatten(c, d)
    new, new_phi, proof = ref.evaluate(c, current, 0)
    membrane = c["raw"]["model"]["ionic"]["membranes"]
    cells = c["cell_ids"]
    outside = [row["id"] for row in c["raw"]["model"]["ionic"]["extracellular"]]
    def vm(potentials):
        return np.array([
            potentials[cells.index(p["inside"])]
            - potentials[len(cells) + outside.index(p["outside"])]
            for p in membrane
        ])
    np.testing.assert_allclose(vm(phi), vm(new_phi), atol=3e-14, rtol=3e-13)
    assert ref.mitochondrial_voltage(c, d)[0] > c["mitochondrial_initial_voltage"][0]
    a, b = ref.unpack(c, old), ref.unpack(c, new)
    assert np.max(np.abs(a["plasma_pump_cycles"] - b["plasma_pump_cycles"])) > 0
    # Pool demand may change through real free-Ca PMCA/ER feedback. Comparing
    # against the same changed parent state isolates zero new direct demand.
    extra, _, _, _ = separate(c, current)
    np.testing.assert_array_equal(extra["energy_amount_increment_fmol"], 0)
    assert proof["mitochondrial_direct_atp_demand_fmol_s"] == [0, 0]


def test_component_native_flux_matches_only_at_fresh_matched_voltage_and_si_constants():
    c = ref.bind(case())
    y = changed(c)
    d = ref.unpack(c, y)
    ci, _ = ref.parent._concentrations(c["parent"], d)
    cm = (c["mitochondrial_initial"] + d["mitochondrial_amount_increment_fmol"]) / c[
        "mitochondrial_volume"
    ]
    voltage = ref.mitochondrial_voltage(c, d)
    rows = c["mitochondrial_rows"]
    raw = dict(
        species_valence=c["mitochondrial_valence"].tolist(),
        moving_species=list(range(len(ci))),
        cell_volume_m3=(c["vi"] * 1e-15).tolist(),
        cell_area_m2=[2 * r["area_m2"] for r in rows],
        specific_capacitance_F_m2=rows[0]["specific_capacitance_F_per_m2"],
        membrane_thickness_m=rows[0]["membrane_thickness_m"],
        temperature_K=c["temperature"],
        faraday_C_mol=ref.F,
        gas_constant_J_mol_K=ref.R,
        cytosol_mM=ci.tolist(),
        mitochondria_mM=cm.tolist(),
        charge_C=(voltage * c["mitochondrial_capacitance"]).tolist(),
        voltage_V=voltage.tolist(),
        extra_charge_density_C_m3=(
            c["mitochondrial_fixed_charge_C"] / (c["mitochondrial_volume"] * 1e-15)
        ).tolist(),
        dt_s=0.0,
        refresh_before=False,
        diffusivity_m2_s=[
            [0.8 * r["diffusivity_m2_per_s"][s] for r in rows] for s in c["network_species"]
        ],
    )
    captured = native.evaluate(raw)
    np.testing.assert_allclose(
        captured["physical_charge_before_C"],
        voltage * c["mitochondrial_capacitance"],
        atol=3e-22,
        rtol=5e-12,
    )
    expected = (
        np.asarray(captured["flux_density_mol_m2_s"])
        * np.array([r["area_m2"] for r in rows])
        / 1e-15
    )
    rate = ref.unpack(c, ref.evaluate(c, y, 0)[0])["mitochondrial_transferred_fmol"]
    np.testing.assert_allclose(rate, expected, rtol=5e-12, atol=1e-15)
    evidence(
        "source-flux-limit",
        dict(
            status="passed",
            inputs=raw,
            independent_native_reference=captured,
            continuous_rate_fmol_s=rate,
            native_discrete_trace_equivalence=False,
            scope=("Matched fresh voltage/SI constants/geometry and current D; "
                   "no cache or Euler equivalence"),
        ),
    )


@pytest.mark.parametrize("voltage", [0.0, np.nextafter(0.0, 1.0), np.nextafter(0.0, -1.0), -1e-25])
@pytest.mark.parametrize("valence", [0, 1, -1])
def test_stable_continuous_zero_neutral_and_native_singularity_limits(voltage, valence):
    values = ref.passive_exchange(10, 20, valence, voltage, 1e-19, 5e-10, 7.5e-9, 298.15)
    expected = (10 - 20) * 1e-19 * 5e-10 / (7.5e-9 * 1e-15)
    np.testing.assert_allclose(values["flux_fmol_s"], expected, rtol=3e-14, atol=1e-20)
    assert values["dissipated_power_pJ_s"] >= 0


@pytest.mark.parametrize("arm", ["active", "reverse"])
def test_mitochondrial_endpoint_energy_directional_derivative(arm):
    c = ref.bind(case(arm))
    y = ref.initial(c)
    extra, _, _, _ = separate(c, y)
    tangent = ref.flatten(c, extra)
    heat = float(np.sum(extra["mitochondrial_dissipated_energy_pJ"]))
    derivatives = []
    for h in (2e-3, 1e-3, 5e-4):
        plus = ref.stored_energy_change(c, y + h * tangent)["total_pJ"]
        minus = ref.stored_energy_change(c, y - h * tangent)["total_pJ"]
        derivatives.append((plus - minus) / (2 * h))
    np.testing.assert_allclose(derivatives, -heat, rtol=5e-7, atol=3e-11)
    evidence(
        "directional-energy-" + arm,
        dict(
            status="passed",
            derivatives_pJ_s=derivatives,
            expected_pJ_s=-heat,
            plasma_amount_change=False,
            mitochondrial_capacitor_counted_once=True,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "identity",
        "source",
        "initialization",
        "volume_role",
        "constant",
        "missing_owner",
        "duplicate_owner",
        "zero_volume",
        "negative_diffusion",
        "missing_species",
        "zero_inventory",
        "voltage",
        "control",
    ],
)
def test_explicit_organelle_ownership_geometry_and_source_scope_guards(fault):
    raw = case()
    group = raw["model"]["mitochondria"]
    row = group["compartments"][0]
    if fault == "identity":
        raw["model"]["id"] = "resolved_calcium_energy_transport@1"
    elif fault == "source":
        group["law"] = group["source_law"]
    elif fault == "initialization":
        group["initialization"] = "copy_cytosol"
    elif fault == "volume_role":
        group["cytosol_volume_role"] = "whole_cell_volume"
    elif fault == "constant":
        group["constants"]["faraday_C_mol"] = 96485.0
    elif fault == "missing_owner":
        group["compartments"].pop()
    elif fault == "duplicate_owner":
        group["compartments"][1]["cell_id"] = row["cell_id"]
    elif fault == "zero_volume":
        row["volume_pL"] = 0
    elif fault == "negative_diffusion":
        row["diffusivity_m2_per_s"]["Ca"] = -1e-19
    elif fault == "missing_species":
        row["initial_amount_fmol"].pop("Ca")
    elif fault == "zero_inventory":
        row["initial_amount_fmol"]["Ca"] = 0
    elif fault == "voltage":
        row["initial_voltage_V"] = 0.20001
    else:
        raw["experiment"]["mitochondria_controls"][0]["schedule"][0]["availability"] = 1.1
    with pytest.raises(ValueError):
        ref.bind(raw)


@pytest.mark.parametrize("fault", ["depleted", "voltage", "nan", "negative_heat"])
def test_bad_live_organelle_state_rejected_even_when_blocked(fault):
    c = ref.bind(case("blocked"))
    d = ref.unpack(c, ref.initial(c))
    if fault == "depleted":
        d["mitochondrial_amount_increment_fmol"][0, 0] = -c["mitochondrial_initial"][0, 0]
    elif fault == "voltage":
        d["mitochondrial_amount_increment_fmol"][0, 0] = 1
    elif fault == "nan":
        d["mitochondrial_transferred_fmol"][0, 0] = np.nan
    else:
        d["mitochondrial_dissipated_energy_pJ"][0, 0] = -1
    with pytest.raises(ValueError):
        ref.evaluate(c, ref.flatten(c, d), 0)


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_fixture_clock_boundaries_and_right_continuous_organelle_control(arm):
    raw = fixtures.compact_probe(arm)
    e = raw["experiment"]
    dt = raw["execution"]["dt"]
    events = {0.0, e["end_time"]}
    for name, groups in e.items():
        if name.endswith("_controls"):
            events.update(
                v["time"] for row in groups for v in row.get("schedule", row.get("controls", []))
            )
    assert all(t == round(t / dt) * dt or t in events for t in e["observation_times"])
    c = ref.bind(raw)
    y = ref.initial(c)
    before = ref.unpack(c, ref.evaluate(c, y, 12.7e-6 - 1e-12)[0])
    after = ref.unpack(c, ref.evaluate(c, y, 12.7e-6)[0])
    np.testing.assert_array_equal(after["mitochondrial_transferred_fmol"][:, 0], 0)
    if arm not in ("blocked", "zero-diffusion"):
        assert np.any(before["mitochondrial_transferred_fmol"][:, 0] != 0)
    for key in (
        "amount_increment",
        "extracellular_amount_increment",
        "energy_amount_increment_fmol",
    ):
        np.testing.assert_array_equal(before[key], after[key])


def test_actual_rate_reduced_charged_pair_relaxes_for_twelve_tau_with_refinement():
    c = ref.bind(case())
    row = c["mitochondrial_rows"][0]
    s = c["network_species"].index("K")
    store = c["stores"][0]
    nc = store.n0[store.ids.index("K"), store.cy]
    nm = c["mitochondrial_initial"][s, 0]
    vc, vm = c["vi"][0], row["volume_pL"]
    cap = c["mitochondrial_capacitance"][0]
    v0 = row["initial_voltage_V"]
    z = int(c["mitochondrial_valence"][s])
    kappa = z * ref.F * 1e-15 / cap

    def values(extent):
        return ref.passive_exchange(
            (nc - extent) / vc,
            (nm + extent) / vm,
            z,
            v0 + kappa * extent,
            row["diffusivity_m2_per_s"]["K"],
            row["area_m2"],
            row["membrane_thickness_m"],
            298.15,
            0.8,
        )

    lower = max(-nm * 0.999, (-0.199 - v0) / kappa)
    upper = min(nc * 0.999, (0.199 - v0) / kappa)
    equilibrium = brentq(lambda x: values(x)["transfer_energy_J_mol"], lower, upper, xtol=1e-15)
    voltage = v0 + kappa * equilibrium
    x = z * ref.F * voltage / (ref.R * 298.15)
    b = 1 if x == 0 else x / math.expm1(x)
    amplitude = (
        row["diffusivity_m2_per_s"]["K"]
        * row["area_m2"]
        * 0.8
        / (row["membrane_thickness_m"] * 1e-15)
        * (nc - equilibrium)
        / vc
        * b
    )
    mu_derivative = (
        ref.R * 298.15 * (1 / (nc - equilibrium) + 1 / (nm + equilibrium)) + z * ref.F * kappa
    )
    tau = ref.R * 298.15 / (amplitude * mu_derivative)
    horizon = 12 * tau
    outputs = []
    for refinement in (1, 2):

        def rhs(t, y):
            value = values(float(y[0]))
            return [value["flux_fmol_s"], value["dissipated_power_pJ_s"]]

        solution = solve_ivp(
            rhs,
            (0, horizon),
            [0.0, 0.0],
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=2e-14 / refinement,
            max_step=tau / (16 * refinement),
        )
        assert solution.success
        extent, heat = solution.y[:, -1]
        chemical = 0.0
        for n, v, delta in ((nc, vc, -extent), (nm, vm, extent)):
            chemical += (
                1e-3
                * ref.R
                * 298.15
                * (delta * (math.log(n / v) - 1) + (n + delta) * math.log1p(delta / n))
            )
        electrical = 0.5e12 * cap * (kappa * extent) * (2 * v0 + kappa * extent)
        assert abs(chemical + electrical + heat) < 3e-11
        assert abs(extent - equilibrium) < abs(equilibrium) * 1e-5
        outputs.append(
            dict(
                refinement=refinement,
                final=solution.y[:, -1].tolist(),
                energy_residual_pJ=chemical + electrical + heat,
                evaluations=solution.nfev,
            )
        )
    np.testing.assert_allclose(outputs[0]["final"], outputs[1]["final"], rtol=2e-10, atol=3e-12)
    evidence(
        "actual-charged-pair-relaxation",
        dict(
            status="passed",
            tau_s=tau,
            horizon_s=horizon,
            equilibrium_extent_fmol=equilibrium,
            initial_voltage_V=v0,
            eq_voltage_V=voltage,
            geometry=row,
            physical_diffusivity_unchanged=True,
            outputs=outputs,
            scope=("Actual K route and finite owner volumes/capacitance; "
                   "other routes held off, not full-cell settling"),
        ),
    )


def test_full45_fifty_microsecond_refinement_and_endpoint_energy():
    raw = fixtures.compact_probe()
    c = ref.bind(raw)
    results = [ref.integrate(raw, refinement=r, max_step_s=5e-6) for r in (1, 2)]
    residuals = []
    for result in results:
        assert {12.7e-6, 31.7e-6, 15 * raw["execution"]["dt"]} <= set(result["event_times"])
        residuals.append(
            [
                ref.endpoint_balance(c, y, time=t)["balance_pJ"]
                for t, y in zip(result["times"], result["state"], strict=True)
            ]
        )
        assert max(map(abs, residuals[-1])) < 3e-9
        for state in result["state"]:
            d = ref.unpack(c, state)
            np.testing.assert_array_equal(
                d["mitochondrial_amount_increment_fmol"], d["mitochondrial_transferred_fmol"]
            )
    np.testing.assert_allclose(results[0]["state"], results[1]["state"], rtol=2e-8, atol=3e-11)
    evidence(
        "full45-short-refinement",
        dict(
            status="passed",
            duration_s=raw["experiment"]["end_time"],
            fields=45,
            event_times=results[0]["event_times"],
            energy_residuals_pJ=residuals,
            evaluations=[r["evaluations"] for r in results],
            settling_claim=False,
        ),
        dict(
            time_s=np.asarray(results[0]["times"]),
            state=results[0]["state"],
            refined_state=results[1]["state"],
        ),
    )

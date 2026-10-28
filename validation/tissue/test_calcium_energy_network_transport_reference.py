"""Independent material, charge, work and live-owner checks for native transport."""

import ast
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from validation.tissue import calcium_energy_network_transport_fixtures as fixtures
from validation.tissue import calcium_energy_network_transport_reference as ref
from validation.transport import betse_network_transport_reference as native


def evidence(name, report, arrays=None):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(target / (name + ".npz"), **arrays)
        (target / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda value: value.tolist())
            + "\n"
        )


def case(arm="active"):
    return fixtures.definition(arm, padded=False)


def changed(c):
    state = ref.initial(c)
    slope, _, _ = ref.evaluate(c, state, 0)
    state += 1e-9 * slope
    d = ref.unpack(c, state)
    for i, store in enumerate(c["stores"]):
        d["energy_amount_increment_fmol"][:, i] += (
            np.array([-1, 1, 1]) * 0.02 * c["energy_initial"][:, i].min()
        )
        d["chemical_amount_increment"][
            i, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
        ] += np.array([-1, -1, 1]) * 1e-4
    return ref.flatten(c, d)


def transport_only(c, state, time=0):
    slope, phi, proof = ref.evaluate(c, state, time)
    base, old_phi, old_proof = ref.energy.evaluate(
        c["energy"], ref.flatten(c["energy"], ref.unpack(c, state)), time
    )
    base_fields = ref.unpack(c["energy"], base)
    result = ref.unpack(c, slope)
    for key in base_fields:
        result[key] -= base_fields[key]
    np.testing.assert_array_equal(phi, old_phi)
    return result, phi, proof, old_proof


def test_independent_api_and_complete_state_order():
    c = ref.bind(case())
    assert len(c["shapes"]) == 42
    assert tuple(c["shapes"])[-4:] == ref.EXTRA_FIELDS
    assert fixtures.F == ref.F and fixtures.R == ref.R
    assert c["network_nu"].shape == (4, 4)
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
    for module in (fixtures, ref):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("nonzero", [False, True])
def test_full42_stages_conserve_owned_species_charge_and_all_work(arm, nonzero):
    raw, c = case(arm), ref.bind(case(arm))
    state = changed(c) if nonzero else ref.initial(c)
    slope, _, proof = ref.evaluate(c, state, 0)
    d, extra, _, _ = transport_only(c, state)
    del extra
    full = ref.unpack(c, slope)
    species = c["network_species"]
    cell, outer = (
        np.zeros_like(d["amount_increment"]),
        np.zeros_like(d["extracellular_amount_increment"]),
    )
    for j, (i, o) in enumerate(c["network_owners"]):
        cell[:, i] -= d["network_transferred_fmol"][:, j]
        outer[:, o] += d["network_transferred_fmol"][:, j]
    np.testing.assert_allclose(
        d["network_transferred_fmol"],
        c["network_nu"] * d["network_cycles_fmol"],
        atol=1e-13,
        rtol=3e-14,
    )
    np.testing.assert_allclose(d["amount_increment"], cell, atol=3e-13, rtol=3e-13)
    np.testing.assert_allclose(d["extracellular_amount_increment"], outer, atol=3e-13, rtol=3e-13)
    np.testing.assert_allclose(cell.sum(axis=1) + outer.sum(axis=1), 0, atol=3e-13)
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        expected[[store.ids.index(s) for s in species], store.cy] = cell[:, i]
        np.testing.assert_allclose(
            d["chemical_amount_increment"][i], expected, rtol=3e-13, atol=3e-13
        )
    for key in (
        "energy_amount_increment_fmol",
        "er_pump_transferred",
        "er_metabolic_work_pJ",
        "regeneration_cycles_fmol",
    ):
        np.testing.assert_array_equal(d[key], 0)
    scale = np.sum(np.abs(full["network_dissipated_energy_pJ"])) + np.sum(
        np.abs(full["network_supplied_work_pJ"])
    )
    budget = 3e-10 + 32 * np.finfo(float).eps * scale
    assert abs(proof["physical_energy_balance_pJ_s"]) < budget
    assert np.max(np.abs(proof["network_energy_balance_pJ_s"]), initial=0) < budget
    assert np.all(full["network_dissipated_energy_pJ"] >= 0)
    if arm in ("blocked", "empty"):
        for field in ref.EXTRA_FIELDS:
            np.testing.assert_array_equal(d[field], 0)
    evidence(
        f"stage-{arm}-{nonzero}",
        dict(status="passed", inputs=raw, state=state, proof=proof, energy_budget_pJ_s=budget),
        dict(slope=slope),
    )


@pytest.mark.parametrize("arm", ["blocked", "empty"])
def test_exact_parent_reduction_when_network_is_blocked_or_absent(arm):
    c = ref.bind(case(arm))
    state = ref.initial(c)
    actual, phi, _ = ref.evaluate(c, state, 0)
    expected, old_phi, _ = ref.energy.evaluate(c["energy"], ref.energy.initial(c["energy"]), 0)
    np.testing.assert_array_equal(ref.flatten(c["energy"], ref.unpack(c, actual)), expected)
    np.testing.assert_array_equal(phi, old_phi)


def test_route_species_and_product_reordering_preserve_physical_rates():
    a, b = (ref.bind(case(arm)) for arm in ("active", "reordered"))
    da, pa, _ = ref.evaluate(a, ref.initial(a), 0)
    db, pb, _ = ref.evaluate(b, ref.initial(b), 0)
    va, vb = ref.unpack(a, da), ref.unpack(b, db)
    indices = [b["network_species"].index(s) for s in a["network_species"]]
    routes = [b["network_ids"].index(s) for s in a["network_ids"]]
    for key in ("amount_increment", "extracellular_amount_increment"):
        np.testing.assert_allclose(va[key], vb[key][indices], rtol=3e-13, atol=3e-13)
    np.testing.assert_allclose(
        va["network_transferred_fmol"],
        vb["network_transferred_fmol"][indices][:, routes],
        rtol=3e-13,
        atol=3e-13,
    )
    np.testing.assert_allclose(
        va["chemical_amount_increment"], vb["chemical_amount_increment"], rtol=3e-13, atol=3e-13
    )
    np.testing.assert_allclose(pa, pb, atol=2e-13, rtol=2e-12)


def test_free_cytosol_sensing_excludes_bound_calcium_and_er_inventory():
    c = ref.bind(case())
    initial = ref.initial(c)
    baseline = ref.unpack(c, ref.evaluate(c, initial, 0)[0])["network_cycles_fmol"]
    store = c["stores"][0]
    # Equal-charge Ca + B -> CaB leaves plasma charge fixed but reduces free Ca.
    for owner, should_change in ((store.cy, True), (store.er, False)):
        d = ref.unpack(c, initial.copy())
        d["chemical_amount_increment"][
            0, [store.ids.index(v) for v in ("Ca", "B", "CaB")], owner
        ] += np.array([-1, -1, 1]) * 1e-4
        actual = ref.unpack(c, ref.evaluate(c, ref.flatten(c, d), 0)[0])["network_cycles_fmol"]
        if should_change:
            assert abs(actual[1] - baseline[1]) > 1e-5
        else:
            np.testing.assert_array_equal(actual, baseline)
    # Bound amount alone has no concentration role in any declared transporter.
    d = ref.unpack(c, initial.copy())
    d["chemical_amount_increment"][0, store.ids.index("CaB"), store.cy] += 1e-4
    actual = ref.unpack(c, ref.evaluate(c, ref.flatten(c, d), 0)[0])["network_cycles_fmol"]
    np.testing.assert_array_equal(actual, baseline)


def test_maintained_transporter_drive_is_separate_from_finite_atp_demand():
    c = ref.bind(case())
    d, _, proof, _ = transport_only(c, ref.initial(c))
    route = c["raw"]["model"]["network_transport"]["routes"][2]
    np.testing.assert_allclose(
        d["network_supplied_work_pJ"][2], 1e-3 * 6000 * d["network_cycles_fmol"][2], rtol=1e-14
    )
    np.testing.assert_array_equal(d["energy_amount_increment_fmol"], 0)
    assert route["drive"]["supplied_energy_J_per_mol"] == 6000
    assert proof["network_direct_atp_demand_fmol_s"] == [0, 0]


@pytest.mark.parametrize("arm", ["active", "reverse", "zero-drive"])
def test_endpoint_energy_directional_derivative_counts_no_internal_pump_work_twice(arm):
    c = ref.bind(case(arm))
    y = ref.initial(c)
    extra, _, _, _ = transport_only(c, y)
    tangent = ref.flatten(c, extra)
    work = np.sum(extra["network_supplied_work_pJ"])
    heat = np.sum(extra["network_dissipated_energy_pJ"])
    # Choose perturbations by amount/charge domain, not a changed physical rate.
    scale = max(1.0, np.max(np.abs(extra["network_cycles_fmol"]), initial=0))
    steps = [1e-6 / scale, 5e-7 / scale, 2.5e-7 / scale]
    estimates = []
    for h in steps:
        plus = ref.stored_energy_change(c, y + h * tangent)["total_pJ"]
        minus = ref.stored_energy_change(c, y - h * tangent)["total_pJ"]
        estimates.append((plus - minus) / (2 * h))
    expected = work - heat
    np.testing.assert_allclose(estimates, expected, rtol=3e-7, atol=3e-7)
    evidence(
        "directional-energy-" + arm,
        dict(
            status="passed",
            steps_s=steps,
            estimates_pJ_s=estimates,
            expected_pJ_s=float(expected),
            direct_pool_demand=False,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "constant",
        "accounting",
        "irreversible",
        "conversion",
        "duplicate",
        "no_transfer",
        "ignore_ecm",
        "profile",
        "drive",
        "owner",
        "capacity",
        "control",
        "inner_version",
    ],
)
def test_unsupported_physical_ledger_declarations_rejected(fault):
    raw = case()
    group = raw["model"]["network_transport"]
    row = group["routes"][0]
    config = row["configuration"]
    if fault == "constant":
        group["constants"]["faraday_C_mol"] = 96485.33212
    elif fault == "accounting":
        group["accounting"] = "source_diagnostic_only"
    elif fault == "irreversible":
        config["standard free energy"] = None
    elif fault == "conversion":
        config["product multipliers"][0] = 2
    elif fault == "duplicate":
        config["reactants"].append("K")
        config["reactant multipliers"].append(1)
        config["Km reactants"].append(1)
    elif fault == "no_transfer":
        config["transfered into cell"] = []
    elif fault == "ignore_ecm":
        config["ignore ECM"] = True
    elif fault == "profile":
        config["apply to"] = ["tissue_1"]
    elif fault == "drive":
        row["drive"]["supplied_energy_J_per_mol"] = 1
    elif fault == "owner":
        row["membrane_id"] = "missing"
    elif fault == "capacity":
        raw["execution"]["network_transport_capacity"] = True
    elif fault == "control":
        raw["experiment"]["network_transport_controls"][0]["schedule"].append(
            dict(time=0, availability=0)
        )
    else:
        raw["model"]["ionic"]["id"] = "resolved_tissue@11"
    with pytest.raises(ValueError):
        ref.bind(raw)


@pytest.mark.parametrize("blocked", [False, True])
def test_negative_regulation_rejected_even_when_blocked(blocked):
    raw = case("blocked" if blocked else "active")
    config = raw["model"]["network_transport"]["routes"][0]["configuration"]
    config.update({"transporter inhibitors": ["Na&"], "inhibitor Km": [1.0], "inhibitor n": [1.0]})
    c = ref.bind(raw)
    with pytest.raises(ValueError, match="nonnegative native regulation"):
        ref.evaluate(c, ref.initial(c), 0)


def test_right_continuous_route_only_events_and_unrelated_parent_rates():
    raw = fixtures.compact_probe()
    c, state = ref.bind(raw), ref.initial(ref.bind(raw))
    snapshots = []
    for time in (13.3e-6 - 1e-12, 13.3e-6, 31.1e-6 - 1e-12, 31.1e-6):
        snapshots.append(ref.unpack(c, ref.evaluate(c, state, time)[0]))
    assert snapshots[0]["network_cycles_fmol"][2] != 0
    assert snapshots[1]["network_cycles_fmol"][2] == snapshots[2]["network_cycles_fmol"][2] == 0
    assert snapshots[3]["network_cycles_fmol"][2] != 0
    for key in ("channel_gate", "pump_cycles", "plasma_pump_cycles", "er_pump_transferred"):
        np.testing.assert_array_equal(snapshots[0][key], snapshots[1][key])


def test_actual_rate_reduced_electroneutral_relaxation_through_twelve_tau():
    raw = case()
    row = raw["model"]["network_transport"]["routes"][0]
    ion = raw["model"]["ionic"]
    patch = ion["membranes"][0]
    inside, outside = ion["cells"][0], ion["extracellular"][0]
    initial_i, initial_o = inside["initial_amount_fmol"], outside["initial_amount_fmol"]
    vi, vo = inside["volume_pL"], outside["volume_pL"]
    z = {s["id"]: s["valence"] for s in ion["species"]}

    def concentrations(extent):
        ci, co = (
            {s: a / vi for s, a in initial_i.items()},
            {s: a / vo for s, a in initial_o.items()},
        )
        for s in ("K", "Cl"):
            ci[s] += extent / vi
            co[s] -= extent / vo
        return ci, co

    def law(extent):
        ci, co = concentrations(extent)
        return native.evaluate(
            row["configuration"],
            ci,
            co,
            z,
            voltage_V=-0.080,
            temperature_K=298.15,
            area_m2=patch["area_m2"],
            availability=0.8,
            rho=row["density_multiplier"],
        )

    equilibrium = brentq(
        lambda x: law(x)["source_reaction_energy_J_mol"],
        -0.999 * min(initial_i[s] for s in ("K", "Cl")),
        0.999 * min(initial_o[s] for s in ("K", "Cl")),
        xtol=2e-14,
    )
    ci, co = concentrations(equilibrium)
    slope_log = sum(1 / (ci[s] * vi) + 1 / (co[s] * vo) for s in ("K", "Cl"))
    prefactor = (
        row["configuration"]["max rate"]
        * patch["area_m2"]
        / 1e-15
        * 0.8
        * row["density_multiplier"]
    )
    tau = 1 / (prefactor * law(equilibrium)["forward_saturation"] * slope_log)
    horizon = 12 * tau
    outputs = []
    for refinement in (1, 2):

        def rhs(time, y):
            rate = law(float(y[0]))
            return [
                rate["extent_fmol_s"],
                -1e-3 * rate["extent_fmol_s"] * rate["source_reaction_energy_J_mol"],
            ]

        solved = solve_ivp(
            rhs,
            (0, horizon),
            [0.0, 0.0],
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=2e-14 / refinement,
            max_step=tau / (16 * refinement),
            dense_output=True,
        )
        assert solved.success
        final = solved.y[:, -1]
        ci, co = concentrations(final[0])
        change = 0.0
        for s in ("K", "Cl"):
            for amount, volume, delta in (
                (initial_i[s], vi, final[0]),
                (initial_o[s], vo, -final[0]),
            ):
                after = amount + delta
                change += (
                    1e-3
                    * ref.R
                    * 298.15
                    * (delta * (math.log(amount / volume) - 1) + after * math.log1p(delta / amount))
                )
        assert abs(change + final[1]) < 3e-10
        assert abs(final[0] - equilibrium) < 3e-4
        assert solved.t[-1] == horizon and min(*ci.values(), *co.values()) > 0
        outputs.append(
            dict(
                refinement=refinement,
                final=final.tolist(),
                energy_residual_pJ=change + final[1],
                evaluations=solved.nfev,
            )
        )
    np.testing.assert_allclose(outputs[0]["final"], outputs[1]["final"], rtol=3e-11, atol=3e-11)
    evidence(
        "actual-route-reduced-relaxation",
        dict(
            status="passed",
            route=row,
            tau_s=tau,
            horizon_s=horizon,
            equilibrium_extent_fmol=equilibrium,
            physical_rates_unchanged=True,
            scope=(
                "Actual K/Cl route in its finite owner pair; "
                "electrogenic/channel/ER/fuel settling excluded"
            ),
            outputs=outputs,
        ),
    )


def test_full42_short_refinement_and_all_event_boundaries():
    raw = fixtures.compact_probe()
    # Full short probe is 50 us; this bounded pair targets the initial coupling
    # and off-grid event semantics without claiming all channels have settled.
    results = [ref.integrate(raw, refinement=r, max_step_s=5e-6) for r in (1, 2)]
    c = ref.bind(raw)
    residuals = []
    for result in results:
        assert 13.3e-6 in result["event_times"] and 31.1e-6 in result["event_times"]
        assert 15 * raw["execution"]["dt"] in result["event_times"]
        residuals.append(
            [
                ref.endpoint_balance(c, state, time=time)["balance_pJ"]
                for time, state in zip(result["times"], result["state"], strict=True)
            ]
        )
        assert max(map(abs, residuals[-1])) < 3e-9
    difference = np.abs(results[0]["state"] - results[1]["state"])
    np.testing.assert_allclose(results[0]["state"], results[1]["state"], rtol=2e-8, atol=3e-11)
    evidence(
        "full42-short-refinement",
        dict(
            status="passed",
            duration_s=raw["experiment"]["end_time"],
            state_fields=42,
            event_times=results[0]["event_times"],
            residuals_pJ=residuals,
            max_difference=float(difference.max()),
            evaluations=[r["evaluations"] for r in results],
            settling_claim=False,
        ),
        {
            "time_s": np.asarray(results[0]["times"]),
            "state": results[0]["state"],
            "refined_state": results[1]["state"],
        },
    )


def test_failed_reference_stage_retains_complete_state(monkeypatch):
    raw = fixtures.compact_probe()

    def invalid(*args, **kwargs):
        raise ValueError("synthetic retained failure")

    monkeypatch.setattr(ref, "evaluate", invalid)
    with pytest.raises(ref.ReferenceIntegrationError) as caught:
        ref.integrate(raw)
    diagnostic = caught.value.diagnostics
    assert len(diagnostic["state"]) == len(ref.initial(ref.bind(raw)))
    assert diagnostic["evaluations"] == 1 and diagnostic["automatic_retry"] is False
    evidence("injected-stage-failure", dict(status="expected_rejection", **diagnostic))


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_probe_fixture_clocks_are_exact_grid_or_declared_events(arm):
    """Data-only planning contract; no model bind, field solve or integration."""
    raw = fixtures.compact_probe(arm)
    e, dt = raw["experiment"], raw["execution"]["dt"]
    events = {0.0, e["end_time"]}
    for kind, groups in e.items():
        if kind.endswith("_controls"):
            events.update(
                change["time"]
                for group in groups
                for change in group.get("schedule", group.get("controls", []))
            )
    assert all(time == round(time / dt) * dt or time in events for time in e["observation_times"])
    assert e["end_time"] == 40 * dt
    assert all(
        a < b for a, b in zip(e["observation_times"][:-1], e["observation_times"][1:], strict=True)
    )
    off_grid = {13.3e-6, 31.1e-6}
    if arm == "empty":
        assert e["network_transport_controls"] == []
        assert off_grid.isdisjoint(e["observation_times"])
    else:
        route = next(
            row for row in e["network_transport_controls"] if row["transporter_id"] == "na_drive"
        )
        assert [change["time"] for change in route["schedule"]] == [0.0, 13.3e-6, 31.1e-6]
        assert off_grid <= set(e["observation_times"]) & events
        if arm == "blocked":
            assert all(
                change["availability"] == 0
                for row in e["network_transport_controls"]
                for change in row["schedule"]
            )
    evidence(
        "fixture-clocks-" + arm,
        dict(status="passed", inputs=raw, event_times=sorted(events), data_only=True),
    )

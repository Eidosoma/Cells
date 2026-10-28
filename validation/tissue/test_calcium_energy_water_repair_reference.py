"""Independent prescribed-repair checks on the joint finite-fuel/water graph."""

import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import calcium_energy_water_reference as parent
from validation.tissue import calcium_energy_water_repair_reference as ref
from validation.tissue import surface_reference as transport
from validation.tissue.test_calcium_energy_reference import ownership_checks
from validation.tissue.test_calcium_energy_water_reference import accounting as parent_accounting
from validation.tissue.test_calcium_energy_water_reference import changed as parent_changed

pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_ENERGY_WATER_REPAIR_INPUTS" not in os.environ,
    reason="Require frozen raw serialized joint prescribed-repair inputs",
)


def inputs():
    directory = os.environ.get("CELLS_CALCIUM_ENERGY_WATER_REPAIR_INPUTS")
    if not directory:
        return {}
    result = {}
    for path in sorted(Path(directory).glob("*.json")):
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and raw.get("model", {}).get("id") == ref.MODEL_ID:
            result[path.stem] = raw
    return result


def case(arm="preinjured"):
    return deepcopy(next(value for name, value in inputs().items() if name.startswith(arm + "-")))


def evidence(name, value):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def test_smoke_48field_joint_repair_reference():
    raw = case()
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    assert len(c["shapes"]) == 48 and len(c["parent"]["shapes"]) == 43
    assert np.isfinite(slope).all() and np.isfinite(phi).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert proof["structural_repair_energy"] == "not modelled"
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
    fields = ref.unpack(c, ref.initial(c))
    fields.update(parent.unpack(c["parent"], parent_changed(c["parent"])))
    fields["damage"][0] += 0.125
    fields["damage_opened"][0] += 0.125
    return ref.flatten(c, fields)


def checks(c, y, slope, time, proof):
    fields, rates = ref.unpack(c, y), ref.unpack(c, slope)
    base, phi, _ = parent.evaluate(c["parent"], parent.flatten(c["parent"], fields), time)
    prior = parent.unpack(c["parent"], base)
    affected = {"amount_increment", "extracellular_amount_increment", "chemical_amount_increment"}
    for key in c["parent"]["shapes"]:
        if key not in affected:
            np.testing.assert_array_equal(rates[key], prior[key])
    # In particular, pore opening has no direct ATP or regeneration demand and
    # no direct water/gate displacement at a fixed physical stage.
    result = parent_accounting(
        c["parent"], parent.flatten(c["parent"], fields), parent.flatten(c["parent"], rates), proof
    )
    volume = parent.volumes(c["parent"], fields)
    delta_i, delta_o = (
        np.zeros_like(rates["amount_increment"]),
        np.zeros_like(rates["extracellular_amount_increment"]),
    )
    delta_chemical = np.zeros_like(rates["chemical_amount_increment"])
    flux_budget = []
    for j, patch in enumerate(c["injury"]):
        i, o = c["layout"]["membrane_cell"][j], c["layout"]["membrane_outside"][j]
        store = c["stores"][i]
        vm = phi[i] - phi[len(c["vi"]) + o]
        for s, ion in enumerate(c["raw"]["model"]["ionic"]["species"]):
            index = store.ids.index(ion["id"])
            ci = (store.n0 + fields["chemical_amount_increment"][i])[index, store.cy] / volume[i]
            co = (c["ao"][s, o] + fields["extracellular_amount_increment"][s, o]) / volume[
                len(c["vi"]) + o
            ]
            flux = transport.decimal_flux(
                ci,
                co,
                vm,
                ion["valence"],
                c["temperature"],
                c["layout"]["membrane_area"][j],
                patch["permeability_m_per_s"][ion["id"]],
                1.0,
                fields["damage"][j],
                {"R": ref.R, "F": ref.F},
            )
            np.testing.assert_allclose(
                rates["injury_transferred"][s, j], flux, atol=3e-15, rtol=3e-14
            )
            delta_i[s, i] -= flux
            delta_o[s, o] += flux
            delta_chemical[i, index, store.cy] -= flux
            if patch["permeability_m_per_s"][ion["id"]] == 0:
                assert (
                    rates["injury_transferred"][s, j]
                    == rates["injury_dissipated_energy_pJ"][s, j]
                    == 0
                )
            flux_budget.append(float(abs(rates["injury_transferred"][s, j] - flux)))
    for key, expected in (
        ("amount_increment", delta_i),
        ("extracellular_amount_increment", delta_o),
        ("chemical_amount_increment", delta_chemical),
    ):
        np.testing.assert_allclose(rates[key] - prior[key], expected, atol=3e-13, rtol=3e-13)
    for inside, outside in zip(delta_i, delta_o, strict=True):
        assert abs(math.fsum(inside) + math.fsum(outside)) < 3e-14
    np.testing.assert_allclose(
        rates["damage"] - rates["damage_opened"] + rates["damage_closed"], 0, rtol=0, atol=3e-12
    )
    assert rates["injury_dissipated_energy_pJ"].min(initial=0) >= -3e-14
    assert abs(proof["injury_energy_balance_pJ_s"]) < 3e-12
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    result["max_decimal_lesion_flux_error_fmol_s"] = max(flux_budget, default=0)
    return result


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("perturbed", [False, True])
def test_frozen_48field_stages_and_joint_lesion_accounting(name, perturbed):
    raw = inputs()[name]
    c = ref.bind(raw)
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
    record["checks"] = checks(c, y, slope, 0.0, proof)
    evidence(f"stage-{name}-{perturbed}", record)


@pytest.mark.parametrize("arm", ["sham", "uninjured"])
def test_no_lesion_is_exact_parent_without_inventory_resets(arm):
    c = ref.bind(case(arm))
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    expected, wanted, _ = parent.evaluate(c["parent"], parent.initial(c["parent"]), 0.0)
    np.testing.assert_array_equal(parent.flatten(c["parent"], ref.unpack(c, slope)), expected)
    np.testing.assert_array_equal(phi, wanted)
    assert all(not np.any(ref.unpack(c, slope)[key]) for key in ref.EXTRA_FIELDS)
    assert proof["direct_structural_atp_demand_fmol_s"] == 0.0
    np.testing.assert_array_equal(y, ref.initial(c))


def test_open_lesion_survives_ordinary_route_blocking_and_source_switches():
    raw = case()
    c = ref.bind(raw)
    y = ref.initial(c)
    before, _, _ = ref.evaluate(c, y, 0.0)
    blocked = deepcopy(raw)
    for kind in ("membrane_controls", "channel_controls"):
        for row in blocked["experiment"][kind]:
            row["schedule"] = [dict(time=0.0, availability=0.0)]
    for row in blocked["experiment"]["injury_controls"]:
        row["schedule"] = [dict(time=0.0, injury=0.0, resealing=0.0)]
    b = ref.bind(blocked)
    after, _, _ = ref.evaluate(b, ref.initial(b), 0.0)
    a, z = ref.unpack(c, before), ref.unpack(b, after)
    np.testing.assert_allclose(
        a["injury_transferred"], z["injury_transferred"], atol=3e-15, rtol=3e-12
    )
    assert np.count_nonzero(z["injury_transferred"]) == 2
    assert z["damage"][0] == 0 and a["damage"][0] < 0


@pytest.mark.parametrize(
    "fault",
    [
        "damage_low",
        "damage_high",
        "ledger",
        "negative_heat",
        "negative_opened",
        "ca_transfer",
        "ca_heat",
        "nonfinite",
        "size",
    ],
)
def test_invalid_injury_history_rejects_with_injury_controls_off(fault):
    raw = case()
    for row in raw["experiment"]["injury_controls"]:
        row["schedule"] = [dict(time=0.0, injury=0.0, resealing=0.0)]
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    if fault in ("damage_low", "damage_high"):
        d["damage"][0] = -0.1 if fault == "damage_low" else 1.1
    elif fault == "ledger":
        d["damage_opened"][0] = 0.1
    elif fault in ("negative_heat", "negative_opened"):
        d["injury_dissipated_energy_pJ" if fault == "negative_heat" else "damage_opened"].flat[
            0
        ] = -1.0
    elif fault in ("ca_transfer", "ca_heat"):
        s = [v["id"] for v in raw["model"]["ionic"]["species"]].index("Ca")
        d["injury_transferred" if fault == "ca_transfer" else "injury_dissipated_energy_pJ"][
            s, 0
        ] = 1e-20
    else:
        d["damage"][0] = np.nan if fault == "nonfinite" else d["damage"][0]
    y = ref.flatten(c, d)
    with pytest.raises(ValueError):
        ref.evaluate(c, y[:-1] if fault == "size" else y, 0.0)


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_law",
        "ca_route",
        "negative_perm",
        "nan_rate",
        "boolean_rate",
        "damage",
        "missing_patch",
        "duplicate_patch",
        "duplicate_time",
        "nonzero_start",
        "bad_control",
        "hidden_atp_cost",
    ],
)
def test_strict_prescribed_repair_contract(fault):
    raw = case()
    row = raw["model"]["injury_patches"][0]
    control = raw["experiment"]["injury_controls"][0]["schedule"]
    if fault == "wrong_law":
        row["law"] = "native_measured_repair@1"
    elif fault in ("ca_route", "negative_perm"):
        row["permeability_m_per_s"]["Ca" if fault == "ca_route" else "Na"] = (
            1e-8 if fault == "ca_route" else -1e-8
        )
    elif fault in ("nan_rate", "boolean_rate"):
        row["injury_rate_per_s"] = np.nan if fault == "nan_rate" else True
    elif fault == "damage":
        row["initial_damage"] = 1.1
    elif fault == "missing_patch":
        raw["model"]["injury_patches"].pop()
    elif fault == "duplicate_patch":
        raw["model"]["injury_patches"][1] = deepcopy(row)
    elif fault == "duplicate_time":
        control[1]["time"] = 0.0
    elif fault == "nonzero_start":
        control[0]["time"] = 1e-6
    elif fault == "bad_control":
        control[0]["resealing"] = 1.1
    else:
        raw["model"]["repair_atp_cost_fmol"] = 0.1
    with pytest.raises(ValueError):
        ref.bind(raw)


def test_no_production_cells_or_jax_imports():
    assert not any(
        name == "cells" or name.startswith("cells.") or name == "jax" or name.startswith("jax.")
        for name in sys.modules
    )


def test_endpoint_free_energy_derivative_with_live_lesion_water_and_fuel():
    c = ref.bind(case())
    y = changed(c)
    slope, _, proof = ref.evaluate(c, y, 0.0)
    fields, rates = ref.unpack(c, y), ref.unpack(c, slope)
    target = proof["physical_free_energy_rate_pJ_s"]
    margins = []
    for key in ("channel_gate", "calcium_gate", "damage"):
        value, rate = fields[key], rates[key]
        active = rate != 0
        margins.extend(
            (np.minimum(value[active], 1 - value[active]) / np.abs(rate[active])).tolist()
        )
    inventories = [
        (
            c["energy_initial"] + fields["energy_amount_increment_fmol"],
            rates["energy_amount_increment_fmol"],
        ),
        (
            c["ao"] + fields["extracellular_amount_increment"],
            rates["extracellular_amount_increment"],
        ),
    ]
    inventories.extend(
        (store.n0 + fields["chemical_amount_increment"][i], rates["chemical_amount_increment"][i])
        for i, store in enumerate(c["stores"])
    )
    for amount, rate in inventories:
        active = rate != 0
        margins.extend((amount[active] / np.abs(rate[active])).tolist())
    volume = parent.volumes(c["parent"], fields)
    volume_rate = np.r_[rates["volume_increment_pL"], rates["extracellular_volume_increment_pL"]]
    active = volume_rate != 0
    allowed = np.minimum(volume - c["minimum_volume_pL"], c["maximum_volume_pL"] - volume)
    margins.extend((allowed[active] / np.abs(volume_rate[active])).tolist())
    coarse = min(6.4e-6, 0.25 * min(margins))
    steps = [coarse / 2**i for i in range(12)]
    numerical = [
        (ref.free_energy_change(c, y + h * slope) - ref.free_energy_change(c, y - h * slope))
        / (2 * h)
        for h in steps
    ]
    errors = np.abs(np.array(numerical) - target)
    budget = 2e-5 + 2e-10 * abs(target)
    windows = [i for i in range(len(steps) - 2) if np.all(errors[i : i + 3] <= budget)]
    evidence(
        "endpoint-live-lesion-water-fuel",
        dict(
            inputs=c["raw"],
            state=y.tolist(),
            expected_power_pJ_s=target,
            numerical_power_pJ_s=numerical,
            step_s=steps,
            minimum_positive_domain_margin_s=float(min(margins)),
            absolute_errors_pJ_s=errors.tolist(),
            acceptance_budget_pJ_s=budget,
            adjacent_passing_windows=windows,
            coarse_convergence_order=float(np.log2(errors[0] / errors[1])),
            structural_repair_energy=proof["structural_repair_energy"],
        ),
    )
    assert np.any(rates["injury_transferred"])
    assert np.any(volume_rate) and np.any(rates["energy_amount_increment_fmol"])
    assert windows and errors[0] > errors[2] and errors[0] / errors[1] > 3
    np.testing.assert_allclose(
        numerical[windows[0] : windows[0] + 3], target, rtol=2e-10, atol=2e-5
    )


@pytest.mark.parametrize("damage", [0.0, 0.25, 1.0])
def test_actual_rates_separate_twelve_tau_opening_and_closure(damage):
    raw = case()
    patch = raw["model"]["injury_patches"][0]
    patch["initial_damage"] = damage
    a, b = patch["injury_rate_per_s"], patch["resealing_rate_per_s"]
    opening, closing = 12 / (a + b), 12 / b
    raw["experiment"].update(end_time=opening + closing, observation_times=[0, opening + closing])
    raw["experiment"]["injury_controls"][0]["schedule"] = [
        dict(time=0.0, injury=1.0, resealing=1.0),
        dict(time=opening, injury=0.0, resealing=1.0),
    ]
    c = ref.bind(raw)
    opened = np.array(ref.analytic_clock(damage, a, b, opening))
    closed = np.array(ref.analytic_clock(opened[0], 0, b, closing))
    closed[1:] += opened[1:]

    def rhs(y, hazard):
        opened_rate, closed_rate = hazard * (1 - y[0]), b * y[0]
        return np.array([opened_rate - closed_rate, opened_rate, closed_rate])

    # Bind the actual full48 oracle at both held-control phases. Other physical
    # fields stay fixed here: only this prescribed scalar clock is integrated.
    for time, values, hazard in ((0.0, [damage, 0, 0], a), (opening, opened, 0.0)):
        d = ref.unpack(c, ref.initial(c))
        for key, value in zip(("damage", "damage_opened", "damage_closed"), values, strict=True):
            d[key][0] = value
        rates = ref.unpack(c, ref.evaluate(c, ref.flatten(c, d), time)[0])
        np.testing.assert_allclose(
            [rates[key][0] for key in ("damage", "damage_opened", "damage_closed")],
            rhs(values, hazard),
            rtol=0,
            atol=0,
        )
    errors, traces = [], {}
    for count in (32, 64, 128):
        state = np.array([damage, 0.0, 0.0])
        records, targets, times = [state.copy()], [state.copy()], [0.0]
        for phase, (hazard, duration) in enumerate(((a, opening), (0.0, closing))):
            initial = np.array([damage, 0.0, 0.0]) if phase == 0 else opened
            h = duration / count
            for index in range(1, count + 1):
                k1 = rhs(state, hazard)
                k2 = rhs(state + h * k1 / 2, hazard)
                k3 = rhs(state + h * k2 / 2, hazard)
                k4 = rhs(state + h * k3, hazard)
                state = state + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
                target = np.array(ref.analytic_clock(initial[0], hazard, b, index * h))
                target[1:] += initial[1:]
                records.append(state.copy())
                targets.append(target)
                times.append((opening if phase else 0.0) + index * h)
        values, exact = np.array(records), np.array(targets)
        errors.append(float(np.max(np.abs(values - exact))))
        traces[str(count)] = dict(time_s=times, numerical=values.tolist(), exact=exact.tolist())
    evidence(
        "physical-repair-clock-" + str(damage),
        dict(
            inputs=raw,
            initial_damage=damage,
            hazard_per_s=a,
            closure_per_s=b,
            opening_time_s=opening,
            closing_time_s=closing,
            total_physical_time_s=opening + closing,
            tau_multiples=[12, 12],
            max_trace_errors=errors,
            observed_orders=np.log2(np.array(errors[:-1]) / errors[1:]).tolist(),
            final_exact=closed.tolist(),
            traces=traces,
            scope="Separate prescribed scalar clocks with other43 fields frozen; no cell settling",
            structural_repair_energy="not modelled",
        ),
    )
    for trace in traces.values():
        values = np.array(trace["numerical"])
        assert np.all((values[:, 0] >= 0) & (values[:, 0] <= 1))
        assert np.all(np.diff(values[:, 1:], axis=0) >= -1e-14)
        assert np.max(np.abs(values[:, 0] - damage - values[:, 1] + values[:, 2])) < 1e-13
    assert errors[0] < 1e-4 and errors[1] < errors[0] / 14 and errors[2] < errors[1] / 14
    assert closed[0] < 1e-5 * opened[0]


def test_short_full48_adaptive_refinement_with_offgrid_injury_and_joint_energy():
    raw = deepcopy(inputs()["probe"])
    horizon = 20e-6
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [v for v in row[key] if v["time"] <= horizon]
    raw["experiment"].update(
        end_time=horizon, observation_times=[0, 5.3e-6, 12.5e-6, 15.3e-6, 18.75e-6, horizon]
    )
    profiles = []
    evidence(
        "short48-plan", dict(inputs=raw, max_step_s=raw["execution"]["dt"], refinements=[1, 2])
    )
    for refinement in (1, 2):
        profile = ref.integrate(raw, refinement=refinement, max_step_s=raw["execution"]["dt"])
        evidence(
            "short48-profile-" + str(refinement),
            {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in profile.items()},
        )
        profiles.append(profile)
    first, second = profiles
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
    energy, internal, ownership = [], [], []
    for time, y in zip(second["times"], second["state"], strict=True):
        d = ref.unpack(c, y)
        slope, _, proof = ref.evaluate(c, y, time)
        checks(c, y, slope, time, proof)
        ownership.append(
            ownership_checks(c["energy"]["calcium"], parent.flatten(c["energy"]["calcium"], d))
        )
        heat = sum(
            float(np.sum(v)) for key, v in d.items() if key.endswith("_dissipated_energy_pJ")
        )
        supply = sum(
            float(np.sum(d[key]))
            for key in ("regeneration_supplied_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
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
        volume = parent.volumes(c["parent"], d)
        fuel = c["energy_initial"] + d["energy_amount_increment_fmol"]
        internal.append(
            [
                float(
                    chemistry.free_energy_change(
                        c["energy_initial"][:, i],
                        fuel[:, i],
                        c["vi"][i],
                        volume[i],
                        c["temperature"],
                        c["energy_delta_g0"][i],
                    )
                    + work[i]
                    - d["pool_volume_work_pJ"][i]
                )
                for i in range(len(c["vi"]))
            ]
        )
        np.testing.assert_allclose(
            fuel[0] + fuel[1], c["energy_initial"][:2].sum(axis=0), atol=2e-12, rtol=0
        )
        np.testing.assert_allclose(
            np.array([3, 2, 1]) @ fuel,
            np.array([3, 2, 1]) @ c["energy_initial"],
            atol=2e-12,
            rtol=0,
        )
        assert (
            abs(d["volume_increment_pL"].sum() + d["extracellular_volume_increment_pL"].sum())
            < 2e-12
        )
        ref.damage_valid(c, d)
    evidence(
        "short48-refinement",
        dict(
            inputs=raw,
            horizon_s=horizon,
            evaluations=[profile["evaluations"] for profile in profiles],
            max_state_error_over_budget=ratio,
            joint_energy_residual_pJ=energy,
            pool_internal_residual_pJ=internal,
            history_ownership=ownership,
            injury_on_s=5.3e-6,
            injury_off_s=15.3e-6,
            structural_repair_energy="not modelled",
            scope="Short full48 coupled refinement through injury pulse; no full-system settling",
        ),
    )
    assert ratio < 1
    np.testing.assert_allclose(energy, 0, atol=1e-9, rtol=0)
    np.testing.assert_allclose(internal, 0, atol=1e-9, rtol=0)

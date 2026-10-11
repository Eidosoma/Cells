"""Saved-data and deliberately synthetic numerical tests; not new response evidence."""

import copy
import math
import subprocess

import contact as c
import held_intervention as held
import held_response_cells_check as local
import held_response_check as check
import pytest
import trajectory_check as old_check
import trajectory_evidence as evidence
from test_held_response import array
from test_held_response import plan as plan
from test_held_response import prior as prior
from test_held_response import registered as registered
from test_held_response import saved as saved
from test_held_response import synthetic_pulse as synthetic_pulse
from trajectory_check import Checks


@pytest.mark.parametrize("condition", ["baseline", "zero_amplitude", "static_blocked"])
def test_saved_native_internal_laws_match_unchanged_criteria(registered, saved, condition):
    row = next(r for r in registered["native_rows"] if r["condition"] == condition)
    checks = Checks()
    canonical = check.native_record(registered, saved[condition]["observed"], row, checks)
    assert checks.failed_count == 0, checks.failures
    # Initial 44 state + 222 concentration checks; each step has two states,
    # 180 face fluxes and six species' local/bath step and cumulative ledgers.
    assert checks.count == 44 + 222 + 40 * (2 * 44 + 6 * (30 + 2 * 7 + 2))
    assert len(canonical) == 41
    assert canonical[-1]["current_A"] == canonical[-1]["flux_fmol_per_s"] == []
    assert len(check.intervals(canonical)) == 40


def test_synthetic_pulse_with_baseline_transport_fails_physical_law(registered, synthetic_pulse):
    checks = Checks()
    check.native_record(registered, synthetic_pulse, registered["native_rows"][-1], checks)
    assert checks.failed_count > 0
    assert any("GHK" in item["id"] for item in checks.failures)


def test_final_permeability_cannot_replace_per_interval_Dm(registered, synthetic_pulse):
    packet = copy.deepcopy(synthetic_pulse)
    final = packet["result"]["final_state"]["arrays"]["Dm_cells"]
    for event in packet["events"]["events"]:
        event["after"]["arrays"]["Dm_cells"] = copy.deepcopy(final)
    with pytest.raises(ValueError, match="dynamic permeability"):
        check.native_record(registered, packet, registered["native_rows"][-1], Checks())


@pytest.mark.parametrize(
    "corruption",
    [
        "nonpositive",
        "nonmixed",
        "charge",
        "flux",
        "inventory",
        "stored_Dm",
        "stored_current",
        "inactive_flux",
        "ion_table",
    ],
)
def test_native_numerical_corruptions_fail(registered, saved, corruption):
    packet = copy.deepcopy(saved["baseline"]["observed"])
    numerical = packet["result"]["numerical"]
    step = numerical["trace"]["steps"][3]
    if corruption == "nonpositive":
        step["after"]["inside_mM"][0][0] = 0
    elif corruption == "nonmixed":
        step["after"]["outside_mM"][0][0] += 1
    elif corruption == "charge":
        step["after"]["rho_C_per_m3"][0] += 1
    elif corruption == "flux":
        step["density_mol_per_m2_s"][0][0] *= 0.5
    elif corruption == "inventory":
        for state in [
            numerical["trace"]["initial"],
            *(s[k] for s in numerical["trace"]["steps"] for k in ("before", "after")),
        ]:
            state["inside_mM"][0][0] += 1
    elif corruption in ("stored_Dm", "stored_current"):
        name = "dd_time" if corruption == "stored_Dm" else "I_mem_time"
        a = numerical["ordinary"][name]
        if name == "dd_time":
            a["values"][0][0][0] *= 0.5
        else:
            a["values"][0][0] += 1
        numerical["ordinary"][name] = array(a["values"], a["shape"])
    elif corruption == "inactive_flux":
        step["junction_density_mol_per_m2_s"][0][0] = 1
    elif corruption == "ion_table":
        numerical["species"].reverse()
    checks = Checks()
    try:
        check.native_record(registered, packet, registered["native_rows"][0], checks)
    except ValueError:
        return
    assert checks.failed_count > 0


@pytest.fixture(scope="module")
def blocked(registered):
    """Resample the constant exact blocked solution, only in pytest memory."""
    baseline = c.read(evidence.SESSION / "cells/blocked/jax_eager/0.00005000/result.json")
    results = {}
    for row in registered["cells_rows"]:
        if row["condition"] != "static_blocked":
            continue
        n = 40 * row["subdivision"]
        record = copy.deepcopy(baseline)
        record |= {
            "id": row["id"],
            "definition": registered["cells_definitions"][row["id"]],
            "final_step_index": n,
        }
        record["times"] = array(
            [k * 0.000025 / row["subdivision"] for k in range(n)] + [0.001], [n + 1]
        )
        for group, count in (("history", n + 1), ("observations", 41)):
            for name, original in baseline[group].items():
                record[group][name] = array(
                    [copy.deepcopy(original["values"][0]) for _ in range(count)],
                    [count, *original["shape"][1:]],
                )
        record["observations"]["times"] = array(registered["common_times_s"], [41])
        results[row["id"]] = record
    return results


@pytest.mark.parametrize("backend", ["jax_eager", "jax_jit"])
@pytest.mark.parametrize("factor", [1, 2, 4])
def test_synthetic_exact_blocked_solution_checks_every_grid_point(
    registered, blocked, backend, factor
):
    row = next(
        r
        for r in registered["cells_rows"]
        if r["id"] == f"static_blocked/{backend}/subdivision-{factor}"
    )
    checks = Checks()
    canonical = local.cells_record(registered, blocked[row["id"]], row, checks)
    assert checks.failed_count == 0, checks.failures
    assert all(v == 0 for point in canonical for a in point.values() for v in a)
    assert checks.count > 40 * factor * 24


@pytest.mark.parametrize(
    "corruption",
    [
        "definition",
        "grid",
        "final_step",
        "missing_history",
        "missing_readout",
        "shape",
        "bytes",
        "padding",
        "hidden_inventory",
        "owned_transfer",
        "global_inventory",
        "on_grid_link",
        "flux",
        "voltage",
        "bath_amount",
        "bath_rate",
        "inactive_state",
        "inactive_readout",
        "negative_energy",
        "nonfinite",
        "diagnostics",
        "control",
        "terminal_control",
    ],
)
def test_cells_rehashed_corruptions_are_not_accepted(registered, blocked, corruption):
    identifier = "static_blocked/jax_eager/subdivision-4"
    record = copy.deepcopy(blocked[identifier])
    row = next(r for r in registered["cells_rows"] if r["id"] == identifier)
    # For history-mutation tests avoid the earlier exact-blocked gate so that
    # conservation/positivity/padding gates are exercised on their own.
    if corruption in (
        "padding",
        "hidden_inventory",
        "owned_transfer",
        "global_inventory",
        "on_grid_link",
        "negative_energy",
    ):
        row = row | {"condition": "baseline", "id": "baseline/jax_eager/subdivision-4"}
        record |= {"id": row["id"], "definition": registered["cells_definitions"][row["id"]]}
    if corruption == "definition":
        record["definition"]["execution"]["dt"] *= 2
    elif corruption == "grid":
        a = record["times"]
        a["values"][3] += 1e-8
        record["times"] = array(a["values"], a["shape"])
    elif corruption == "final_step":
        record["final_step_index"] -= 1
    elif corruption == "missing_history":
        record["history"].pop("gate")
    elif corruption == "missing_readout":
        record["observations"].pop("pump_affinity_J_per_mol")
    elif corruption == "shape":
        record["observations"]["voltage_V"]["shape"] = [41, 8]
    elif corruption == "bytes":
        record["history"]["gate"]["bytes_sha256"] = "0" * 64
    elif corruption == "diagnostics":
        record["diagnostics"]["max_balance_error_fmol"] = -1
    else:
        group, name, indices, value = {
            "padding": ("history", "amount_increment", [3, 0, 7], 1),
            "hidden_inventory": ("history", "amount_increment", [3, 0, 0], -100000),
            "owned_transfer": ("history", "leak_transferred", [3, 0, 0], 1),
            "global_inventory": ("history", "extracellular_amount_increment", [3, 0, 0], 1),
            "on_grid_link": ("observations", "leak_transferred", [3, 0, 0], 1),
            "flux": ("observations", "leak_flux_fmol_per_s", [3, 0, 0], 1),
            "voltage": ("observations", "voltage_V", [3, 0], 1),
            "bath_amount": ("observations", "extracellular_amount", [3, 0, 0], 1),
            "bath_rate": ("observations", "extracellular_rate_fmol_per_s", [3, 0, 0], 1),
            "inactive_state": ("history", "channel_transferred", [3, 0], 1),
            "inactive_readout": ("observations", "pump_multiplier", [3, 0], 1),
            "negative_energy": ("history", "dissipated_energy_pJ", [3, 0], -1),
            "nonfinite": ("observations", "voltage_V", [3, 0], float("nan")),
            "control": ("observations", "leak_multiplier", [3, 0, 0], 1),
            "terminal_control": ("observations", "leak_multiplier", [40, 0, 0], 1),
        }[corruption]
        a = record[group][name]
        cursor = a["values"]
        for i in indices[:-1]:
            cursor = cursor[i]
        cursor[indices[-1]] = value
        if corruption != "nonfinite":
            record[group][name] = array(a["values"], a["shape"])
    checks = Checks()
    try:
        local.cells_record(registered, record, row, checks)
    except ValueError:
        return
    assert checks.failed_count > 0


def test_pulse_uses_last_interval_not_analytic_endpoint():
    schedule = held.held_schedule(c.read(held.PLAN), "suppression_recovery", 0.000025)
    law = c.read(held.law.PLAN)
    final = schedule[-1]["multipliers"]["Na"]
    endpoint = held.law.decimal_availability(0.001, law["candidate_pulse"])
    assert final != endpoint
    assert 0 < final < 1
    assert schedule[-1]["time"] == 39 * 0.000025


@pytest.fixture(scope="module")
def synthetic_cells_pulse(registered, blocked):
    """Prescribed states with independent instantaneous readouts, NOT an ODE solution."""
    identifier = "suppression_recovery/jax_eager/subdivision-4"
    record = copy.deepcopy(blocked["static_blocked/jax_eager/subdivision-4"])
    record |= {"id": identifier, "definition": registered["cells_definitions"][identifier]}
    old = c.read(evidence.SESSION / "cells/passive/jax_eager/0.00005000/result.json")
    b, g = registered["base_protocol"], registered["geometry"]
    constant = b["profiles"]["matched_constants"]
    schedule = held.held_schedule(c.read(held.PLAN), "suppression_recovery", 0.000025)
    for name, a in record["history"].items():

        def scale(value, fraction):
            return (
                [scale(v, fraction) for v in value] if isinstance(value, list) else value * fraction
            )

        record["history"][name] = array(
            [scale(old["history"][name]["values"][-1], k / 160) for k in range(161)], a["shape"]
        )
    observations = {name: a["values"] for name, a in record["observations"].items()}
    for j in range(41):
        for name, a in record["history"].items():
            observations[name][j] = copy.deepcopy(a["values"][4 * j])
        inside = observations["amount_increment"][j]
        outside = observations["extracellular_amount_increment"][j]
        vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
        u = schedule[min(j, 39)]["multipliers"]["Na"]
        voltage = [
            constant["F"]
            * 1e-15
            * math.fsum(b["expected_valence"][s] * inside[s][i] for s in range(3))
            / (0.01 * g["cell_areas_m2"][i])
            for i in range(7)
        ]
        observations["voltage_V"][j] = voltage + [0, 0]
        fluxes = []
        for s in range(3):
            amounts = [b["inside_mM"][s] * vi[i] + inside[s][i] for i in range(7)]
            concentrations = [a / v for a, v in zip(amounts, vi, strict=True)]
            co = b["outside_mM"][s] + outside[s][0] / vo
            flux = [
                c.oracle(
                    {
                        "inside_mM": concentrations[i],
                        "outside_mM": co,
                        "voltage_V": voltage[i],
                        "valence": b["expected_valence"][s],
                        "temperature_K": 310.15,
                        "area_m2": g["cell_areas_m2"][i],
                        "permeability_m_per_s": b["permeability_m_per_s"][s] * u,
                    },
                    constant,
                )
                for i in range(7)
            ]
            fluxes.append(flux)
            observations["amount"][j][s] = amounts + [0]
            observations["concentration_mM"][j][s] = concentrations + [0]
            observations["extracellular_amount"][j][s] = [co * vo, 0]
            observations["extracellular_concentration_mM"][j][s] = [co, 0]
            observations["extracellular_rate_fmol_per_s"][j][s] = [-math.fsum(flux), 0]
            observations["leak_multiplier"][j][s] = [u] * 7 + [0, 0]
            observations["leak_flux_fmol_per_s"][j][s] = flux + [0, 0]
        observations["membrane_current_A"][j] = [
            constant["F"]
            * 1e-15
            * math.fsum(b["expected_valence"][s] * fluxes[s][i] for s in range(3))
            for i in range(7)
        ] + [0, 0]
    record["observations"] = {
        name: array(observations[name], a["shape"]) for name, a in record["observations"].items()
    }
    return record


def test_prescribed_pulse_readouts_include_terminal_held_rate(registered, synthetic_cells_pulse):
    row = next(r for r in registered["cells_rows"] if r["id"] == synthetic_cells_pulse["id"])
    checks = Checks()
    canonical = local.cells_record(registered, synthetic_cells_pulse, row, checks)
    assert checks.failed_count == 0, checks.failures
    assert canonical[-1]["current_A"] == canonical[-1]["flux_fmol_per_s"] == []
    assert synthetic_cells_pulse["observations"]["membrane_current_A"]["values"][-1][0] != 0


@pytest.mark.parametrize(
    "change",
    [
        "analytic_endpoint_control",
        "terminal_rate",
        "shifted_control",
        "missing_terminal_rate",
        "inventory",
        "transfer",
        "sampled_ledger",
    ],
)
def test_pulse_readout_corruption_is_rejected(registered, synthetic_cells_pulse, change):
    record = copy.deepcopy(synthetic_cells_pulse)
    row = next(r for r in registered["cells_rows"] if r["id"] == record["id"])
    if change == "analytic_endpoint_control":
        a = record["observations"]["leak_multiplier"]
        law = c.read(held.law.PLAN)
        endpoint = held.law.decimal_availability(0.001, law["candidate_pulse"])
        a["values"][-1] = [[endpoint] * 7 + [0, 0] for _ in range(3)]
        record["observations"]["leak_multiplier"] = array(a["values"], a["shape"])
    elif change == "shifted_control":
        a = record["observations"]["leak_multiplier"]
        a["values"][16] = a["values"][15]
        record["observations"]["leak_multiplier"] = array(a["values"], a["shape"])
    elif change == "missing_terminal_rate":
        a = record["observations"]["leak_flux_fmol_per_s"]
        record["observations"]["leak_flux_fmol_per_s"] = array(a["values"][:-1], [40, 3, 9])
    else:
        group, name, k = {
            "terminal_rate": ("observations", "leak_flux_fmol_per_s", 40),
            "inventory": ("history", "extracellular_amount_increment", 3),
            "transfer": ("history", "leak_transferred", 3),
            "sampled_ledger": ("observations", "leak_transferred", 3),
        }[change]
        a = record[group][name]
        a["values"][k][0][0] += 1
        record[group][name] = array(a["values"], a["shape"])
    checks = Checks()
    try:
        local.cells_record(registered, record, row, checks)
    except ValueError:
        return
    assert checks.failed_count > 0


def test_interval_transfers_include_last_interval_not_final_fresh_rate():
    canonical = [
        {k: [float(i)] * 21 if k == "transfer_fmol" else [] for k in check.UNITS} for i in range(41)
    ]
    values = check.intervals(canonical)
    assert len(values) == 40
    assert all(point["transfer_fmol"] == [1.0] * 21 for point in values)
    assert all(point["current_A"] == point["flux_fmol_per_s"] == [] for point in values)
    with pytest.raises(ValueError, match="coverage"):
        check.intervals(canonical[:-1])


def test_panel_keeps_cross_failures_and_separates_scopes(registered):
    canonical = [
        {
            unit: [0.0]
            * (7 if unit in ("voltage_V", "current_A") else 24 if unit == "amount_fmol" else 21)
            for unit in check.UNITS
        }
        for _ in range(41)
    ]
    canonical[-1]["current_A"] = canonical[-1]["flux_fmol_per_s"] = []
    cells = {identifier: copy.deepcopy(canonical) for identifier in registered["cells_definitions"]}
    natives = {
        condition: copy.deepcopy(canonical) for condition in registered["plan"]["conditions"]
    }
    # Synthetic shared-bath amount error, retained even if every Cells refinement passes.
    natives["baseline"][-1]["amount_fmol"][-1] = 3e-7
    checks = Checks()
    compared = check.compare_panel(registered, natives, cells, checks)
    assert len(compared) == 36
    assert checks.failed_count == 2
    assert all(
        v["failed_comparisons"] == 0
        for k, v in compared.items()
        if not k.startswith("cross_engine/baseline/")
    )
    assert compared["cross_engine/baseline/jax_eager"]["failed_comparisons"] == 1
    assert check.summary(checks)["failed_comparisons"] == 2


def test_real_retained_coarse_native_mismatch_is_not_requalified(prior):
    native = c.read(
        evidence.SESSION / "native/passive/matched_constants/0.00002500/observed/result.json"
    )
    cells = c.read(evidence.SESSION / "cells/passive/jax_eager/0.00005000/result.json")
    case = {"id": "passive", "availability": 1.0}
    checks = Checks()
    left = old_check.native_record(prior, native, case, "matched_constants", 0.000025, checks)
    right = old_check.cells_record(prior, cells, case, "jax_eager", 0.000050, checks)
    assert checks.failed_count == 0
    old_check.difference(
        "retained_coarse_cross", left, right, prior["protocol"]["trajectory_tolerances"], checks
    )
    assert checks.failed_count > 0
    assert any("amount_fmol" in item["id"] for item in checks.failures)


def test_comparison_imports_are_model_and_array_free():
    script = (
        "import sys; sys.path.insert(0,'validation/betse'); import held_response_check as c; "
        "assert not any(n.split('.')[0] in c.fence.FORBIDDEN for n in sys.modules); "
        "sys.meta_path.insert(0,c.fence.ImportFence()); import numpy"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", script],
        cwd=c.ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Offline audit forbids model/array import: numpy" in result.stderr

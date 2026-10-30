"""Prepared true molecule chemistry/mover checks; no new numerical run yet."""

import copy
import json
import os
import re
import subprocess
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_network_transport as transporter_component
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_transporter_join as joined
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit import test_betse_normal_network_join as feedback_checks
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_transporter_join_fixtures as fixtures
from validation.betse import betse_normal_transporter_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

RATE_TOLERANCES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "validation/chemistry/betse_network_reactions_protocol.json"
    ).read_text()
)["tolerances"]
TRANSPORT_TOLERANCES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "validation/transport/betse_network_transport_protocol.json"
    ).read_text()
)["tolerances"]


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-transporter-join"
    )


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, ions.data(payload))


def archive_refusal(tmp_path, name, inputs, error):
    payload = dict(
        inputs=inputs,
        type=type(error).__name__,
        message=str(error),
        traceback=traceback.format_exc(),
    )
    for key in (
        "stage",
        "parent",
        "initialization",
        "material",
        "channel_phases",
        "network",
        "readout",
        "voltage_trial",
    ):
        payload[key] = getattr(error, key, None)
    return archive(tmp_path, "unexpected-refusal-" + name, payload)


def seed(inputs):
    ib = ions.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    gb = gated.bind(ib, vb, inputs["gate_definition"])
    pb = pump.bind(gb, inputs["pump_definition"])
    binding = joined.bind(pb, inputs["channel_definition"])
    parent = joined.initialize_values(
        binding,
        inputs["initial"],
        initial_gate_block=inputs["initial_gate_block"],
        initial_NaK_rate=inputs["initial_rate_proxy_mol_m2_s"],
        initial_CaATP_rate=inputs["initial_calcium_rate_proxy_mol_m2_s"],
    )
    return binding, parent


def advance(inputs, binding, parent, index, elapsed, observer=None, transporter_observer=None):
    drive = inputs["drives"][index]
    scheduled = drive["scheduled_controls"]
    effective = parent.network_controls if scheduled is None else scheduled
    material = dict(drive["material"], junction_block=effective["gj_block"])
    live_pump = dict(drive["pump"], block=effective["NaKATP_block"])
    return joined.advance(
        binding,
        parent,
        ions.drive(binding.pump_binding.gated_binding.material_binding, **material),
        pump.packet(binding.pump_binding, **live_pump),
        joined.packet(binding, **drive["channels"]),
        joined.calcium_packet(binding, **drive["calcium"]),
        before_network=observer,
        before_transporters=transporter_observer,
        scheduled_controls=scheduled,
        boundary_V=drive["boundary_V"],
        extra_charge_C_m3=drive["extra_charge_C_m3"],
        extra_current_A_m2=drive["extra_current_A_m2"],
        elapsed_s=elapsed,
    )


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_transporter_join_native",
        "--inputs",
        str(folder / "inputs.json"),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    result = archive_read(folder / "native")
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["RNG_unchanged"]
    return folder, result


def references(folder, before):
    (folder / "inputs.json").write_text(
        json.dumps(old.plain(ions.data(before)), indent=2, allow_nan=False) + "\n"
    )
    result = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_transporter_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--refinement",
            str(level),
        ]
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        answer = json.loads(path.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        result.append(answer)
    return result


def exact_nested(actual, expected):
    if isinstance(expected, np.ndarray):
        assert isinstance(actual, (np.ndarray, np.generic))
        value = np.asarray(actual)
        assert value.dtype == expected.dtype and value.shape == expected.shape
        np.testing.assert_array_equal(value, expected)
    elif isinstance(expected, Mapping):
        assert isinstance(actual, Mapping) and set(actual) == set(expected)
        for name in expected:
            exact_nested(actual[name], expected[name])
    elif isinstance(expected, (tuple, list)):
        assert isinstance(actual, (tuple, list)) and len(actual) == len(expected)
        for value, wanted in zip(actual, expected, strict=True):
            exact_nested(value, wanted)
    else:
        assert actual == expected


def compare_feedback(actual, source, *, completed):
    for key in ("values_before", "values_after"):
        exact(ions.Values(**actual[key]), source[key])
    for key in (
        "controls_before",
        "controls_after",
        "cache_before",
        "cache_after",
        "rhs",
        "molecule_states_before",
        "molecule_states_after",
        "molecule_frames",
        "mover_frames",
        "control_writes",
    ):
        exact_nested(actual[key], source[key])
    assert list(actual["molecule_states_after"]) == list(source["molecule_states_after"])
    assert actual["source_completed"] == source["source_completed"] == completed
    assert actual["chemical_rhs_evaluated"] == source["chemical_rhs_evaluated"]
    assert actual["executed_chemistry"] == source["executed_chemistry"]
    assert actual["molecular_transports_completed"] == source["molecular_transports_completed"]


def local_comparisons(binding, trial, lower, target, reused):
    rows, errors, budgets = feedback_checks.local_comparisons(trial, lower, target, reused)
    feedback = trial.material.network_feedback
    ib = binding.pump_binding.gated_binding.material_binding
    definitions = binding.definition["network"]["molecules"]
    count, n, m = len(ib.ion_ids), len(ib.cell_ids), len(ib.membrane_ids)
    factor = 128 * np.finfo(float).eps * (count + len(definitions) + n + m + 64)

    def add(name, actual, expected, less, budget, unit):
        a, b = np.asarray(actual), np.asarray(expected)
        rows[name] = old.metric(a, b, budget) | dict(unit=unit)
        rows["reference/" + name] = old.metric(less, b, budget) | dict(unit=unit)
        errors[name], budgets[name] = abs(a - b), np.broadcast_to(budget, a.shape)

    for key in ("growth_rates", "reaction_rates", "all_rates"):
        wanted = np.asarray(target["rhs"][key])
        budget = RATE_TOLERANCES["rate_atol_mM_s"] + RATE_TOLERANCES["relative"] * abs(wanted)
        add("rhs/" + key, feedback["rhs"][key], wanted, lower["rhs"][key], budget, "mM/s")
    wanted = np.asarray(target["delta_conc"])
    budget = 3 * RATE_TOLERANCES["rate_atol_mM_s"] + RATE_TOLERANCES["relative"] * np.asarray(
        target["delta_gross"]
    )
    add(
        "delta_conc",
        feedback["cache_after"]["delta_conc"],
        wanted,
        lower["delta_conc"],
        budget,
        "mM/s",
    )
    ledger = {}
    cell_volume, area = ib.kernel.cell_volume_m3, ib.kernel.area_m2
    dt = trial.material.pump.gated.material.drive.dt_s
    for index, definition in enumerate(definitions):
        name = definition["name"]
        actual = feedback["molecule_states_after"][name]
        expected, less = target["molecules_after"][name], lower["molecules_after"][name]
        for key in ("c_cells", "cc_at_mem", "c_env", "f_mem", "f_gj"):
            gross = np.asarray(target["gross_molecules"][name][key])
            floor = (
                FLOORS["membrane_flux_mol_m2_s"]
                if key.startswith("f_")
                else FLOORS["bath_mol_m3"]
                if key == "c_env"
                else FLOORS["cell_mol_m3"]
            )
            add(
                name + "/" + key,
                actual[key],
                expected[key],
                less[key],
                factor * gross + floor,
                "mol/(m2*s)" if key.startswith("f_") else "mM",
            )
        np.testing.assert_array_equal(
            actual["flux_intra"], feedback["molecule_states_before"][name]["flux_intra"]
        )
        assert actual["fenvx"] == actual["fenvy"] == 0
        prior = feedback["molecule_states_before"][name]
        chemical = feedback["cache_after"]["delta_conc"][count + index] * cell_volume * dt
        growth = feedback["rhs"]["growth_rates"][index] * cell_volume * dt
        membrane = np.dot(ib.kernel.owner_sum, actual["f_mem"] * area) * dt
        gap = (
            -np.dot(ib.kernel.owner_sum, actual["f_gj"] * area)
            * dt
            * definition["parameters"]["modify_time_factor"]
        )
        cell_change = (actual["c_cells"] - prior["c_cells"]) * cell_volume
        residual = cell_change - chemical - membrane - gap
        cell_budget = (
            factor
            * (
                abs(actual["c_cells"] * cell_volume)
                + abs(prior["c_cells"] * cell_volume)
                + abs(chemical)
                + abs(membrane)
                + abs(gap)
            )
            + FLOORS["cell_mol_m3"] * cell_volume
        )
        env_volume = ib.kernel.bath_volume_m3
        effective_env_change = (np.sum(actual["c_env"]) - np.sum(prior["c_env"])) * env_volume
        membrane_total = np.sum(actual["f_mem"] * area) * dt
        env_residual = effective_env_change + membrane_total
        env_budget = (
            factor
            * (
                (np.sum(abs(actual["c_env"])) + np.sum(abs(prior["c_env"]))) * env_volume
                + np.sum(abs(actual["f_mem"] * area)) * dt
            )
            + FLOORS["bath_mol_m3"] * m * env_volume
        )
        for label, value, bound in (
            ("cell_balance", residual, cell_budget),
            ("source_effective_bath_balance", np.asarray(env_residual), np.asarray(env_budget)),
        ):
            rows[name + "/" + label] = old.metric(
                value, np.zeros(np.asarray(value).shape), bound
            ) | dict(unit="mol")
            errors[name + "/" + label], budgets[name + "/" + label] = abs(value), bound
        single_bath_change = (np.mean(actual["c_env"]) - np.mean(prior["c_env"])) * env_volume
        physical_residual = (
            np.sum(cell_change) + single_bath_change - np.sum(chemical) - np.sum(gap)
        )
        predicted_defect = (1 - 1 / m) * membrane_total
        defect_error = physical_residual - predicted_defect
        defect_budget = np.sum(cell_budget) + env_budget
        rows[name + "/declared_bath_source_defect"] = old.metric(
            np.asarray(defect_error), np.asarray(0.0), defect_budget
        ) | dict(unit="mol", physical_conservation_credit=False)
        (
            errors[name + "/declared_bath_source_defect"],
            budgets[name + "/declared_bath_source_defect"],
        ) = abs(defect_error), defect_budget
        ledger[name] = dict(
            chemical_source_mol=chemical,
            growth_source_mol=growth,
            reaction_conversion_mol=chemical - growth,
            membrane_transfer_mol=membrane,
            directed_GJ_change_mol=gap,
            source_effective_bath_change_mol=effective_env_change,
            source_effective_bath_volume_m3=m * env_volume,
            declared_single_bath_volume_m3=env_volume,
            declared_single_bath_residual_mol=physical_residual,
            predicted_single_bath_source_defect_mol=predicted_defect,
            physical_global_conservation_credit=False,
            global_GJ_zero_assumed=False,
        )
    for key, gross_key, coefficient, unit in (
        (
            "extra_rho_cells",
            "extra_rho_gross",
            32 * np.finfo(float).eps * (len(definitions) + n + 16),
            "C/m3",
        ),
        (
            "extra_J_mem",
            "extra_J_gross",
            128 * np.finfo(float).eps * (len(definitions) + m + 32),
            "A/m2",
        ),
    ):
        budget = coefficient * np.asarray(target[gross_key]) + 1e-30
        add(key, feedback["cache_after"][key], target[key], lower[key], budget, unit)
    np.testing.assert_array_equal(feedback["values_after"]["voltage_V"], target["voltage_after_V"])
    np.testing.assert_array_equal(
        feedback["values_after"]["junction_voltage_V"], target["junction_voltage_after_V"]
    )
    return rows, errors, budgets, ledger


def transporter_comparisons(execution, lower, target):
    rows, errors, budgets, ledgers = {}, {}, {}, []
    geometry = execution["geometry"]
    owner = np.asarray(geometry["owner"], int)
    area, volume, wedge = (
        np.asarray(geometry[key])
        for key in ("membrane_area_m2", "cell_volume_m3", "membrane_volume_m3")
    )
    n, m = len(volume), len(owner)
    species = tuple(execution["concentrations_before"]["cell_concs"])
    factor = 128 * np.finfo(float).eps * (len(species) + n + m + 64)
    dt, bath_volume = execution["dt_s"], execution["bath_volume_m3"]
    counts = np.bincount(owner, minlength=n)
    effective_weights = volume[owner] / counts[owner]

    def add(name, actual, wanted, less, budget, unit):
        a, b = np.asarray(actual), np.asarray(wanted)
        budget = np.broadcast_to(budget, a.shape)
        assert np.isfinite(a).all() and np.isfinite(b).all() and np.all(budget > 0)
        rows[name] = old.metric(a, b, budget) | dict(unit=unit)
        rows["reference/" + name] = old.metric(less, b, budget) | dict(unit=unit)
        errors[name], budgets[name] = abs(a - b), budget.copy()

    actual_frames = [row for row in execution["frames"] if row["stage"] not in ("before", "flux")]
    assert len(actual_frames) == len(target["frames"]) == len(lower["frames"])
    for index, (actual, wanted, less) in enumerate(
        zip(actual_frames, target["frames"], lower["frames"], strict=True)
    ):
        assert (actual["stage"], actual["name"], actual["term"]) == (
            wanted["stage"],
            wanted["name"],
            wanted["term"],
        )
        prefix = str(index) + "/" + actual["name"] + "/" + actual["stage"]
        rate = np.asarray(wanted["flux"])
        add(
            prefix + "/flux",
            actual["fluxes"][actual["name"]],
            rate,
            less["flux"],
            TRANSPORT_TOLERANCES["density_atol_mol_m2_s"]
            + TRANSPORT_TOLERANCES["relative"] * abs(rate),
            "mol/(m2*s)",
        )
        add(
            prefix + "/current",
            actual["extra_current_A_m2"],
            wanted["extra_current_A_m2"],
            less["extra_current_A_m2"],
            TRANSPORT_TOLERANCES["current_atol_A_m2"]
            + factor * np.asarray(wanted["current_gross"]),
            "A/m2",
        )
        for zone, floor in (
            ("cell_concs", "cell_mol_m3"),
            ("mem_concs", "membrane_mol_m3"),
            ("env_concs", "bath_mol_m3"),
        ):
            for name in species:
                add(
                    prefix + "/" + zone + "/" + name,
                    actual["concentrations"][zone][name],
                    wanted["concentrations"][zone][name],
                    less["concentrations"][zone][name],
                    FLOORS[floor] + factor * np.asarray(wanted["gross"][zone][name]),
                    "mM",
                )
        if actual["delta"] is not None:
            add(
                prefix + "/delta",
                actual["delta"],
                wanted["delta"],
                less["delta"],
                FLOORS["cell_mol_m3"] + factor * np.asarray(wanted["delta_gross"]),
                "mM/s",
            )

    valence = dict(zip(execution["ion_ids"], execution["valence"], strict=True))
    valence.update(
        {row["name"]: row["parameters"]["z"] for row in execution["definition"]["molecules"]}
    )
    configurations = {row["name"]: row for row in execution["definition"]["transporters"]}
    for index, (prediction, less) in enumerate(
        zip(target["ledgers"], lower["ledgers"], strict=True)
    ):
        name, config = prediction["name"], configurations[prediction["name"]]
        before = next(
            row for row in execution["frames"] if row["stage"] == "before" and row["name"] == name
        )
        after = next(
            row for row in execution["frames"] if row["stage"] == "after" and row["name"] == name
        )
        flux = np.asarray(after["fluxes"][name])
        old_state, new_state = before["concentrations"], after["concentrations"]
        # Legacy fixtures supply F=96485,R=8.314; the component fixes modern
        # constants. Compare constant-independent factors/net_z for every row,
        # and the flux only for irreversible rows. The Decimal reference above
        # always uses the actual source constants for reversible source rates.
        for site in range(m):
            topology, parameters = transporter_component.bind(
                [ions.data(config)],
                species,
                joined.network_source.integer_valences([valence[s] for s in species]),
                [0],
                [1],
                [True, True],
                area_m2=[area[site]],
                temperature_K=execution["runtime_temperature_K"],
            )
            values = np.asarray(
                [
                    [old_state["mem_concs"][s][site], old_state["env_concs"][s][site]]
                    for s in species
                ]
            )
            result = transporter_component.rates(
                values,
                execution["values_before"]["voltage_V"][site],
                topology,
                parameters,
                rho=execution["rho_pump"][site],
                xp=np,
            )
            secondary = [
                ("saturation", result.forward_saturation[0], prediction["forward"][site], "1"),
                ("regulation", result.regulation[0], prediction["regulation"][site], "1"),
                ("net_z", result.native_net_z[0], prediction["net_z"], "1"),
            ]
            if config["standard free energy"] == "None":
                secondary.append(
                    ("flux", result.flux_density_mol_m2_s[0], flux[site], "mol/(m2*s)")
                )
            for label, actual_value, expected_value, unit in secondary:
                budget = TRANSPORT_TOLERANCES[
                    "density_atol_mol_m2_s" if label == "flux" else "dimensionless_atol"
                ] + TRANSPORT_TOLERANCES["relative"] * abs(expected_value)
                key = f"component/{name}/{site}/{label}"
                rows[key] = old.metric(actual_value, expected_value, budget) | dict(unit=unit)
                errors[key], budgets[key] = (
                    abs(np.asarray(actual_value) - expected_value),
                    np.asarray(budget),
                )
        for substance in species:
            old_cell, new_cell = (
                np.asarray(state["cell_concs"][substance]) for state in (old_state, new_state)
            )
            old_env, new_env = (
                np.asarray(state["env_concs"][substance]) for state in (old_state, new_state)
            )
            bulk = np.dot(new_cell - old_cell, volume)
            bath = (new_env - old_env).mean() * bath_volume
            effective = np.dot(new_env - old_env, effective_weights)
            p, lo = prediction["predicted"][substance], less["predicted"][substance]
            gross_amount = (
                np.dot(abs(new_cell) + abs(old_cell), volume)
                + np.dot(abs(new_env) + abs(old_env), effective_weights)
                + (abs(old_env).mean() + abs(new_env).mean()) * bath_volume
            )
            amount_budget = factor * gross_amount + FLOORS["cell_mol_m3"] * (
                sum(volume) + bath_volume
            )
            prefix = f"accounting/{index}/{substance}"
            for label, actual, wanted, lower_value in (
                ("bulk", bulk, p["bulk"], lo["bulk"]),
                ("physical_bath", bath, p["bath"], lo["bath"]),
                ("source_effective_environment", effective, p["effective"], lo["effective"]),
                ("physical_defect", bulk + bath, p["bulk"] + p["bath"], lo["bulk"] + lo["bath"]),
                (
                    "source_effective_residual",
                    bulk + effective,
                    p["bulk"] + p["effective"],
                    lo["bulk"] + lo["effective"],
                ),
            ):
                add(prefix + "/" + label, actual, wanted, lower_value, amount_budget, "mol")
            # Compare the discrepancy to its a priori source prediction. A
            # zero-physical-defect assertion would hide the source semantics.
            ideal = np.zeros(m)
            for sign, role, coefficient_key, transfer in (
                (-1, "reactants", "reactant multipliers", "transfered into cell"),
                (1, "products", "product multipliers", "transfered out of cell"),
            ):
                moved = config[transfer]
                moved = [] if moved in (None, "None") else moved
                for s, nu in zip(config[role], config[coefficient_key], strict=True):
                    if s == substance and s not in moved:
                        ideal += sign * nu * flux * area / wedge * dt
            old_mem, new_mem = (
                np.asarray(state["mem_concs"][substance]) for state in (old_state, new_state)
            )
            discrepancy = new_mem - old_mem - ideal
            buffer_budget = FLOORS["membrane_mol_m3"] + factor * (
                abs(old_mem) + abs(new_mem) + abs(ideal)
            )
            add(
                prefix + "/buffer_discrepancy",
                discrepancy,
                p["buffer"],
                lo["buffer"],
                buffer_budget,
                "mM",
            )
            ledgers.append(
                dict(
                    name=name,
                    species=substance,
                    physical_bulk_delta_mol=bulk,
                    physical_single_bath_delta_mol=bath,
                    physical_defect_mol=bulk + bath,
                    predicted_physical_defect_mol=p["bulk"] + p["bath"],
                    source_effective_environment_delta_mol=effective,
                    source_effective_residual_mol=bulk + effective,
                    predicted_source_effective_residual_mol=p["bulk"] + p["effective"],
                    observed_buffer_discrepancy_mM=discrepancy,
                    predicted_buffer_discrepancy_mM=p["buffer"],
                    amount_budget_mol=amount_budget,
                    buffer_budget_mM=buffer_budget,
                    original_bath_volume_m3=bath_volume,
                    source_effective_weights_m3=effective_weights.copy(),
                    physical_conservation_credit=False,
                )
            )
    return rows, errors, budgets, ledgers


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_configured_transporters_and_conditional_reference(tmp_path, case):
    inputs = fixtures.fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, case + "-constructor", inputs, error)
        raise
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    elapsed, reports = inputs["elapsed_start_s"], []
    for index, source in enumerate(captured["history"]):
        local = folder / ("pre-network-" + str(index))
        local.mkdir()
        answers, reused, transporter_answers = [], [], []
        transporter_local = folder / ("pre-transporters-" + str(index))
        transporter_local.mkdir()

        def observer(before, local=local, index=index, answers=answers, reused=reused):
            archive(tmp_path, case + "-pre-network-" + str(index), before)
            answers.extend(references(local, before))
            reused.append(feedback_checks.standalone(before))

        def transporter_observer(
            before,
            index=index,
            transporter_answers=transporter_answers,
            transporter_local=transporter_local,
        ):
            archive(tmp_path, case + "-pre-transporters-" + str(index), before)
            transporter_answers.extend(references(transporter_local, before))

        digest = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed, observer, transporter_observer)
        except Exception as error:
            archive_refusal(
                tmp_path, case + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == digest and len(answers) == len(transporter_answers) == 2
        material = source["material"]
        old.exact_phase(trial.material.pump.pump, material)
        for actual, expected in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (actual.stage, actual.ion_id) == (expected["stage"], expected["ion_id"])
            exact(actual.values, expected["values"])
        calcium_checks.compare_calcium(trial.material.calcium_handler, material)
        feedback_checks.compare_channel_routes(trial, material)
        feedback = trial.material.network_feedback
        compare_feedback(feedback, material["channel_capture"]["network_feedback"], completed=True)
        execution = feedback["transporter_execution"]
        exact_nested(
            execution, material["channel_capture"]["network_feedback"]["transporter_execution"]
        )
        assert execution["source_completed"]
        transporter_rows, transporter_errors, transporter_budgets, transporter_ledgers = (
            transporter_comparisons(execution, transporter_answers[0], transporter_answers[1])
        )
        archive(
            tmp_path,
            "transporter-errors-" + case + "-" + str(index),
            dict(
                fields=transporter_rows,
                errors=transporter_errors,
                budgets=transporter_budgets,
                ledgers=transporter_ledgers,
            ),
        )
        (transporter_local / "comparison.json").write_text(
            json.dumps(
                dict(
                    fields=transporter_rows,
                    actual_pre_transporter_only=True,
                    physical_global_conservation_credit=False,
                ),
                indent=2,
            )
            + "\n"
        )
        assert max(row["normalized_max_error"] for row in transporter_rows.values()) <= 1
        assert (
            max(
                row["normalized_max_error"]
                for key, row in transporter_rows.items()
                if key.startswith("reference/")
            )
            <= 0.1
        )
        if case in ("zero_capacity", "zero_rho"):
            for value in execution["fluxes_after"].values():
                np.testing.assert_array_equal(value, np.zeros(9))
        if case in ("nkcc_multiplier_two", "ncx_multiplier_three"):
            assert (
                max(
                    np.max(abs(row["observed_buffer_discrepancy_mM"]))
                    for row in transporter_ledgers
                )
                > 0
            )
        if case == "closed_boundary":
            assert any(
                np.any(np.asarray(value)[[1, 5, 6]] != 0)
                for value in execution["fluxes_after"].values()
            )

        for actual, expected in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            old.exact_gate(actual, expected)
        for actual, expected in zip(
            trial.candidate.channel_caches, material["channel_caches"], strict=True
        ):
            exact_nested(actual, expected)
        exact_nested(
            trial.candidate.network_controls,
            material["channel_capture"]["network_feedback"]["controls_after"],
        )
        exact_nested(
            trial.candidate.network_cache,
            material["channel_capture"]["network_feedback"]["cache_after"],
        )
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        count = len(binding.pump_binding.gated_binding.material_binding.ion_ids)
        n = len(binding.pump_binding.gated_binding.material_binding.cell_ids)
        np.testing.assert_array_equal(
            feedback["cache_after"]["delta_conc"][:count], np.zeros((count, n))
        )
        assert feedback["rhs"]["growth_rates"].shape == (2, n)
        assert feedback["rhs"]["all_rates"].shape == (
            2 + len(binding.definition["network"]["reactions"]),
            n,
        )
        assert (
            feedback["molecular_transports_completed"] == 2 and len(feedback["mover_frames"]) == 8
        )
        assert trial.candidate.pump.gated.material.step_index == index + 1
        assert trial.clock["elapsed_start_s"] == elapsed
        if case == "transporter_only":
            for mol in feedback["molecule_states_after"].values():
                np.testing.assert_array_equal(mol["f_mem"], np.zeros(9))
        rows, errors, budgets, ledger = local_comparisons(
            binding, trial, answers[0], answers[1], reused[0]
        )
        archive(
            tmp_path,
            "local-errors-" + case + "-" + str(index),
            dict(fields=rows, errors=errors, budgets=budgets, ledger=ledger),
        )
        (local / "comparison.json").write_text(
            json.dumps(
                dict(
                    fields=rows,
                    conditional_pre_network_only=True,
                    physical_global_conservation_credit=False,
                ),
                indent=2,
            )
            + "\n"
        )
        assert max(row["normalized_max_error"] for row in rows.values()) <= 1
        assert (
            max(
                row["normalized_max_error"]
                for name, row in rows.items()
                if name.startswith("reference/")
            )
            <= 0.1
        )
        reports.append(
            rows | {"transporter/" + key: value for key, value in transporter_rows.items()}
        )
        parent, elapsed = trial.candidate, trial.clock["elapsed_end_s"]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                conditional_pre_network_checks=3,
                conditional_pre_transporter_checks=3,
                native_configured_transporter_calls=3,
                source_buffer_discrepancy_preserved=True,
                source_bath_update_preserved=True,
                carried_reference_forms=0,
                real_molecules=2,
                completed_mover_invocations=6,
                executed_chemistry=case != "transporter_only",
                case_role=inputs["case_role"],
                physical_global_conservation_credit=False,
                no_upstream_or_trajectory_accuracy_claim=True,
                maximum_error_fraction=max(
                    row["normalized_max_error"] for rows in reports for row in rows.values()
                ),
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_native_transporter_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    binding, parent = seed(inputs)
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 1
    material = captured["history"][0]["material"]
    assert material["failure"]["type"] == "IndexError"
    digest = ions.digest(parent)
    with pytest.raises(joined.ChannelJoinRejected) as caught:
        advance(
            inputs,
            binding,
            parent,
            0,
            inputs["elapsed_start_s"],
            transporter_observer=lambda before: archive(
                tmp_path, case + "-actual-pre-transporters", before
            ),
        )
    archive_refusal(tmp_path, case, dict(inputs=inputs, parent=parent), caught.value)
    assert ions.digest(parent) == digest
    actual = caught.value.network["network_feedback"]["transporter_execution"]
    source = material["channel_capture"]["network_feedback"]["transporter_execution"]
    exact_nested(actual, source)
    assert not actual["source_completed"]
    stages = [(row["stage"], row["name"]) for row in actual["frames"]]
    assert stages[-1] == ("reactant_commit", "subset_export")
    completed = sum(stage == "after" for stage, _ in stages)
    assert completed == (0 if case == "first_subset_partial" else 1)
    # The source adds current over ALL membranes before target writes. Its
    # internal reactant commits bulk cell1 and membrane3:6, then fails in env.
    before = next(
        row
        for row in actual["frames"]
        if row["stage"] == "before" and row["name"] == "subset_export"
    )
    final = actual["concentrations_after"]
    assert np.any(actual["extra_current_after_A_m2"] != before["extra_current_A_m2"])
    assert final["cell_concs"]["Na"][1] != before["concentrations"]["cell_concs"]["Na"][1]
    assert np.any(
        final["mem_concs"]["Na"][[3, 4, 5]]
        != before["concentrations"]["mem_concs"]["Na"][[3, 4, 5]]
    )
    np.testing.assert_array_equal(
        final["env_concs"]["Na"], before["concentrations"]["env_concs"]["Na"]
    )
    causes, error = [], caught.value
    while error is not None:
        causes.append(type(error).__name__)
        error = error.__cause__
    assert "IndexError" in causes
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                source_refused=True,
                source_failure=material["failure"],
                model_cause_types=causes,
                completed_transporters=completed,
                partial_current_and_material_preserved=True,
                positive_transporter_credit=False,
                physical_conservation_credit=False,
                equation_or_mover_bypass=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_complete_transporter_dependencies(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    valid_binding, valid_parent = seed(inputs)
    ib = valid_binding.pump_binding.gated_binding.material_binding
    original_valence = np.asarray(
        tuple(ib.kernel.valence)
        + tuple(
            row["parameters"]["z"] for row in inputs["channel_definition"]["network"]["molecules"]
        ),
        np.float64,
    )
    component_axis = joined.network_source.integer_valences(original_valence)
    assert component_axis.dtype == np.int64 and np.array_equal(original_valence, component_axis)
    archive(
        tmp_path,
        dependency + "-valid-admission",
        dict(
            binding=valid_binding,
            parent=valid_parent,
            baseline_admitted=True,
            original_native_valence=original_valence,
            component_integer_axis=component_axis,
            lossless=True,
        ),
    )
    expected_messages = dict(
        missing_membrane_volume=(
            "Require configured transporters, membrane volumes and profile ownership"
        ),
        missing_configuration="Unsupported or incomplete native transporter configuration",
        unknown_profile="Require all targets or completely supplied named profiles",
        mitochondrial_zone="Require unique transporter names and supported cell reaction zone",
        missing_flux_cache="Require every owned transporter flux cache; no silent reset",
    )
    expected_message = expected_messages[dependency]
    network = inputs["channel_definition"]["network"]
    if dependency == "missing_membrane_volume":
        del network["membrane_volume_m3"]
    if dependency == "missing_configuration":
        del network["transporters"][0]["reactants"]
    if dependency == "unknown_profile":
        network["transporters"][0]["apply to"] = ["missing"]
    if dependency == "mitochondrial_zone":
        network["transporters"][0]["reaction zone"] = "mit"
    archive(tmp_path, dependency + "-dependency-inputs", inputs)
    if dependency == "missing_flux_cache":
        binding, parent = valid_binding, valid_parent
        cache = ions.data(parent.network_cache)
        del cache["transporter_fluxes"]
        altered = joined._state(
            binding,
            parent.pump,
            parent.channel_caches,
            parent.channel_calls,
            parent.initialization,
            parent.calcium_rate_proxy_mol_m2_s,
            parent.network_controls,
            cache,
        )
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs, binding, altered, 0, inputs["elapsed_start_s"])
    else:
        with pytest.raises(ValueError, match="^" + re.escape(expected_message) + "$") as caught:
            seed(inputs)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is ValueError and str(leaf) == expected_message
    if dependency == "missing_flux_cache":
        for invalid in (
            [0.5],
            [9.0],
            [-9],
            [-9223372036854775808],
            [float("nan")],
            [float("inf")],
            [True],
            [[1.0]],
        ):
            with pytest.raises(ValueError, match="finite integral valences"):
                joined.network_source.integer_valences(invalid)
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                dependency=dependency,
                lossless_component_valence_axis=True,
                component_axis_dtype="int64",
                expected_leaf_type="ValueError",
                actual_leaf_type=type(leaf).__name__,
                expected_message=expected_message,
                actual_message=str(leaf),
                intended_failure_reached=True,
                native_or_physical_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )
    archive(
        tmp_path,
        dependency + "-expected-refusal",
        dict(
            type=type(caught.value).__name__,
            message=str(caught.value),
            native_refusal_or_physical_case_credit=False,
        ),
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    shared = {
        "cells.core.grid",
        "cells.core.specs",
        "cells.core.runner",
        "cells.core.batch",
        "cells.ensemble.ionic",
        "cells.core.surface_cotransport_water_spec",
        "cells.models.surface_energy",
        "cells.models.surface_energy_water",
    }
    assert not shared.intersection(sys.modules)
    runtime = runtime_inventory()
    if cpu := os.environ.get("CELLS_TRANSPORTER_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

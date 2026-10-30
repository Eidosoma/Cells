"""Prepared true molecule chemistry/mover checks; no new numerical run yet."""

import copy
import json
import os
import subprocess
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_molecule_join as joined
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit import test_betse_normal_network_join as feedback_checks
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_molecule_join_fixtures as fixtures
from validation.betse import betse_normal_molecule_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

RATE_TOLERANCES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "validation/chemistry/betse_network_reactions_protocol.json"
    ).read_text()
)["tolerances"]


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-molecule-join"


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


def advance(inputs, binding, parent, index, elapsed, observer=None):
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
        "validation.betse.betse_normal_molecule_join_native",
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
            "validation.betse.betse_normal_molecule_join_reference",
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


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_chemical_transport_and_conditional_reference(tmp_path, case):
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
        answers, reused = [], []

        def observer(before, local=local, index=index, answers=answers, reused=reused):
            archive(tmp_path, case + "-pre-network-" + str(index), before)
            answers.extend(references(local, before))
            reused.append(feedback_checks.standalone(before))

        digest = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed, observer)
        except Exception as error:
            archive_refusal(
                tmp_path, case + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == digest and len(answers) == 2
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
        if case in ("reaction_only", "growth_only", "zero_Dm_GJ"):
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
        reports.append(rows)
        parent, elapsed = trial.candidate, trial.clock["elapsed_end_s"]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                conditional_pre_network_checks=3,
                carried_reference_forms=0,
                real_molecules=2,
                completed_mover_invocations=6,
                executed_chemistry=case != "transport_only",
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
def test_native_molecule_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    binding, parent = seed(inputs)
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 1
    material = captured["history"][0]["material"]
    assert material["failure"]["type"] == "BetseSimUnstableException"
    digest = ions.digest(parent)
    with pytest.raises(joined.ChannelJoinRejected) as caught:
        advance(
            inputs,
            binding,
            parent,
            0,
            inputs["elapsed_start_s"],
            lambda before: archive(tmp_path, case + "-actual-pre-network", before),
        )
    archive_refusal(tmp_path, case, dict(inputs=inputs, parent=parent), caught.value)
    assert ions.digest(parent) == digest
    feedback = caught.value.network["network_feedback"]
    compare_feedback(feedback, material["channel_capture"]["network_feedback"], completed=False)
    assert feedback["chemical_rhs_evaluated"] and feedback["executed_chemistry"]
    assert feedback["molecular_transports_completed"] == (
        0 if case == "first_molecule_negative" else 1
    )
    causes = []
    error = caught.value
    while error is not None:
        causes.append(type(error).__name__)
        error = error.__cause__
    assert "BetseSimUnstableException" in causes
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                source_refused=True,
                source_failure=material["failure"],
                model_cause_types=causes,
                completed_transports=feedback["molecular_transports_completed"],
                positive_chemistry_credit=False,
                physical_conservation_credit=False,
                equation_or_mover_bypass=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_complete_molecule_dependencies(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    network = inputs["channel_definition"]["network"]
    if dependency == "missing_molecule_state":
        del network["molecules"][0]["initial"]["c_env"]
    if dependency == "intracellular_field":
        network["molecules"][0]["parameters"]["update_intra_conc"] = True
    if dependency == "radius_mismatch":
        network["radius_m"][0] *= 2
    if dependency == "GRN_owner":
        network["owner"] = "grn"
    archive(tmp_path, dependency + "-dependency-inputs", inputs)
    with pytest.raises((ValueError, joined.MissingCoupledState)) as caught:
        seed(inputs)
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
    if cpu := os.environ.get("CELLS_MOLECULE_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

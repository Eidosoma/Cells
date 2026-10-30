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
from cells.processes import betse_normal_grn_join as joined
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit import test_betse_normal_network_join as feedback_checks
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_grn_join_fixtures as fixtures
from validation.betse import betse_normal_grn_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

RATE_TOLERANCES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "validation/chemistry/betse_network_reactions_protocol.json"
    ).read_text()
)["tolerances"]


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-grn-join"


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
        "validation.betse.betse_normal_grn_join_native",
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
            "validation.betse.betse_normal_grn_join_reference",
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


def cold_comparisons(cache, lower, target):
    rows, errors, budgets = {}, {}, {}
    raw = cache["wire"]
    assert dict(raw["owner_fields"]) == target["owner_fields"]
    assert (
        raw["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"] is True
    )
    for name, fields in target["molecule_fields"].items():
        actual = raw["molecule_fields"][name]
        for key, wanted in fields.items():
            value = actual[key]
            if wanted is None or type(wanted) is bool:
                assert value is wanted
                continue
            a, b, less = (
                np.asarray(value, np.float64),
                np.asarray(wanted, np.float64),
                np.asarray(lower["molecule_fields"][name][key], np.float64),
            )
            np.testing.assert_array_equal(a, b)
            np.testing.assert_array_equal(less, b)
            budget = np.full(a.shape, FLOORS["cell_mol_m3"])
            rows[name + "/" + key] = old.metric(a, b, budget)
            rows["reference/" + name + "/" + key] = old.metric(less, b, budget)
            errors[name + "/" + key], budgets[name + "/" + key] = abs(a - b), budget
    matrix = np.asarray(target["reaction_matrix"])
    rows["reaction_matrix"] = old.metric(
        raw["core_fields"]["reaction_matrix"], matrix, np.full(matrix.shape, 1e-25)
    )
    errors["reaction_matrix"], budgets["reaction_matrix"] = (
        abs(raw["core_fields"]["reaction_matrix"] - matrix),
        np.full(matrix.shape, 1e-25),
    )
    assert set(raw["simulator_fields"]) == set(target["simulator_fields"])
    for key, value in target["simulator_fields"].items():
        np.testing.assert_array_equal(raw["simulator_fields"][key], np.asarray(value))
        budget = np.full(np.asarray(value).shape, 1e-25)
        rows["simulator/" + key] = old.metric(raw["simulator_fields"][key], value, budget)
        errors["simulator/" + key], budgets["simulator/" + key] = (
            abs(raw["simulator_fields"][key] - value),
            budget,
        )
    return rows, errors, budgets


@pytest.mark.parametrize("case", fixtures.CASES)
def test_genuine_grn_owner_and_conditional_reference(tmp_path, case):
    inputs = fixtures.fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    cold_folder = preparation / "cold-initialization"
    cold_folder.mkdir()
    cold_inputs = dict(
        mode="cold_initialization",
        network=inputs["channel_definition"]["network"],
        ion_ids=inputs["ion_definition"]["ions"]["ids"],
        cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),
    )
    cold_answers = references(cold_folder, cold_inputs)
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, case + "-constructor", inputs, error)
        raise
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    native_cold = captured["history"][0]["material"]["channel_capture"]["network_feedback"][
        "cache_before"
    ]
    exact_nested(parent.network_cache, native_cold)
    cold_rows, cold_errors, cold_budgets = cold_comparisons(
        parent.network_cache, cold_answers[0], cold_answers[1]
    )
    archive(
        tmp_path,
        case + "-cold-errors",
        dict(
            fields=cold_rows,
            errors=cold_errors,
            budgets=cold_budgets,
            actual=parent.network_cache,
            lower=cold_answers[0],
            target=cold_answers[1],
            exact_initial_assignments=True,
        ),
    )
    (cold_folder / "comparison.json").write_text(
        json.dumps(
            dict(
                fields=cold_rows,
                actual_cold_configuration_only=True,
                physical_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert max(row["normalized_max_error"] for row in cold_rows.values()) <= 1

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
        exact_nested(
            feedback["grn_owner"], material["channel_capture"]["network_feedback"]["grn_owner"]
        )
        exact_nested(
            feedback["grn_owner_after"],
            material["channel_capture"]["network_feedback"]["grn_owner_after"],
        )
        assert (
            feedback["grn_owner"]["owner_class"] == "MasterOfGenes"
            and feedback["grn_owner"]["core_class"] == "MasterOfNetworks"
        )
        assert (
            feedback["grn_owner"]["actual_core_identity"]
            and feedback["grn_owner"]["grn_enabled"]
            and not feedback["grn_owner"]["molecules_enabled"]
        )
        expected = (
            ("clear_run_loop",)
            + (
                ("run_loop_modulators",)
                if inputs["channel_definition"]["network"]["modulators"]
                else ()
            )
            + ("run_loop",)
        )
        assert (
            tuple(feedback["grn_dispatch_stages"])
            == tuple(material["channel_capture"]["network_feedback"]["grn_dispatch_stages"])
            == expected
        )
        assert material["channel_capture"]["network_feedback"]["cold_initialization"] == (
            index == 0
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
                executed_chemistry=True,
                genuine_grn_owner_dispatch=True,
                cold_initialization_checks=1,
                cold_reference_forms=2,
                cold_phase="constructor; native before first ordinary call",
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
def test_genuine_grn_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-inputs", inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 1
    if case.startswith("cold_"):
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            seed(inputs)
        archive_refusal(tmp_path, case, inputs, caught.value)
        source = captured["channel_initialization_failure"]
        exact_nested(caught.value.initialization, source)
        assert (
            source["source_exception"] == "KeyError"
            and source["stage"] == caught.value.stage == "grn_initialization"
        )
        assert source["actual_grn_enabled"] and not source["actual_molecules_enabled"]
        fields = source["owner_snapshot"]["molecule_fields"]
        assert fields["X"]["c_cells"].shape == (3,) and fields["Y"]["c_cells"].shape == (3,)
        assert (fields["X"]["Dm"] is not None) == ("second" in case)
        assert fields["Y"]["Dm"] is None
        failure = dict(
            source_refused=True,
            source_type="KeyError",
            cold_initialization_failure=True,
            partial_owner_fields_preserved=True,
            completed_transports=0,
            positive_grn_credit=False,
            physical_conservation_credit=False,
        )
    else:
        try:
            binding, parent = seed(inputs)
        except Exception as error:
            archive_refusal(tmp_path, case + "-unexpected-constructor", inputs, error)
            raise
        digest = ions.digest(parent)
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(
                inputs,
                binding,
                parent,
                0,
                inputs["elapsed_start_s"],
                lambda before: archive(tmp_path, case + "-pre-network", before),
            )
        archive_refusal(tmp_path, case, dict(inputs=inputs, parent=parent), caught.value)
        assert digest == ions.digest(parent)
        feedback = caught.value.network["network_feedback"]
        material = captured["history"][0]["material"]
        compare_feedback(feedback, material["channel_capture"]["network_feedback"], completed=False)
        exact_nested(
            feedback["grn_owner_after"],
            material["channel_capture"]["network_feedback"]["grn_owner_after"],
        )
        assert material["failure"]["type"] == "BetseSimUnstableException"
        expected = 0 if "first" in case else 1
        assert feedback["molecular_transports_completed"] == expected
        failure = dict(
            source_refused=True,
            source_type="BetseSimUnstableException",
            cold_initialization_failure=False,
            partial_owner_fields_preserved=True,
            completed_transports=expected,
            positive_grn_credit=False,
            physical_conservation_credit=False,
        )
    (folder / "raw-retention.json").write_text(json.dumps(failure, indent=2) + "\n")


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_complete_grn_dependencies(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    try:
        valid_binding, valid_parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, dependency + "-unexpected-valid-constructor", inputs, error)
        raise
    archive(
        tmp_path,
        dependency + "-valid-admission",
        dict(
            binding=valid_binding,
            parent=valid_parent,
            baseline_admitted=True,
            genuine_grn_owner=True,
        ),
    )
    expected_messages = dict(
        wrong_owner="Require an actual configured GRN owner and complete initialization context",
        intracellular_field="Require the bounded neutral, instant-mixing native GRN configuration",
        charged_gene="Require the bounded neutral, instant-mixing native GRN configuration",
        missing_owner_cache="Require all GRN owner/cache fields",
        missing_source_default="Missing source-initialized GRN molecule fields",
    )
    net = inputs["channel_definition"]["network"]
    if dependency == "wrong_owner":
        net["owner"] = "molecules"
    if dependency == "intracellular_field":
        net["grn_configuration"]["biomolecules"][0]["update intracellular"] = True
    if dependency == "charged_gene":
        net["grn_configuration"]["biomolecules"][0]["z"] = 1.0
    archive(tmp_path, dependency + "-inputs", inputs)
    if dependency in ("missing_owner_cache", "missing_source_default"):
        binding, parent = valid_binding, valid_parent
        cache = ions.data(parent.network_cache)
        if dependency == "missing_owner_cache":
            del cache["wire"]["owner_fields"]
        else:
            del cache["wire"]["molecule_fields"]["X"]["ignore_ECM_pump"]
        changed = joined._state(
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
            advance(inputs, binding, changed, 0, inputs["elapsed_start_s"])
    else:
        with pytest.raises(ValueError) as caught:
            seed(inputs)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is ValueError and str(leaf) == expected_messages[dependency]
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                dependency=dependency,
                genuine_grn_owner=True,
                expected_message=expected_messages[dependency],
                actual_message=str(leaf),
                actual_leaf_type=type(leaf).__name__,
                intended_failure_reached=True,
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )
    archive(
        tmp_path,
        dependency + "-expected-refusal",
        dict(
            type=type(caught.value).__name__, message=str(caught.value), source_failure_credit=False
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
    if cpu := os.environ.get("CELLS_GRN_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

"""Prepared standalone GRN qualification; this module is not collected in preparation."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_sim_grn as model
from tests.unit import test_betse_normal_grn_join as old
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS
from validation.betse import betse_sim_grn_fixtures as fixtures
from validation.betse import betse_sim_grn_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "sim-grn"


def archive(tmp_path, name, value):
    return native.archive_native.write_archive(root(tmp_path) / name, ions.data(value))


def isolated(tmp_path, inputs):
    folder = root(tmp_path) / ("isolated-" + inputs["case_id"])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_sim_grn_native",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "native"),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    result = archive_read(folder / "native")
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["RNG_unchanged"] and result["normal_solver_executed"] is False
    return folder, result


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(old.old.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_sim_grn_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(path),
                    "--refinement",
                    str(level),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        answer = json.loads(path.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        assert answer["carried_reference_forms"] == 0
        assert answer["decimal_precision"] == (90 if level == 1 else 140)
        answers.append(answer)
    return answers


def report(folder, actual, expected, lower, budget, unit):
    a, b = np.asarray(actual, np.float64), np.asarray(expected, np.float64)
    budget = np.broadcast_to(budget, a.shape)
    return dict(
        field=folder,
        actual=a,
        expected=b,
        lower=np.asarray(lower),
        error=abs(a - b),
        budget=budget,
        unit=unit,
        metric=old.old.metric(a, b, budget),
        resolution=old.old.metric(lower, b, budget),
    )


def check_rows(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows))
    metrics = {key: value["metric"] for key, value in rows.items()}
    resolutions = {key: value["resolution"] for key, value in rows.items()}
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                fields=metrics,
                resolutions=resolutions,
                fresh_conditional_reference=True,
                physical_global_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert rows and max(v["normalized_max_error"] for v in metrics.values()) <= 1
    assert max(v["normalized_max_error"] for v in resolutions.values()) <= 0.1


def cold_inputs(inputs):
    return dict(
        mode="cold_initialization",
        network=inputs["network"],
        ion_ids=inputs["ion_definition"]["ions"]["ids"],
        cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),
        incoming_charge_C_m3=inputs["incoming_charge_C_m3"],
        incoming_current_A_m2=inputs["incoming_current_A_m2"],
    )


def compare_cold(snapshot, lower, target):
    wire, rows = snapshot["wire"], {}
    assert dict(wire["owner_fields"]) == target["owner_fields"]
    assert wire["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"]
    for name, fields in target["molecule_fields"].items():
        for key, expected in fields.items():
            actual = wire["molecule_fields"][name][key]
            if expected is None or type(expected) is bool:
                assert actual is expected
            else:
                np.testing.assert_array_equal(actual, expected)
                rows[name + "/" + key] = report(
                    name + "/" + key,
                    actual,
                    expected,
                    lower["molecule_fields"][name][key],
                    FLOORS["cell_mol_m3"],
                    "source field",
                )
    rows["reaction_matrix"] = report(
        "reaction_matrix",
        wire["core_fields"]["reaction_matrix"],
        target["reaction_matrix"],
        lower["reaction_matrix"],
        1e-25,
        "stoichiometry",
    )
    assert set(wire["simulator_fields"]) == set(target["simulator_fields"])
    for key, wanted in target["simulator_fields"].items():
        np.testing.assert_array_equal(wire["simulator_fields"][key], wanted)
        rows[key] = report(
            key,
            wire["simulator_fields"][key],
            wanted,
            lower["simulator_fields"][key],
            1e-25,
            "C/m3" if "rho" in key else "A/m2",
        )
    return rows


def compare_local(step, lower, target):
    before, after = step["before"], step["after"]
    wire, rows = after["wire"], {}
    n, m, s = (
        len(before["molecular_geometry"]["cell_volume_m3"]),
        len(before["gap_open"]),
        len(before["ion_ids"]),
    )
    factor = 128 * np.finfo(float).eps * (s + 2 + n + m + 64)
    tolerance = old.RATE_TOLERANCES
    for key in ("growth_rates", "reaction_rates", "all_rates"):
        wanted = np.asarray(target["rhs"][key])
        budget = tolerance["rate_atol_mM_s"] + tolerance["relative"] * abs(wanted)
        rows["rhs/" + key] = report(
            key, step["rhs"][key], wanted, lower["rhs"][key], budget, "mM/s"
        )
    rows["delta_conc"] = report(
        "delta_conc",
        wire["core_fields"]["delta_conc"],
        target["delta_conc"],
        lower["delta_conc"],
        3 * tolerance["rate_atol_mM_s"] + tolerance["relative"] * np.asarray(target["delta_gross"]),
        "mM/s",
    )
    for name, wanted in target["molecules_after"].items():
        actual = wire["molecule_fields"][name]
        for key in ("c_cells", "cc_at_mem", "c_env", "f_mem", "f_gj"):
            floor = (
                FLOORS["membrane_flux_mol_m2_s"]
                if key.startswith("f_")
                else FLOORS["bath_mol_m3"]
                if key == "c_env"
                else FLOORS["cell_mol_m3"]
            )
            budget = floor + factor * np.asarray(target["gross_molecules"][name][key])
            rows[name + "/" + key] = report(
                name + "/" + key,
                actual[key],
                wanted[key],
                lower["molecules_after"][name][key],
                budget,
                "mol/m2/s" if key.startswith("f_") else "mol/m3",
            )
        np.testing.assert_array_equal(
            actual["flux_intra"], before["molecule_states_before"][name]["flux_intra"]
        )
        volume = np.asarray(before["molecular_geometry"]["cell_volume_m3"])
        bath = before["bath_volume_m3"]
        previous = before["molecule_states_before"][name]
        initial_cell = np.sum(np.asarray(previous["c_cells"]) * volume)
        final_cell = np.sum(actual["c_cells"] * volume)
        initial_env = np.mean(previous["c_env"]) * bath
        final_env = np.mean(actual["c_env"]) * bath
        book = target["balances"][name]
        transfer = book["chemical_source_mol"] + book["directed_GJ_change_mol"]
        gross = sum(
            abs(book[k])
            for k in (
                "initial_amount_mol",
                "final_amount_mol",
                "chemical_source_mol",
                "directed_GJ_change_mol",
            )
        )
        budget = factor * gross + FLOORS["cell_mol_m3"] * np.sum(volume)
        budget += FLOORS["bath_mol_m3"] * m * bath
        rows[name + "/source_effective_amount"] = report(
            name,
            final_cell + m * final_env - initial_cell - m * initial_env - transfer,
            book["source_effective_residual_mol"],
            lower["balances"][name]["source_effective_residual_mol"],
            budget,
            "mol",
        )
        rows[name + "/declared_bath_source_defect"] = report(
            name,
            final_cell + final_env - initial_cell - initial_env - transfer,
            book["expected_single_bath_defect_mol"],
            lower["balances"][name]["expected_single_bath_defect_mol"],
            budget,
            "mol",
        )
    sim = after["simulator"]
    np.testing.assert_array_equal(sim["vm"], target["voltage_after_V"])
    np.testing.assert_array_equal(sim["vgj"], target["junction_voltage_after_V"])
    for actual_key, input_key in (
        ("cc_cells", "cell_mol_m3"),
        ("cc_at_mem", "membrane_mol_m3"),
        ("cc_env", "bath_mol_m3"),
    ):
        np.testing.assert_array_equal(sim[actual_key], before["values_before"][input_key])
    for key in ("gj_block", "NaKATP_block"):
        np.testing.assert_array_equal(sim[key], before["controls_before"][key])
        np.testing.assert_array_equal(sim[key], target["controls_after"][key])
    assert (
        after["parameters"]["substances_affect_charge"]
        is before["substances_affect_charge"]
        is False
    )
    np.testing.assert_array_equal(sim["extra_J_mem"], before["incoming_channel_current_A_m2"])
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_standalone_grn_advancing_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cold_folder = preparation / "cold"
    cold = references(cold_folder, cold_inputs(inputs))
    try:
        binding = model.bind(inputs)
        parent = model.initialize(binding)
    except Exception as error:
        archive(
            tmp_path,
            case + "-unexpected-cold",
            dict(
                inputs=inputs,
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 2
    old.exact_nested(parent.snapshot, captured["cold"])
    rows = compare_cold(parent.snapshot, cold[0], cold[1])
    check_rows(tmp_path, case + "-cold-errors", cold_folder, rows)
    total_steps = 0
    for invocation, native_call in enumerate(captured["history"]):
        clock_folder = preparation / ("clock-" + str(invocation))
        clock = references(
            clock_folder, dict(mode="standalone_clock", call=inputs["calls"][invocation])
        )
        answers = []

        def before_step(before, invocation=invocation, answers=answers):
            point = len(answers)
            path = preparation / ("call-" + str(invocation) + "-point-" + str(point))
            answers.append((path, references(path, before)))

        digest = ions.digest(parent)
        try:
            candidate, trace = model.advance(binding, parent, before_step=before_step)
        except Exception as error:
            archive(
                tmp_path,
                case + "-unexpected-call-" + str(invocation),
                dict(
                    parent=parent,
                    inputs=inputs,
                    error=str(error),
                    traceback=traceback.format_exc(),
                    partial=getattr(error, "partial", None),
                ),
            )
            raise
        archive(
            tmp_path,
            case + "-call-" + str(invocation),
            dict(parent=parent, candidate=candidate, trace=trace),
        )
        assert digest == ions.digest(parent)
        old.exact_nested(candidate.snapshot, native_call["snapshot"])
        old.exact_nested(trace, native_call["trace"])
        clock_actual = trace["events"][0]["clock"]
        assert trace["events"][0]["stage"] == "before_reinitialize"
        np.testing.assert_array_equal(clock_actual["tt"], clock[1]["tt"])
        np.testing.assert_array_equal(clock_actual["tsamples"], clock[1]["sample_times"])
        np.testing.assert_array_equal(clock[0]["tt"], clock[1]["tt"])
        np.testing.assert_array_equal(clock[0]["sample_times"], clock[1]["sample_times"])
        assert len(trace["steps"]) == len(answers) == clock[1]["steps"]
        expected = clock[1]["sample_times"]
        np.testing.assert_array_equal(candidate.snapshot["wire"]["owner_fields"]["time"], expected)
        np.testing.assert_array_equal(
            candidate.snapshot["simulator"]["time"],
            list(parent.snapshot["simulator"]["time"]) + expected,
        )
        for key in ("extra_rho_cells", "extra_J_mem", "c_env_bound"):
            np.testing.assert_array_equal(
                candidate.snapshot["simulator"][key], parent.snapshot["simulator"][key]
            )
        for name, fields in parent.snapshot["wire"]["molecule_fields"].items():
            for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra"):
                np.testing.assert_array_equal(
                    trace["steps"][0]["before"]["molecule_states_before"][name][key], fields[key]
                )
            saved = candidate.snapshot["wire"]["molecule_fields"][name]
            assert len(saved["c_cells_time"]) == len(expected)
            for sample, index in enumerate(clock[1]["sample_indices"]):
                source = trace["steps"][index]["after"]["wire"]["molecule_fields"][name]
                for key, time_key in (
                    ("c_cells", "c_cells_time"),
                    ("cc_at_mem", "c_mems_time"),
                    ("c_env", "c_env_time"),
                ):
                    np.testing.assert_array_equal(saved[time_key][sample], source[key])
        assert [event["operation"] for event in trace["io_events"]] == [
            "saveSim",
            "make_unless_dir",
            "CSV",
            "CSV",
        ]
        assert all(event["persistence_executed"] is False for event in trace["io_events"])
        assert len(candidate.snapshot["captured_files"]) == 2
        assert candidate.snapshot["parameters"]["dt"] == inputs["calls"][invocation]["dt_s"]
        for point, (step, (path, forms)) in enumerate(zip(trace["steps"], answers, strict=True)):
            rows = compare_local(step, forms[0], forms[1])
            check_rows(
                tmp_path, case + "-local-errors-" + str(invocation) + "-" + str(point), path, rows
            )
        (clock_folder / "comparison.json").write_text(
            json.dumps(
                dict(
                    exact_native_clock=True,
                    independent_clock=True,
                    steps=len(trace["steps"]),
                    clock_reference_forms=2,
                    physical_conservation_credit=False,
                ),
                indent=2,
            )
            + "\n"
        )
        total_steps += len(trace["steps"])
        parent = candidate
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                standalone_run_core_sim=True,
                normal_solver_executed=False,
                advancing_invocations=2,
                actual_core_calls=total_steps,
                warm_reference_forms=2 * total_steps,
                cold_reference_forms=2,
                clock_reference_forms=4,
                carried_reference_forms=0,
                complete_public_state_carry=True,
                real_reinitialize_and_cache_reset=True,
                force_publication_off=True,
                configured_modulators_dispatched=False,
                physical_global_conservation_credit=False,
                file_persistence_credit=False,
                case_role=inputs["case_role"],
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_standalone_grn_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_refused"
    expected = (
        "KeyError"
        if case in ("cold_missing_Y_Dm", "second_call_missing_Y_Dm")
        else "BetseSimConfException"
        if case == "late_plot_cell"
        else "BetseSimUnstableException"
    )
    assert captured["failure"]["type"] == expected
    try:
        binding = model.bind(inputs)
        parent = model.initialize(binding)
        for invocation in range(len(inputs["calls"])):
            digest = ions.digest(parent)
            candidate, trace = model.advance(binding, parent)
            assert digest == ions.digest(parent)
            old.exact_nested(candidate.snapshot, captured["history"][invocation]["snapshot"])
            old.exact_nested(trace, captured["history"][invocation]["trace"])
            parent = candidate
    except model.StandaloneRejected as error:
        archive(
            tmp_path,
            case + "-partial",
            dict(error=str(error), partial=error.partial, traceback=traceback.format_exc()),
        )
        partial = error.partial
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert type(leaf).__name__ == expected
        assert str(leaf) == captured["failure"]["message"]
        native_partial = (
            captured["partial"]
            if case == "cold_missing_Y_Dm"
            else captured["history"][-1]["snapshot"]
        )
        old.exact_nested(partial["snapshot"], native_partial)
        if case != "cold_missing_Y_Dm":
            assert digest == ions.digest(parent)
            old.exact_nested(partial["trace"], captured["history"][-1]["trace"])
        if case == "second_call_missing_Y_Dm":
            assert len(captured["history"]) == 2 and not partial["trace"]["steps"]
            for name, fields in parent.snapshot["wire"]["molecule_fields"].items():
                for key in ("c_cells", "c_env", "c_cells_time"):
                    old.exact_nested(
                        partial["snapshot"]["wire"]["molecule_fields"][name][key], fields[key]
                    )
        if case == "late_plot_cell":
            assert len(partial["trace"]["steps"]) == 3
            assert [e["operation"] for e in partial["trace"]["io_events"]] == [
                "saveSim",
                "make_unless_dir",
            ]
        if case in ("first_negative", "second_negative"):
            completed = sum(
                frame["stage"] == "transport_after" for frame in partial["trace"]["molecule_frames"]
            )
            assert completed == (0 if case == "first_negative" else 1)
            assert len(partial["trace"]["steps"]) == 1
            assert not partial["trace"]["io_events"]
    except Exception as error:
        archive(
            tmp_path,
            case + "-unexpected-refusal",
            dict(error=str(error), traceback=traceback.format_exc()),
        )
        raise
    else:
        raise AssertionError("Intended standalone source failure not reached")
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                source_refused=True,
                source_type=expected,
                intended_failure=case,
                partial_state_and_clock_preserved=True,
                exact_native_partial=True,
                positive_credit=False,
                physical_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_standalone_grn_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture()
    try:
        binding = model.bind(inputs)
        parent = model.initialize(binding)
    except Exception as error:
        archive(
            tmp_path,
            dependency + "-unexpected-valid-constructor",
            dict(
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    archive(tmp_path, dependency + "-valid-admission", dict(binding=binding, parent=parent))
    messages = dict(
        ECM="Standalone ECM requires a separate spatial phase",
        mitochondria="Standalone mitochondria require separate organelle state",
        fluid="Standalone fluid and cuts require separate phase dynamics",
        unsafe_sampling="Sampling below dt stalls the source sampling-index loop",
        missing_owner_state="Require complete standalone owner state",
        missing_boundary_state="Require standalone boundary state",
        file_restart="File restart requires a separate persistence boundary",
    )
    if dependency in ("missing_owner_state", "missing_boundary_state"):
        raw = ions.data(parent.snapshot)
        del raw["wire"][
            "owner_fields" if dependency == "missing_owner_state" else "ion_boundary_state"
        ]
        changed = model.state(binding, raw, 0)
        with pytest.raises(ValueError) as caught:
            model.advance(binding, changed)
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "ECM":
            changed["ion_definition"]["parameters"]["is_ecm"] = True
        elif dependency in ("mitochondria", "fluid"):
            changed["scope"][dependency] = True
        elif dependency == "unsafe_sampling":
            changed["calls"][0]["sample_s"] = 0.001
        else:
            changed["scope"]["grn_unpickle_filename"] = "/uncaptured/restart.pickle"
        archive(tmp_path, dependency + "-inputs", changed)
        with pytest.raises(ValueError) as caught:
            model.bind(changed)
    archive(
        tmp_path,
        dependency + "-refusal",
        dict(message=str(caught.value), type=type(caught.value).__name__),
    )
    assert type(caught.value) is ValueError and str(caught.value) == messages[dependency]
    folder = root(tmp_path)
    (folder / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_leaf_type="ValueError",
                expected_message=messages[dependency],
                actual_message=str(caught.value),
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    receipt = inventory()
    if cpu := os.environ.get("CELLS_SIM_GRN_CPU"):
        assert receipt["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")

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

from cells.processes import betse_ecm_sim_grn as model
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_grn_join as old
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS
from validation.betse import betse_ecm_sim_grn_fixtures as fixtures
from validation.betse import betse_ecm_sim_grn_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "ecm-sim-grn"


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
                "validation.betse.betse_ecm_sim_grn_native",
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
                    "validation.betse.betse_ecm_sim_grn_reference",
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
        assert answer["decimal_precision"] == (100 if level == 1 else 160)
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
    declaration = inputs["material_definition"]
    ids = declaration["environment_geometry_definition"]["current_definition"]["ions"]["ids"]
    return dict(
        mode="cold_initialization",
        network=inputs["network"],
        material_declaration=declaration,
        ion_ids=ids,
        cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),
        environment_sites=len(inputs["initial"]["environment_mol_m3"][0]),
        incoming_publication_fields=inputs["incoming_publication_fields"],
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
    for actual_key, reference_key in (
        ("map_mem2ecm", "membrane_to_grid"),
        ("map_cell2ecm", "cell_to_grid"),
    ):
        np.testing.assert_array_equal(
            snapshot["grid_fields"][actual_key], target["independent_geometry"][reference_key]
        )
    for actual_key, reference_key in (
        ("X", "X_m"),
        ("Y", "Y_m"),
        ("memSa_per_envSquare", "membrane_area_per_site_m2"),
        ("M_divmap_mem2ecm", "membrane_divergence_map_m2"),
        ("true_ecm_vol", "true_environment_volume_m3"),
    ):
        wanted = np.asarray(target["independent_geometry"][reference_key], np.float64)
        rows["grid/" + actual_key] = report(
            actual_key,
            snapshot["grid_fields"][actual_key],
            wanted,
            lower["independent_geometry"][reference_key],
            3e-13 + 6e-12 * abs(wanted),
            "input-derived geometry",
        )
    return rows


def comparisons():
    rows = {}

    def add(name, actual, target, lower, budget, unit):
        a, b = np.asarray(actual, np.float64), np.asarray(target, np.float64)
        budget = np.broadcast_to(budget, a.shape)
        rows[name] = dict(
            actual=a,
            target=b,
            lower=np.asarray(lower),
            error=abs(a - b),
            budget=budget,
            unit=unit,
            metric=old.old.metric(a, b, budget),
            resolution=old.old.metric(lower, b, budget),
        )

    return rows, add


def compare_ecm_local(feedback, lower, target):
    before = feedback["before"]
    actual = feedback["cache_after"]["wire"]
    n, m = (len(before["molecular_geometry"]["cell_volume_m3"]), len(before["gap_open"]))
    e = len(before["values_before"]["environment_mol_m3"][0])
    factor = 128 * np.finfo(float).eps * (len(before["ion_ids"]) + 2 + n + m + e + 64)
    rows, add = comparisons()
    for key in ("growth_rates", "reaction_rates", "all_rates"):
        wanted = np.asarray(target["rhs"][key])
        add(
            "rhs/" + key,
            feedback["rhs"][key],
            wanted,
            lower["rhs"][key],
            2e-14 + 5e-12 * abs(wanted),
            "mM/s",
        )
    add(
        "delta",
        actual["core_fields"]["delta_conc"],
        target["delta_conc"],
        lower["delta_conc"],
        6e-14 + 5e-12 * np.asarray(target["delta_gross"]),
        "mM/s",
    )
    volumes = np.asarray(before["molecular_geometry"]["cell_volume_m3"])
    for name, wanted in target["molecules_after"].items():
        fields = actual["molecule_fields"][name]
        for key in ("c_cells", "cc_at_mem", "c_env", "f_mem", "f_gj", "fenvx", "fenvy"):
            floor = 1e-18 if key.startswith("f") else 3e-13
            budget = floor + factor * np.asarray(target["gross_molecules"][name][key])
            add(
                name + "/" + key,
                fields[key],
                wanted[key],
                lower["molecules_after"][name][key],
                budget,
                "mol/m2/s" if key.startswith("f") else "mol/m3",
            )
        book = target["balances"][name]
        previous = before["molecule_states_before"][name]
        volume = book["site_volume_m3"]
        old_amount = (
            np.sum(np.asarray(previous["c_cells"]) * volumes) + np.sum(previous["c_env"]) * volume
        )
        new_amount = np.sum(fields["c_cells"] * volumes) + np.sum(fields["c_env"]) * volume
        keys = (
            "chemical_source_mol",
            "directed_GJ_change_mol",
            "fast_exchange_defect_mol",
            "boundary_clamp_change_mol",
            "collocated_transport_change_mol",
            "smoothing_change_mol",
        )
        expected_terms = sum((book[k] for k in keys))
        gross = (
            sum((abs(book[k]) for k in keys))
            + abs(book["initial_amount_mol"])
            + abs(book["final_amount_mol"])
        )
        gross += book["native_true_volume_gross_mol"]
        budget = factor * gross + 3e-13 * (
            np.sum(volumes)
            + e * volume
            + np.sum(target["independent_geometry"]["true_environment_volume_m3"])
        )
        add(
            name + "/source_effective_amount",
            new_amount - old_amount - expected_terms,
            book["source_effective_residual_mol"],
            lower["balances"][name]["source_effective_residual_mol"],
            budget,
            "mol",
        )
        true_volume = np.asarray(target["independent_geometry"]["true_environment_volume_m3"])
        delta = np.sum((fields["c_cells"] - previous["c_cells"]) * volumes) + np.sum(
            (fields["c_env"] - previous["c_env"]) * true_volume
        )
        add(
            name + "/native_true_volume_change",
            delta,
            book["native_true_volume_total_change_mol"],
            lower["balances"][name]["native_true_volume_total_change_mol"],
            budget,
            "mol; no physical conservation credit",
        )
    for key in ("gj_block", "NaKATP_block"):
        add(
            "control/" + key,
            feedback["controls_after"][key],
            target["controls_after"][key],
            lower["controls_after"][key],
            3e-14 + 5e-12 * abs(np.asarray(target["controls_after"][key])),
            "factor",
        )
    np.testing.assert_array_equal(feedback["values_after"]["voltage_V"], target["voltage_after_V"])
    np.testing.assert_array_equal(
        feedback["values_after"]["junction_voltage_V"], target["junction_voltage_after_V"]
    )
    return rows


def compare_local(step, lower, target):
    before, after = step["before"], step["after"]
    sim = after["simulator"]
    feedback = dict(
        before=before,
        cache_after=dict(wire=after["wire"]),
        rhs=step["rhs"],
        controls_after={key: sim[key] for key in ("gj_block", "NaKATP_block")},
        values_after=dict(voltage_V=sim["vm"], junction_voltage_V=sim["vgj"]),
    )
    rows = compare_ecm_local(feedback, lower, target)
    for key, input_key in (
        ("cc_cells", "cell_mol_m3"),
        ("cc_at_mem", "membrane_mol_m3"),
        ("cc_env", "environment_mol_m3"),
    ):
        np.testing.assert_array_equal(sim[key], before["values_before"][input_key])
    for key in ("gj_block", "NaKATP_block"):
        np.testing.assert_array_equal(sim[key], before["controls_before"][key])
    assert (
        after["parameters"]["substances_affect_charge"]
        is before["substances_affect_charge"]
        is False
    )
    for key, value in before["simulator_fields_before"].items():
        np.testing.assert_array_equal(after["wire"]["simulator_fields"][key], value)
    present = {
        key: after["wire"]["core_fields"][key] for key in before["core_publication_fields_before"]
    }
    old.exact_nested(present, before["core_publication_fields_before"])
    assert not {"extra_rho_cells", "extra_rho_env"} & after["wire"]["core_fields"].keys()
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_ecm_standalone_grn_advancing_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cold_folder = preparation / "cold"
    cold = references(cold_folder, cold_inputs(inputs))
    try:
        binding = model.bind(inputs)
        parent = model.initialize(binding)
        archive(
            tmp_path,
            case + "-cold-parent-before-later-calls",
            dict(inputs=inputs, binding=binding, parent=parent),
        )
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
        for key in (
            "extra_rho_cells",
            "extra_rho_env",
            "extra_J_mem",
            "extra_Jenv_x",
            "extra_Jenv_y",
            "c_env_bound",
            "D_env_weight",
            "D_env_weight_base",
            "TJ_targets",
        ):
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
                standalone_ECM=True,
                inherited_scalar_control=inputs["inherited_scalar_control"],
                full_grid_E_buffers_and_publication_carry=True,
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
def test_ecm_standalone_grn_partial_failure(tmp_path, case):
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
        archive(
            tmp_path,
            case + "-cold-parent-before-later-calls",
            dict(inputs=inputs, binding=binding, parent=parent),
        )
        for invocation in range(len(inputs["calls"])):
            digest = ions.digest(parent)
            candidate, trace = model.advance(binding, parent)
            archive(
                tmp_path,
                case + "-raw-returned-call-" + str(invocation),
                dict(parent=parent, candidate=candidate, trace=trace),
            )
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
        if case in (
            "first_negative",
            "second_negative",
            "first_environment_negative",
            "second_environment_negative",
        ):
            completed = sum(
                frame["stage"] == "transport_after" for frame in partial["trace"]["molecule_frames"]
            )
            assert completed == (0 if case.startswith("first_") else 1)
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
def test_ecm_standalone_grn_dependencies(tmp_path, dependency):
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
        ECM_disabled="Require explicit ECM-enabled standalone phase",
        mitochondria="Standalone mitochondria require separate organelle state",
        fluid="Standalone fluid and cuts require separate phase dynamics",
        unsafe_sampling="Sampling below dt stalls the source sampling-index loop",
        missing_owner_state="Require complete standalone owner state",
        missing_boundary_state="Require standalone boundary state",
        missing_grid_state="Require complete generated standalone ECM grid state",
        missing_coefficient_state="Require standalone ECM coefficient state",
        file_restart="File restart requires a separate persistence boundary",
        prepared_mapping="Require owned in-grid TJ indices",
    )
    if dependency in (
        "missing_owner_state",
        "missing_boundary_state",
        "missing_grid_state",
        "missing_coefficient_state",
    ):
        raw = ions.data(parent.snapshot)
        if dependency == "missing_owner_state":
            del raw["wire"]["owner_fields"]
        elif dependency == "missing_boundary_state":
            del raw["wire"]["ion_boundary_state"]
        elif dependency == "missing_grid_state":
            del raw["grid_fields"]
        else:
            del raw["simulator"]["D_env_weight"]
        changed = model.state(binding, raw, 0)
        archive(
            tmp_path,
            dependency + "-malformed-parent-before-call",
            dict(parent=changed, inputs=inputs),
        )
        with pytest.raises(ValueError) as caught:
            model.advance(binding, changed)
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "ECM_disabled":
            changed["is_ecm"] = False
        elif dependency in ("mitochondria", "fluid"):
            changed["scope"][dependency] = True
        elif dependency == "unsafe_sampling":
            changed["calls"][0]["sample_s"] = 0.001
        elif dependency == "file_restart":
            changed["scope"]["grn_unpickle_filename"] = "/uncaptured/restart.pickle"
        else:
            changed["network"]["grid_index_groups"]["all_bound_mem_inds"] = [999]
        archive(tmp_path, dependency + "-inputs", changed)
        with pytest.raises(ValueError) as caught:
            model.bind(changed)
    archive(
        tmp_path,
        dependency + "-refusal",
        dict(message=str(caught.value), type=type(caught.value).__name__),
    )
    assert type(caught.value) is ValueError and str(caught.value) == messages[dependency]
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
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
    if cpu := os.environ.get("CELLS_ECM_SIM_GRN_CPU"):
        assert receipt["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")

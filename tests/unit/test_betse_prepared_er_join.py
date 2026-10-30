"""Unrun checks for a distinct supplied-state seam; old ER failures stay failed."""

import copy
import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_endoretic_source as kernel
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_prepared_er_join as prepared
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit import test_betse_normal_er_join as base_checks
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_prepared_er_join_fixtures as fixtures
from validation.betse import betse_prepared_er_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "prepared-er-join"


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, ions.data(payload))


def refusal(tmp_path, name, inputs, error):
    return archive(
        tmp_path,
        "unexpected-refusal-" + name,
        dict(
            inputs=inputs,
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            partial={
                key: getattr(error, key, None)
                for key in (
                    "stage",
                    "parent",
                    "initialization",
                    "material",
                    "channel_phases",
                    "network",
                    "readout",
                    "voltage_trial",
                )
            },
        ),
    )


def preparation_references(folder, before):
    path = folder / "reference-inputs.json"
    path.write_text(json.dumps(old.plain(ions.data(before)), indent=2, allow_nan=False) + "\n")
    answers = []
    for level in (1, 2):
        output = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_prepared_er_join_reference",
            "--inputs",
            str(path),
            "--output",
            str(output),
            "--refinement",
            str(level),
        ]
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        answer = json.loads(output.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        answers.append(answer)
    return answers


def compare_preparation(tmp_path, name, packet, lower, target):
    fields = packet.endoretic_state.fields
    for key in ("cc_er", "er_vol", "er_sa", "cm_er", "zer", "Dm_er_base"):
        np.testing.assert_array_equal(fields[key], target["fields"][key], err_msg=key)
    np.testing.assert_array_equal(packet.cytosol_mM, target["cytosol_mM"])
    np.testing.assert_array_equal(packet.requested_voltage_V, target["requested_voltage_V"])
    np.testing.assert_array_equal(
        packet.target_charge_density_C_m3, target["target_charge_density_C_m3"]
    )
    assert packet.ideal_target_voltage_decimal == tuple(lower["ideal_target_voltage_decimal"])
    rows, errors, budgets = {}, {}, {}
    quantities = [
        (
            "Q",
            fields["Q"],
            target["fields"]["Q"],
            lower["fields"]["Q"],
            target["budgets"]["Q"],
            "C/m3",
        ),
        (
            "Ver",
            fields["Ver"],
            target["fields"]["Ver"],
            lower["fields"]["Ver"],
            target["budgets"]["Ver"],
            "V",
        ),
        (
            "Dm_channels",
            fields["Dm_channels"],
            target["fields"]["Dm_channels"],
            lower["fields"]["Dm_channels"],
            target["budgets"]["caches"],
            "m2/s",
        ),
        (
            "Dm_er",
            fields["Dm_er"],
            target["fields"]["Dm_er"],
            lower["fields"]["Dm_er"],
            target["budgets"]["caches"],
            "m2/s",
        ),
        (
            "initial_amount",
            packet.initial_amount_mol,
            target["initial_amount_mol"],
            lower["initial_amount_mol"],
            target["budgets"]["amounts"],
            "mol",
        ),
        (
            "source_initial_amount",
            packet.source_initial_amount_mol,
            target["source_initial_amount_mol"],
            lower["source_initial_amount_mol"],
            target["budgets"]["amounts"],
            "mol",
        ),
        (
            "target_Q",
            fields["Q"],
            target["target_charge_density_C_m3"],
            lower["target_charge_density_C_m3"],
            target["budgets"]["target_Q"],
            "C/m3",
        ),
        (
            "target_Ver",
            fields["Ver"],
            target["requested_voltage_V"],
            lower["requested_voltage_V"],
            target["budgets"]["target_Ver"],
            "V",
        ),
    ]
    for label, actual, expected, less, budget, unit in quantities:
        rows[label] = old.metric(actual, expected, budget) | dict(unit=unit)
        rows["reference/" + label] = old.metric(less, expected, budget) | dict(unit=unit)
        errors[label] = abs(np.asarray(actual) - np.asarray(expected))
        budgets[label] = np.asarray(budget)
    if packet.recipe["target"] != "neutral":
        value, budget = (
            np.asarray(target["redistribution_residual_mol"]),
            np.asarray(target["budgets"]["redistribution"]),
        )
        rows["paired_Cl_inventory"] = old.metric(value, np.zeros(value.shape), budget) | dict(
            unit="mol",
            boundary=(
                "Compared with the separately declared neutral baseline; "
                "the failed literal inventory remains a different declaration"
            ),
        )
        errors["paired_Cl_inventory"], budgets["paired_Cl_inventory"] = abs(value), budget
    archive(
        tmp_path,
        "preparation-errors-" + name,
        dict(
            fields=rows,
            errors=errors,
            budgets=budgets,
            initial_inventory_change_mol=packet.initial_amount_mol
            - packet.source_initial_amount_mol,
        ),
    )
    return rows


def seed(tmp_path, inputs, name):
    folder = root(tmp_path) / ("preparation-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    parent = before = packet = None
    try:
        binding, parent = base_checks.seed(inputs)
        archive(
            tmp_path, name + "-literal-constructor-return", dict(binding=binding, parent=parent)
        )
        kwargs = dict(
            recipe=inputs["prepared_er_recipe"],
            owner_context=inputs["drives"][0]["er_context"],
            initial_temperature_K=inputs["drives"][0]["material"]["runtime_temperature_K"],
        )
        before = prepared.preparation_inputs(binding, parent, **kwargs)
        archive(tmp_path, name + "-before-preparation", before)
        answers = preparation_references(folder, before)
        prior_digest = ions.digest(parent)
        packet = prepared.prepare(binding, parent, **kwargs)
        archive(tmp_path, name + "-prepared-return", dict(source_parent=parent, packet=packet))
        rows = compare_preparation(tmp_path, name, packet, *answers)
        (folder / "comparison.json").write_text(
            json.dumps(
                dict(
                    fields=rows,
                    completed=True,
                    preparation_only=True,
                    reference_forms=2,
                    exact_binary_input=True,
                    source_parent_association_preserved=True,
                ),
                indent=2,
            )
            + "\n"
        )
        assert max(row["normalized_max_error"] for row in rows.values()) <= 1
        assert (
            max(
                row["normalized_max_error"]
                for key, row in rows.items()
                if key.startswith("reference/")
            )
            <= 0.1
        )
        prepared.validate(binding, parent, packet)
        state = (
            prepared.attach(binding, parent, packet)
            if packet.recipe["scope"] == "whole_join"
            else None
        )
        assert ions.digest(parent) == prior_digest
        archive(tmp_path, name + "-attachment-return", dict(packet=packet, state=state))
    except Exception as error:
        refusal(
            tmp_path,
            name + "-preparation",
            dict(inputs=inputs, source_parent=parent, before=before, packet=packet),
            error,
        )
        raise
    return binding, parent, packet, state


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "inputs.json"
    path.write_text(json.dumps(old.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_prepared_er_join_native",
        "--inputs",
        str(path),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    captured = archive_read(folder / "native")
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"] and captured["supplied_prepared_state"]
    assert not captured["native_initialization_executed"] and not captured["native_restart_parity"]
    return folder, captured


def run_history(tmp_path, case, *, subdivision=1, diagnostic=False):
    inputs = fixtures.fixture(case, subdivision=subdivision)
    tag = (
        ("refinement-" if diagnostic else "")
        + case
        + ("-n" + str(subdivision) if diagnostic else "")
    )
    binding, source_parent, packet, parent = seed(tmp_path, inputs, tag)
    assert parent.pump.identity == source_parent.pump.identity
    assert parent.identity != source_parent.identity
    inputs["prepared_er_input"] = dict(
        mode=packet.mode,
        packet_identity=packet.identity,
        source_parent_identity=packet.source_parent_identity,
        fields=packet.endoretic_state.fields,
    )
    folder, captured = isolated(tmp_path, tag, inputs)
    calls = 3 * subdivision
    assert captured["status"] == "source_completed" and len(captured["history"]) == calls
    elapsed, reports, endpoints = inputs["elapsed_start_s"], [], []
    for index, source in enumerate(captured["history"]):
        local = folder / ("pre-er-" + str(index))
        local.mkdir()
        answers, observed = [], []

        def observer(before, answers=answers, observed=observed, local=local, index=index):
            archive(tmp_path, tag + "-pre-er-" + str(index), before)
            observed.append(before)
            answers.extend(base_checks.references(local, before))

        digest = ions.digest(parent)
        try:
            trial = base_checks.advance(inputs, binding, parent, index, elapsed, observer)
        except Exception as error:
            refusal(
                tmp_path, tag + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, tag + "-actual-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == digest and len(answers) == 2
        material = source["material"]
        old.exact_phase(trial.material.pump.pump, material)
        for actual, expected in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (actual.stage, actual.ion_id) == (expected["stage"], expected["ion_id"])
            exact(actual.values, expected["values"])
        calcium_checks.compare_calcium(trial.material.calcium_handler, material)
        base_checks.compare_channel_routes(trial, material)
        er = trial.material.calcium_handler["endoretic"]
        assert (
            er.source_completed
            and er.finite
            and er.parent.identity == parent.endoretic_state.identity
        )
        base_checks.compare_er(er, material["channel_capture"]["endoretic"])
        old.exact_cache(
            trial.candidate.endoretic_state.fields,
            material["channel_capture"]["endoretic"]["after"],
        )
        np.testing.assert_array_equal(
            observed[0]["membrane_mM"],
            trial.material.calcium_handler["values_after"]["membrane_mol_m3"],
        )
        for a, b in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            old.exact_gate(a, b)
        for a, b in zip(trial.candidate.channel_caches, material["channel_caches"], strict=True):
            old.exact_cache(a, b)
        assert list(trial.candidate.channel_calls) == material["channel_capture"]["calls"]
        assert trial.candidate.pump.gated.material.step_index == index + 1
        assert trial.clock["elapsed_start_s"] == elapsed
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        rows, errors, budgets = base_checks.local_comparisons(binding, trial, *answers)
        archive(
            tmp_path,
            tag + "-conditional-errors-" + str(index),
            dict(fields=rows, errors=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(dict(fields=rows, conditional_pre_endoretic_only=True), indent=2) + "\n"
        )
        assert max(row["normalized_max_error"] for row in rows.values()) <= 1
        assert (
            max(
                row["normalized_max_error"]
                for key, row in rows.items()
                if key.startswith("reference/")
            )
            <= 0.1
        )
        reports.append(rows)
        parent, elapsed = trial.candidate, trial.clock["elapsed_end_s"]
        if (index + 1) % subdivision == 0:
            endpoints.append(
                dict(
                    relative_time_s=0.002 * ((index + 1) // subdivision),
                    values=ions.data(parent.pump.gated.material.values),
                    er_fields=parent.endoretic_state.fields,
                    current=ions.data(trial.current.values),
                    voltage=ions.data(trial.voltage.values),
                    channel_caches=parent.channel_caches,
                )
            )
    assert abs(elapsed - (inputs["elapsed_start_s"] + 0.006)) <= 32 * np.finfo(float).eps * (
        abs(elapsed) + 0.006
    )
    assert [point["relative_time_s"] for point in endpoints] == [0.002, 0.004, 0.006]
    report = dict(
        completed=True,
        exact_native=True,
        complete_calls=calls,
        conditional_pre_endoretic_checks=calls,
        preparation_reference_forms=2,
        carried_reference_forms=0,
        diagnostic=diagnostic,
        subdivision=subdivision,
        matched_horizon_s=0.006,
        supplied_prepared_state=True,
        native_constructor_parity=False,
        no_upstream_or_trajectory_accuracy_claim=True,
        maximum_error_fraction=max(
            row["normalized_max_error"] for rows in reports for row in rows.values()
        ),
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    archive(tmp_path, tag + "-matched-endpoints", endpoints)
    return endpoints


@pytest.mark.parametrize("case", fixtures.CASES)
def test_supplied_neutral_er_outer_history(tmp_path, case):
    run_history(tmp_path, case)


@pytest.mark.parametrize("case", fixtures.SIGN_CASES)
def test_supplied_thermal_sign_er_only(tmp_path, case):
    inputs = fixtures.fixture(case)
    binding, source_parent, packet, state = seed(tmp_path, inputs, case)
    assert state is None
    with pytest.raises(ValueError):
        prepared.attach(binding, source_parent, packet)
    before = prepared.conditional_inputs(binding, source_parent, packet, dt_s=0.002)
    archive(tmp_path, case + "-pre-er", before)
    folder, captured = isolated(
        tmp_path, case, dict(kind="cells.prepared_owned_ER_only_probe@1", pre_er=before)
    )
    local = folder / "pre-er-0"
    local.mkdir()
    answers = base_checks.references(local, before)
    er = kernel.step(
        packet.endoretic_state,
        binding_identity=binding.identity,
        cytosol_mM=packet.cytosol_mM,
        cell_volume_m3=before["cell_volume_m3"],
        moving_indices=before["moving_indices"],
        valence=before["valence"],
        runtime_temperature_K=before["runtime_temperature_K"],
        parameters=ions.data(before["parameters"]),
        owner_context=packet.owner_context,
    )
    archive(tmp_path, case + "-ER-only-return", er)
    assert captured["status"] == "source_completed" and er.source_completed and er.finite
    base_checks.compare_er(er, captured["endoretic"])
    np.testing.assert_array_equal(er.cytosol_after_mM, captured["cytosol_after_mM"])
    rows, errors, budgets = base_checks.local_comparisons(
        binding,
        SimpleNamespace(material=SimpleNamespace(calcium_handler={"endoretic": er})),
        *answers,
    )
    archive(
        tmp_path, case + "-conditional-errors", dict(fields=rows, errors=errors, budgets=budgets)
    )
    (local / "comparison.json").write_text(
        json.dumps(dict(fields=rows, conditional_pre_endoretic_only=True), indent=2) + "\n"
    )
    assert max(row["normalized_max_error"] for row in rows.values()) <= 1
    assert (
        max(
            row["normalized_max_error"] for key, row in rows.items() if key.startswith("reference/")
        )
        <= 0.1
    )
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=1,
                conditional_pre_endoretic_checks=1,
                preparation_reference_forms=2,
                carried_reference_forms=0,
                supplied_prepared_state=True,
                ER_only=True,
                native_constructor_parity=False,
                maximum_error_fraction=max(row["normalized_max_error"] for row in rows.values()),
            ),
            indent=2,
        )
        + "\n"
    )


def units(path):
    key = path.rsplit("/", 1)[-1]
    er = {
        "cc_er": "mol/m3",
        "er_vol": "m3",
        "er_sa": "m2",
        "cm_er": "F/m2",
        "Q": "C/m3",
        "Ver": "V",
        "zer": "1",
        "Dm_er": "m2/s",
        "Dm_er_base": "m2/s",
        "Dm_channels": "m2/s",
    }
    if key in er:
        return er[key]
    suffixes = (
        ("_mol_m2_s", "mol/(m2*s)"),
        ("_mol_m3", "mol/m3"),
        ("_C_m3", "C/m3"),
        ("_C_m2", "C/m2"),
        ("_A_m2", "A/m2"),
        ("_A", "A"),
        ("_S_m", "S/m"),
        ("_V_m2", "V/m2"),
        ("_V_m", "V/m"),
        ("_V_s", "V/s"),
        ("_V", "V"),
        ("_s", "s"),
    )
    return next((unit for suffix, unit in suffixes if key.endswith(suffix)), "1")


def differences(a, b, prefix=""):
    arrays, summary = {}, {}
    if isinstance(a, dict):
        assert set(a) == set(b)
        for key in a:
            child, rows = differences(a[key], b[key], prefix + "/" + key)
            arrays.update(child)
            summary.update(rows)
    elif isinstance(a, (tuple, list)) and a and isinstance(a[0], dict):
        for i, (left, right) in enumerate(zip(a, b, strict=True)):
            child, rows = differences(left, right, prefix + "/" + str(i))
            arrays.update(child)
            summary.update(rows)
    elif a is not None and np.asarray(a).dtype.kind in "iufb":
        delta = abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))
        arrays[prefix] = delta
        summary[prefix] = dict(
            absolute_max=float(np.max(delta)) if delta.size else 0.0,
            shape=list(delta.shape),
            units=units(prefix),
        )
    return arrays, summary


@pytest.mark.parametrize("case", fixtures.REFINEMENT_CASES)
def test_matched_horizon_refinement_diagnostic(tmp_path, case):
    histories = [
        run_history(tmp_path, case, subdivision=n, diagnostic=True) for n in fixtures.SUBDIVISIONS
    ]
    arrays, summary = {}, {}
    for left, right, label in ((0, 1, "dt002_vs001"), (1, 2, "dt001_vs0005")):
        for index in range(3):
            assert (
                histories[left][index]["relative_time_s"]
                == histories[right][index]["relative_time_s"]
            )
            values, rows = differences(
                ions.data(histories[left][index]),
                ions.data(histories[right][index]),
                label + "/boundary" + str(index),
            )
            arrays.update(values)
            summary.update(rows)
    archive(
        tmp_path,
        "refinement-differences-" + case,
        dict(absolute_differences=arrays, summary=summary, histories=histories),
    )
    diagnostics = root(tmp_path) / "diagnostics"
    diagnostics.mkdir(exist_ok=True)
    (diagnostics / ("refinement-" + case + ".json")).write_text(
        json.dumps(
            dict(
                complete=True,
                subdivisions=list(fixtures.SUBDIVISIONS),
                dt_s=[0.002, 0.001, 0.0005],
                matched_horizon_s=0.006,
                forcing_changes_at_relative_s=[0.002, 0.004],
                diagnostic_only=True,
                physical_accuracy_pass_threshold=None,
                independent_carried_forms=0,
                summary=summary,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.REFUSALS)
def test_prepared_packet_refusals(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    if dependency == "nonpositive_counterion":
        index = inputs["ion_definition"]["ions"]["ids"].index("P")
        inputs["initial"]["cell_mol_m3"][index] = [100.0] * 3
        inputs["initial"]["membrane_mol_m3"][index] = [100.0] * 9
    archive(tmp_path, dependency + "-raw-inputs", inputs)
    binding, parent = base_checks.seed(inputs)
    kwargs = dict(
        recipe=inputs["prepared_er_recipe"],
        owner_context=inputs["drives"][0]["er_context"],
        initial_temperature_K=inputs["drives"][0]["material"]["runtime_temperature_K"],
    )
    if dependency == "nonpositive_counterion":
        with pytest.raises(ValueError) as caught:
            prepared.prepare(binding, parent, **kwargs)
    else:
        packet = prepared.prepare(binding, parent, **kwargs)
        fields = {
            key: np.array(value, copy=True) if isinstance(value, np.ndarray) else value
            for key, value in packet.endoretic_state.fields.items()
        }
        if dependency in ("charge", "voltage", "axes_or_geometry"):
            key = {"charge": "Q", "voltage": "Ver", "axes_or_geometry": "er_vol"}[dependency]
            fields[key][0] = fields[key][0] * 2 if key == "er_vol" else fields[key][0] + 1.0
            packet = replace(
                packet,
                endoretic_state=kernel.state(
                    binding.identity,
                    packet.endoretic_state.ion_ids,
                    packet.endoretic_state.cell_ids,
                    fields,
                ),
            )
        if dependency == "cache_context":
            context = ions.data(packet.owner_context)
            context["molecules"]["IP3_mM"] = np.array(context["molecules"]["IP3_mM"], copy=True)
            context["molecules"]["IP3_mM"][0] *= 2
            packet = replace(packet, owner_context=ions.freeze(context))
        if dependency == "parent_association":
            packet = replace(packet, source_parent_identity="different-complete-parent")
        packet = replace(packet, identity="")
        packet = replace(packet, identity=ions.digest(packet))
        archive(tmp_path, dependency + "-resealed-input", dict(parent=parent, packet=packet))
        with pytest.raises(ValueError) as caught:
            prepared.attach(binding, parent, packet)
    archive(
        tmp_path,
        dependency + "-expected-preparation-refusal",
        dict(
            type=type(caught.value).__name__,
            message=str(caught.value),
            native_refusal_claim=False,
            executed_native_or_update=False,
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
    runtime = inventory()
    if cpu := os.environ.get("CELLS_PREPARED_ER_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

"""Prepared source-exact ER join and conditional pre-ER checks; unrun."""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_endoretic_source as kernel
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_er_join as joined
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_er_join_fixtures as fixtures
from validation.betse import betse_normal_er_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-er-join"


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
    return joined.advance(
        binding,
        parent,
        ions.drive(binding.pump_binding.gated_binding.material_binding, **drive["material"]),
        pump.packet(binding.pump_binding, **drive["pump"]),
        joined.packet(binding, **drive["channels"]),
        joined.calcium_packet(binding, **drive["calcium"]),
        live_er_context=drive["er_context"],
        before_endoretic=observer,
        boundary_V=drive["boundary_V"],
        extra_charge_C_m3=drive["extra_charge_C_m3"],
        extra_current_A_m2=drive["extra_current_A_m2"],
        elapsed_s=elapsed,
    )


def isolated(tmp_path, name, inputs, *, raw=False):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    module = "validation.betse.betse_normal_er_join_native" + ("_er" if raw else "")
    command = [
        sys.executable,
        "-B",
        "-m",
        module,
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
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_er_join_reference",
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
        answers.append(answer)
    return answers


def compare_er(actual, source):
    old.exact_cache(actual.parent.fields, source["initial_state"])
    old.exact_cache(actual.raw_candidate, source["after"])
    for phase, expected in zip(actual.frames, source["frames"], strict=True):
        assert phase["stage"] == expected["stage"] and phase["ion_id"] == expected["ion_id"]
        old.exact_cache(phase["fields"], expected["fields"])
        for name in ("cytosol_mM", "flux_mol_m2_s"):
            if expected[name] is None:
                assert phase[name] is None
            else:
                assert phase[name].dtype == expected[name].dtype
                np.testing.assert_array_equal(phase[name], expected[name])
    old.exact_cache(actual.arithmetic, source["arithmetic"])


def compare_channel_routes(trial, captured):
    phases = captured["channel_capture"]["events"]
    for actual, expected in zip(trial.material.channel_phases, phases, strict=True):
        for key in ("channel_id", "class_name", "skipped", "call_index", "dt_s", "native_dt"):
            assert getattr(actual, key) == expected[key], key
        for key in ("cache_before", "cache_after"):
            old.exact_cache(getattr(actual, key), expected[key])
        for key in ("values_before", "values_after"):
            exact(getattr(actual, key), expected[key])
        for route, wanted in zip(actual.routes, expected["routes"], strict=True):
            assert (
                route.ion_id == wanted["ion_id"]
                and route.relative_permeability == wanted["relative_permeability"]
            )
            for key in ("values_before", "values_after"):
                exact(getattr(route, key), wanted[key])
            old.exact_cache(route.cache_after, wanted["cache_after"])
            for key in (
                "sampled_bulk_mM",
                "sampled_membrane_mM",
                "sampled_bath_mM",
                "diffusion_m2_s",
                "flux_mol_m2_s",
                "network_current_before_A_m2",
                "network_current_after_A_m2",
            ):
                assert getattr(route, key).dtype == wanted[key].dtype, key
                np.testing.assert_array_equal(getattr(route, key), wanted[key], err_msg=key)


def local_comparisons(binding, trial, lower, target):
    ib = binding.pump_binding.gated_binding.material_binding
    vb = binding.pump_binding.gated_binding.voltage_binding
    er = trial.material.calcium_handler["endoretic"]
    material_factor = 128 * np.finfo(float).eps * (len(ib.ion_ids) + len(ib.cell_ids) + 4 + 32)
    charge_factor = 32 * np.finfo(float).eps * (len(ib.ion_ids) + len(ib.cell_ids) + 16)
    voltage_factor = (
        1024
        * np.finfo(float).eps
        * (len(ib.ion_ids) + len(ib.cell_ids) + np.prod(vb.kernel.shape) + 16 + 64)
    )
    rows, errors, budgets = {}, {}, {}
    values = (
        (
            "cytosol",
            er.cytosol_after_mM,
            target["cytosol_mM"],
            lower["cytosol_mM"],
            material_factor * np.asarray(target["cytosol_gross"]) + FLOORS["cell_mol_m3"],
            "mM",
        ),
        (
            "cc_er",
            er.raw_candidate["cc_er"],
            target["fields"]["cc_er"],
            lower["fields"]["cc_er"],
            material_factor * np.asarray(target["er_gross"]) + FLOORS["cell_mol_m3"],
            "mM",
        ),
        (
            "Q",
            er.raw_candidate["Q"],
            target["fields"]["Q"],
            lower["fields"]["Q"],
            charge_factor * np.asarray(target["charge_gross"]) + 1e-30,
            "C/m3",
        ),
        (
            "Ver",
            er.raw_candidate["Ver"],
            target["fields"]["Ver"],
            lower["fields"]["Ver"],
            voltage_factor * np.asarray(target["voltage_gross"]) + 1e-30,
            "V",
        ),
        (
            "SERCA",
            er.arithmetic["serca_flux_mol_m2_s"],
            target["serca_flux_mol_m2_s"],
            lower["serca_flux_mol_m2_s"],
            old.PUMP_TOLERANCES["density_mol_per_m2_s"]
            + old.PUMP_TOLERANCES["relative"] * abs(np.asarray(target["serca_flux_mol_m2_s"])),
            "mol/(m2*s)",
        ),
    )
    for name, actual, expected, less, budget, unit in values:
        rows[name] = old.metric(actual, expected, budget) | dict(unit=unit)
        rows["reference/" + name] = old.metric(less, expected, budget)
        errors[name], budgets[name] = abs(actual - np.asarray(expected)), budget
    amount_budget = material_factor * er.amount_gross_mol + FLOORS["cell_mol_m3"] * (
        ib.kernel.cell_volume_m3 + er.parent.fields["er_vol"]
    )
    rows["ER_transfer_conservation"] = old.metric(
        er.amount_change_mol, np.zeros(er.amount_change_mol.shape), amount_budget
    ) | dict(unit="mol", scope="ER transfer only; ordinary clipping is separate")
    errors["ER_transfer_conservation"] = abs(er.amount_change_mol)
    budgets["ER_transfer_conservation"] = amount_budget
    return rows, errors, budgets


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_er_and_actual_pre_er_reference(tmp_path, case):
    inputs = fixtures.fixture(case)
    initial = root(tmp_path) / ("preparation-" + case)
    initial.mkdir(parents=True, exist_ok=False)
    (initial / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, case + "-constructor", inputs, error)
        raise
    archive(
        tmp_path, case + "-constructor-return", dict(inputs=inputs, binding=binding, parent=parent)
    )
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    elapsed = inputs["elapsed_start_s"]
    reports = []
    for index, source in enumerate(captured["history"]):
        local = folder / ("pre-er-" + str(index))
        local.mkdir()
        answers, actual_before = [], []

        def observer(
            before, answers=answers, actual_before=actual_before, local=local, index=index
        ):
            archive(tmp_path, case + "-pre-er-" + str(index), before)
            actual_before.append(before)
            answers.extend(references(local, before))

        digest_before = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed, observer)
        except Exception as error:
            archive_refusal(
                tmp_path, case + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == digest_before and len(answers) == 2
        material = source["material"]
        old.exact_phase(trial.material.pump.pump, material)
        for a, b in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (a.stage, a.ion_id) == (b["stage"], b["ion_id"])
            exact(a.values, b["values"])
        calcium_checks.compare_calcium(trial.material.calcium_handler, material)
        compare_channel_routes(trial, material)
        er = trial.material.calcium_handler["endoretic"]
        assert er.source_completed and er.finite
        compare_er(er, material["channel_capture"]["endoretic"])
        old.exact_cache(
            trial.candidate.endoretic_state.fields,
            material["channel_capture"]["endoretic"]["after"],
        )
        # Native ER transfer never refreshes the plasma membrane buffer.
        np.testing.assert_array_equal(
            actual_before[0]["membrane_mM"],
            trial.material.calcium_handler["values_after"]["membrane_mol_m3"],
        )
        for a, b in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            old.exact_gate(a, b)
        for a, b in zip(trial.candidate.channel_caches, material["channel_caches"], strict=True):
            old.exact_cache(a, b)
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        rows, errors, budgets = local_comparisons(binding, trial, answers[0], answers[1])
        archive(
            tmp_path,
            "conditional-errors-" + case + "-" + str(index),
            dict(errors=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(dict(fields=rows, conditional_pre_endoretic_only=True), indent=2) + "\n"
        )
        assert max(r["normalized_max_error"] for r in rows.values()) <= 1
        assert (
            max(
                r["normalized_max_error"]
                for name, r in rows.items()
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
                conditional_pre_endoretic_checks=3,
                carried_reference_forms=0,
                no_upstream_or_trajectory_accuracy_claim=True,
                maximum_error_fraction=max(
                    r["normalized_max_error"] for rows in reports for r in rows.values()
                ),
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_raw_native_serca_returns(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    folder, captured = isolated(tmp_path, "raw-" + case, inputs, raw=True)
    model = kernel.probe_pump(inputs)
    path = archive(tmp_path, "raw-model-" + case, model)
    assert model["source_completed"] == captured["source_completed"]
    assert model["finite"] == captured["finite"]
    old.exact_cache(model["arithmetic"], captured["arithmetic"])
    for key in ("flux_mol_m2_s", "cER_after_mM", "cytosol_after_mM", "voltage_after_V"):
        assert model[key].dtype == captured[key].dtype
        np.testing.assert_array_equal(model[key], captured[key])
    assert model["source_completed"]
    if case != "zero_denominator":
        assert not model["finite"]
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                raw_model=str(path),
                source_completed=bool(model["source_completed"]),
                finite=bool(model["finite"]),
                positive_domain_or_physical_acceptance=False,
                source_equation_repair=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", ("Ca_dyn0", "missing_ER_parameter", "missing_owner_context"))
def test_complete_er_state_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture()
    if dependency == "Ca_dyn0":
        inputs["channel_definition"]["calcium_handler"]["Ca_dyn"] = 0
    if dependency == "missing_ER_parameter":
        del inputs["channel_definition"]["calcium_handler"]["endoretic"]["act_Km_IP3"]
    if dependency != "missing_owner_context":
        with pytest.raises((ValueError, joined.MissingCoupledState)):
            seed(inputs)
    else:
        binding, parent = seed(inputs)
        del inputs["drives"][0]["er_context"]["metabo"]
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs, binding, parent, 0, inputs["elapsed_start_s"])
        archive_refusal(tmp_path, "dependency-" + dependency, inputs, caught.value)


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
    if cpu := os.environ.get("CELLS_ER_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

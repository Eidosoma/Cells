"""Prepared CaATP/rectangular-caller checks. No execution in static round."""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_calcium_atp_source as kernel
from cells.processes import betse_normal_calcium_join as calcium
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_channel_join as old
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_calcium_join_fixtures as fixtures
from validation.betse import betse_normal_calcium_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-calcium-join"


def archive(tmp_path, name, value):
    return native.write_archive(root(tmp_path) / name, ions.data(value))


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
    binding = calcium.bind(pb, inputs["channel_definition"])
    parent = calcium.initialize_values(
        binding,
        inputs["initial"],
        initial_gate_block=inputs["initial_gate_block"],
        initial_NaK_rate=inputs["initial_rate_proxy_mol_m2_s"],
        initial_CaATP_rate=inputs["initial_calcium_rate_proxy_mol_m2_s"],
    )
    return binding, parent


def advance(inputs, binding, parent, index, elapsed, observer=None):
    drive = inputs["drives"][index]
    return calcium.advance(
        binding,
        parent,
        ions.drive(binding.pump_binding.gated_binding.material_binding, **drive["material"]),
        pump.packet(binding.pump_binding, **drive["pump"]),
        calcium.packet(binding, **drive["channels"]),
        calcium.calcium_packet(binding, **drive["calcium"]),
        before_calcium=observer,
        boundary_V=drive["boundary_V"],
        extra_charge_C_m3=drive["extra_charge_C_m3"],
        extra_current_A_m2=drive["extra_current_A_m2"],
        elapsed_s=elapsed,
    )


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    payload = inputs
    if inputs.get("helper_probe"):
        # Existing raw archive codec transports IEEE-754 values without JSON
        # numeric NaN tokens. Keep actual nonfinite bits in typed NPZ arrays.
        typed = dict(inputs)
        for key in ("membrane_mM", "bath_mM", "voltage_V", "block"):
            typed[key] = np.asarray(inputs[key], np.float64)
        native.write_archive(folder / "raw-inputs", typed)
        payload = dict(kind="cells.typed_native_capture_inputs@1", archive="raw-inputs")
    (folder / "inputs.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_calcium_join_native",
        "--inputs",
        str(folder / "inputs.json"),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    captured = archive_read(folder / "native")
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"]
    return folder, captured


def references(folder, inputs, phase, drive, *, kernel_only):
    payload = dict(
        definition=inputs,
        phase=old.plain(ions.data(phase)),
        drive=drive,
        conditioned_before_model_calcium=True,
        conditional_context="actual pre-handler state; no outgoing CaATP answers",
    )
    (folder / "inputs.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    results = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_calcium_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--refinement",
            str(level),
        ]
        if kernel_only:
            command.append("--kernel-only")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        value = json.loads(path.read_text())
        assert value["production_imports_denied"] and not value["loaded_production_modules"]
        results.append(value)
    return results


def compare_calcium(actual, source):
    expected = source["channel_capture"]["network"]["calcium_phase"]
    np.testing.assert_array_equal(actual["rate_before"], expected["rate_before"])
    np.testing.assert_array_equal(actual["rate_after"], expected["rate_after"])
    exact(ions.Values(**actual["values_before"]), expected["values_before"])
    exact(ions.Values(**actual["values_after"]), expected["values_after"])
    assert expected["cc_env_rank"] == 2 and expected["bath_row_shape"] == [9]
    if actual["arithmetic"] is None:
        assert not expected["arithmetic"]
    else:
        assert expected["arithmetic"]["rate_aliases_helper_flux"]
        for key, value in actual["arithmetic"].arithmetic.items():
            wanted = expected["arithmetic"][key]
            assert value.dtype == wanted.dtype, key
            np.testing.assert_array_equal(value, wanted, err_msg=key)


def local_comparisons(binding, trial, lower, target):
    phase = trial.material.calcium_handler
    rows = {}
    errors = {}
    budgets = {}
    for key in ("rate_after", "applied_flux_mol_m2_s"):
        actual = phase[key] if key in phase else np.zeros(9)
        wanted = np.asarray(target[key])
        budget = old.PUMP_TOLERANCES["density_mol_per_m2_s"] + old.PUMP_TOLERANCES[
            "relative"
        ] * abs(wanted)
        rows[key] = old.metric(actual, wanted, budget) | dict(
            unit="mol/(m2*s)", conditional_pre_handler=True
        )
        rows["reference/" + key] = old.metric(lower[key], wanted, budget)
        errors[key], budgets[key] = abs(actual - wanted), budget
    if phase["arithmetic"] is not None:
        for key, wanted in target["arithmetic"].items():
            value = phase["arithmetic"].arithmetic[key]
            if key == "zero_denominator_indices":
                np.testing.assert_array_equal(value, wanted)
                continue
            if key == "raw_flux_mol_m2_s":
                budget = old.PUMP_TOLERANCES["density_mol_per_m2_s"] + old.PUMP_TOLERANCES[
                    "relative"
                ] * abs(np.asarray(wanted))
                rows["kernel/" + key] = old.metric(value, wanted, budget) | dict(unit="mol/(m2*s)")
                errors["kernel/" + key], budgets["kernel/" + key] = (
                    abs(value - np.asarray(wanted)),
                    budget,
                )
            else:
                rows["kernel/" + key] = old.metric(value, wanted) | dict(diagnostic_only=True)
    if "material_state" in target:
        ib = binding.pump_binding.gated_binding.material_binding
        vb = binding.pump_binding.gated_binding.voltage_binding
        for group, values, expected, gross, less in (
            (
                "material",
                trial.material.pump.candidate.gated.material.values,
                target["material_state"],
                target["material_gross"],
                lower["material_state"],
            ),
            (
                "current",
                trial.current.values,
                target["current"]["values"],
                target["current"]["gross"],
                lower["current"]["values"],
            ),
            (
                "voltage",
                trial.voltage.values,
                target["voltage"]["values"],
                target["voltage"]["gross"],
                lower["voltage"]["values"],
            ),
        ):
            for key, value in values._asdict().items():
                factor = (
                    (128 if group == "material" else 32 if group == "current" else 1024)
                    * np.finfo(float).eps
                    * (
                        len(ib.ion_ids)
                        + len(ib.membrane_ids)
                        + (
                            4 + 32
                            if group == "material"
                            else 16
                            if group == "current"
                            else np.prod(vb.kernel.shape) + 16 + 64
                        )
                    )
                )
                budget = factor * np.asarray(gross[key]) + (
                    FLOORS[key] if group == "material" else 1e-30
                )
                name = group + "/" + key
                rows[name] = old.metric(value, expected[key], budget) | dict(
                    unit=old.field_unit(group, key)
                )
                rows["reference/" + name] = old.metric(less[key], expected[key], budget)
                errors[name], budgets[name] = abs(value - np.asarray(expected[key])), budget
    return rows, errors, budgets


@pytest.mark.parametrize("case", fixtures.CASES)
def test_actual_rectangular_native_and_pre_handler_reference(tmp_path, case):
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
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    elapsed = inputs["elapsed_start_s"]
    reports = []
    for index, source in enumerate(captured["history"]):
        local = folder / ("handler-" + str(index))
        local.mkdir()
        answers = []

        def observer(phase, answers=answers, local=local, index=index):
            answers.extend(
                references(
                    local,
                    inputs,
                    phase,
                    inputs["drives"][index],
                    kernel_only=case == "channel_coupled",
                )
            )

        before = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed, observer)
        except Exception as error:
            archive_refusal(
                tmp_path, case + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == before and len(answers) == 2
        material = source["material"]
        old.exact_phase(trial.material.pump.pump, material)
        for a, b in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (a.stage, a.ion_id) == (b["stage"], b["ion_id"])
            exact(a.values, b["values"])
        compare_calcium(trial.material.calcium_handler, material)
        for a, b in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            old.exact_gate(a, b)
        for a, b in zip(trial.candidate.channel_caches, material["channel_caches"], strict=True):
            old.exact_cache(a, b)
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        np.testing.assert_array_equal(
            trial.candidate.calcium_rate_proxy_mol_m2_s,
            material["raw_simulator_state"]["rate_CaATP"],
        )
        rows, errors, budgets = local_comparisons(binding, trial, answers[0], answers[1])
        archive(
            tmp_path,
            "conditional-errors-" + case + "-" + str(index),
            dict(errors=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(
                dict(
                    context="actual pre-handler conditions",
                    fields=rows,
                    no_upstream_or_trajectory_error_bound=True,
                ),
                indent=2,
            )
            + "\n"
        )
        assert (
            max(r["normalized_max_error"] for r in rows.values() if "normalized_max_error" in r)
            <= 1
        )
        assert (
            max(
                r["normalized_max_error"]
                for name, r in rows.items()
                if name.startswith("reference/")
            )
            <= 0.1
        )
        reports.append(rows)
        parent = trial.candidate
        elapsed = trial.clock["elapsed_end_s"]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                complete_calls=3,
                completed=True,
                exact_native=True,
                maximum_error_fraction=max(
                    r["normalized_max_error"]
                    for rows in reports
                    for r in rows.values()
                    if "normalized_max_error" in r
                ),
                conditional_pre_handler_only=True,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.PROJECTION_CASES)
def test_uniform_rectangular_projection_to_frozen_B28(tmp_path, case):
    inputs = fixtures.projection_fixture(case)
    binding, parent = seed(inputs)
    legacy, lb, lp = old.seed(case)
    elapsed = inputs["elapsed_start_s"]
    for index in range(3):
        trial = advance(inputs, binding, parent, index, elapsed)
        expected = old.advance(legacy, lb, lp, index, elapsed)
        values = trial.candidate.pump.gated.material.values
        projected = values._replace(bath_mol_m3=values.bath_mol_m3[:, 0])
        exact(projected, ions.data(expected.candidate.pump.gated.material.values))
        np.testing.assert_array_equal(
            values.bath_mol_m3, np.repeat(values.bath_mol_m3[:, 0, None], 9, axis=1)
        )
        exact(trial.current.values, ions.data(expected.current.values))
        exact(trial.voltage.values, ions.data(expected.voltage.values))
        archive(
            tmp_path,
            "projection-" + case + "-" + str(index),
            dict(rectangular=trial, scalar=expected),
        )
        parent, lp = trial.candidate, expected.candidate
        elapsed = trial.clock["elapsed_end_s"]


@pytest.mark.parametrize(
    "kind",
    (
        "scalar_scoped_adapter",
        "nan_membrane",
        "clipped_negative_vector",
        "unused_equilibrium_overflow",
    ),
)
def test_raw_helper_container_and_domain_behaviour(tmp_path, kind):
    data = fixtures.fixture()
    policy = data["channel_definition"]["calcium_handler"]
    parameters = policy["maintained"] | policy["kinetics"] | dict(alpha_Ca=1e-7, F=96485.0, R=8.314)
    ci = np.full(9, 0.0001)
    co = np.full(9, 1.8)
    if kind == "scalar_scoped_adapter":
        co = np.asarray(1.8)
    if kind == "nan_membrane":
        ci[1] = float("nan")
        ci[0] = -1e-6
    if kind == "clipped_negative_vector":
        ci[0] = -1e-6
        co[1] = -1e-5
    if kind == "unused_equilibrium_overflow":
        parameters["deltaGATP"] = -1e9
    payload = dict(
        membrane_mM=ci,
        bath_mM=co,
        voltage_V=np.full(9, -0.02),
        runtime_temperature_K=298.15,
        parameters=parameters,
        block=np.zeros(9),
        met=None,
    )
    _, captured = isolated(
        tmp_path, "helper-" + kind, dict(helper_probe=True, **old.plain(payload))
    )
    if kind in ("clipped_negative_vector", "unused_equilibrium_overflow"):
        trial = kernel.evaluate(**payload)
        if kind == "clipped_negative_vector":
            assert trial.membrane_after_mM[0] == 0 and trial.bath_after_mM[1] == 0
        else:
            assert trial.source_completed and not trial.finite
    else:
        with pytest.raises(kernel.CalciumSourceRefused) as caught:
            kernel.evaluate(**payload)
        trial = caught.value.partial
        assert not trial.source_completed
        if kind == "scalar_scoped_adapter":
            assert trial.failure["type"] == "ValueError"
        else:
            assert trial.membrane_after_mM[0] == 0
    np.testing.assert_array_equal(trial.membrane_after_mM, captured["membrane_after"])
    np.testing.assert_array_equal(trial.bath_after_mM, captured["bath_after"])
    assert trial.source_completed == (captured["status"] == "source_completed")
    if trial.source_completed:
        np.testing.assert_array_equal(trial.flux_mol_m2_s, captured["flux"])
    archive(
        tmp_path,
        "raw-helper-" + kind,
        dict(
            input=payload,
            trial=trial,
            initialized_native_caller=False,
            scalar_refusal_is_scoped_adapter_only=kind == "scalar_scoped_adapter",
        ),
    )


@pytest.mark.parametrize("fault", ("ER", "separate_pools", "scalar_parent"))
def test_explicit_dependencies_and_new_container_contract(fault):
    inputs = fixtures.fixture()
    if fault == "ER":
        inputs["channel_definition"]["calcium_handler"]["Ca_dyn"] = 1
    elif fault == "separate_pools":
        inputs["channel_definition"]["calcium_handler"]["maintained"]["cATP"] = 1.6
    else:
        inputs["initial"]["bath_mol_m3"] = [row[0] for row in inputs["initial"]["bath_mol_m3"]]
    with pytest.raises((ValueError, calcium.MissingCoupledState)):
        seed(inputs)


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    value = runtime_inventory()
    if cpu := os.environ.get("CELLS_CALCIUM_JOIN_CPU"):
        assert value["measured_cpu_affinity"] == [int(cpu)]
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
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(value, indent=2) + "\n")

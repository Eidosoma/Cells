"""Prepared catalog-native and actual-parent comparisons; not yet executed."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_catalog_join as channels
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_channel_join import exact_cache, exact_phase, metric, plain
from tests.unit.test_betse_normal_channel_join import (
    pump_local_comparisons as inherited_comparisons,
)
from tests.unit.test_betse_normal_gated_join import exact_gate
from tests.unit.test_betse_normal_ion_join import FLOORS, exact
from validation.betse import betse_normal_catalog_join_fixtures as fixtures
from validation.betse import betse_normal_catalog_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

PROTOCOL = (
    Path(__file__).resolve().parents[2] / "validation/betse/betse_normal_catalog_join_protocol.json"
)


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-catalog-join"


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


def nonfinite_paths(value, path="$"):
    """Locate nonfinite returns without converting their raw arrays to JSON."""
    value = ions.data(value)
    if isinstance(value, (np.ndarray, np.generic)):
        array = np.asarray(value)
        if array.dtype.kind == "f" and not np.isfinite(array).all():
            return [dict(path=path, flat_indices=np.flatnonzero(~np.isfinite(array)).tolist())]
        return []
    if type(value) is float and not np.isfinite(value):
        return [dict(path=path, flat_indices=[0])]
    if isinstance(value, dict):
        return [
            row for key, item in value.items() for row in nonfinite_paths(item, path + "/" + key)
        ]
    if isinstance(value, (tuple, list)):
        return [
            row
            for index, item in enumerate(value)
            for row in nonfinite_paths(item, path + "/" + str(index))
        ]
    return []


def archive_return(tmp_path, name, inputs, returned):
    paths = nonfinite_paths(returned)
    payload = dict(inputs=inputs, nonfinite_paths=paths)
    payload.update(returned if isinstance(returned, dict) else dict(returned=returned))
    path = archive(
        tmp_path,
        name if name.startswith("actual-") else "raw-return-" + name,
        payload,
    )
    return path, paths


def seed(inputs):
    ib = ions.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    gb = gated.bind(ib, vb, inputs["gate_definition"])
    pb = pump.bind(gb, inputs["pump_definition"])
    ps = pump.initialize(
        pb,
        ions.state(ib, inputs["initial"]),
        initial_gate_block=inputs["initial_gate_block"],
        initial_rate_proxy_mol_m2_s=inputs["initial_rate_proxy_mol_m2_s"],
    )
    binding = channels.bind(pb, inputs["channel_definition"])
    parent = channels.initialize(
        binding,
        ps,
        initial_calcium_rate_proxy_mol_m2_s=inputs["initial_calcium_rate_proxy_mol_m2_s"],
    )
    return binding, parent


def advance(inputs, binding, parent, index, elapsed):
    drive = inputs["drives"][index]
    return channels.advance(
        binding,
        parent,
        ions.drive(binding.pump_binding.gated_binding.material_binding, **drive["material"]),
        pump.packet(binding.pump_binding, **drive["pump"]),
        channels.packet(binding, **drive["channels"]),
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
        "validation.betse.betse_normal_catalog_join_native",
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


def independent(folder, mode):
    results = []
    for precision in (1, 2):
        path = folder / ("reference-" + str(precision) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_catalog_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--refinement",
            str(precision),
            "--mode",
            mode,
        ]
        with (folder / ("reference-" + str(precision) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        result = json.loads(path.read_text())
        assert result["production_imports_denied"] and not result["loaded_production_modules"]
        results.append(result)
    return results


def local_inputs(inputs, parent, index, elapsed):
    result = copy.deepcopy(inputs)
    result.update(
        initial=plain(parent.pump.gated.material.values._asdict()),
        initial_rate_proxy_mol_m2_s=parent.pump.rate_proxy_mol_m2_s.tolist(),
        initial_calcium_rate_proxy_mol_m2_s=None
        if parent.calcium_rate_proxy_mol_m2_s is None
        else parent.calcium_rate_proxy_mol_m2_s.tolist(),
        actual_channel_caches=plain(ions.data(parent.channel_caches)),
        actual_channel_calls=list(parent.channel_calls),
        actual_gate_memory=plain(parent.pump.gated.memory._asdict()),
        actual_parent_identity=parent.identity,
        drives=[copy.deepcopy(inputs["drives"][index])],
        elapsed_start_s=elapsed,
        only_incoming_state_supplied=True,
    )
    return result


def exact_channels(trial, captured):
    phases = captured["channel_capture"]["events"]
    for actual, expected in zip(trial.material.channel_phases, phases, strict=True):
        for key in ("channel_id", "class_name", "skipped", "call_index", "dt_s", "native_dt"):
            assert getattr(actual, key) == expected[key], key
        for key in ("cache_before", "cache_after"):
            exact_cache(getattr(actual, key), expected[key])
        for key in ("values_before", "values_after"):
            exact(getattr(actual, key), expected[key])
        for route, wanted in zip(actual.routes, expected["routes"], strict=True):
            assert (
                route.ion_id == wanted["ion_id"]
                and route.relative_permeability == wanted["relative_permeability"]
            )
            for key in ("values_before", "values_after"):
                exact(getattr(route, key), wanted[key])
            exact_cache(route.cache_after, wanted["cache_after"])
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
    if trial.parent.calcium_rate_proxy_mol_m2_s is not None:
        network = captured["channel_capture"]["network"]
        assert network["actual_disabled_calcium_handler_executed"]
        np.testing.assert_array_equal(network["calcium_rate_before"], network["calcium_rate_after"])
        np.testing.assert_array_equal(
            trial.parent.calcium_rate_proxy_mol_m2_s, trial.candidate.calcium_rate_proxy_mol_m2_s
        )


def comparisons(binding, trial, wanted, less):
    rows, errors, budgets = inherited_comparisons(binding, trial, wanted, less)
    protocol = json.loads(PROTOCOL.read_text())
    ib = binding.pump_binding.gated_binding.material_binding
    factor = 128 * np.finfo(float).eps * (len(ib.ion_ids) + len(ib.membrane_ids) + 4 + 32)
    for slot, (phase, target, lower) in enumerate(
        zip(
            trial.material.channel_phases,
            wanted["channels"]["events"],
            less["channels"]["events"],
            strict=True,
        )
    ):
        tolerance = protocol["catalog_budgets"][phase.class_name]
        if phase.skipped:
            continue
        for key in ("m", "h", "P"):
            if key not in target:
                continue
            value = np.broadcast_to(phase.cache_after[key], np.asarray(target[key]).shape)
            budget = tolerance["absolute"] + tolerance["relative"] * abs(np.asarray(target[key]))
            name = "channel/" + str(slot) + "/" + key
            rows[name] = metric(value, target[key], budget) | dict(
                unit="dimensionless", budget_source=tolerance["source"]
            )
            rows["reference/" + name] = metric(lower[key], target[key], budget)
            errors[name], budgets[name] = abs(value - np.asarray(target[key])), budget
        for route_slot, (route, target_route, lower_route) in enumerate(
            zip(phase.routes, target["routes"], lower["routes"], strict=True)
        ):
            name = "channel/" + str(slot) + "/route/" + str(route_slot) + "/flux"
            budget = (
                factor * np.asarray(target_route["flux_gross"]) + FLOORS["membrane_flux_mol_m2_s"]
            )
            rows[name] = metric(route.flux_mol_m2_s, target_route["chan_flux"], budget) | dict(
                unit="mol/(m2*s)", budget_source="B24 unchanged local flux budget"
            )
            rows["reference/" + name] = metric(
                lower_route["chan_flux"], target_route["chan_flux"], budget
            )
            errors[name], budgets[name] = (
                abs(route.flux_mol_m2_s - np.asarray(target_route["chan_flux"])),
                budget,
            )
    return rows, errors, budgets


def check_sequence(tmp_path, class_name, steps, inputs=None):
    inputs = fixtures.fixture(class_name, steps=steps) if inputs is None else inputs
    initial = root(tmp_path) / ("preparation-" + class_name + "-" + str(steps))
    initial.mkdir(parents=True, exist_ok=False)
    (initial / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, class_name + "-" + str(steps) + "-constructor", inputs, error)
        raise
    constructor_path, nonfinite = archive_return(
        tmp_path,
        class_name + "-" + str(steps) + "-constructor",
        inputs,
        dict(binding=binding, parent=parent),
    )
    assert not nonfinite, "Nonfinite constructor RETURN retained at " + str(constructor_path)
    inputs["initial_channel_caches"] = plain(ions.data(parent.channel_caches))
    folder, captured = isolated(tmp_path, class_name + "-" + str(steps), inputs)
    assert captured["status"] == "source_completed"
    carried = independent(folder, "carried")
    elapsed = inputs["elapsed_start_s"]
    all_rows = []
    for index, source in enumerate(captured["history"]):
        local = folder / ("local-" + str(index))
        local.mkdir()
        (local / "inputs.json").write_text(
            json.dumps(local_inputs(inputs, parent, index, elapsed), indent=2, allow_nan=False)
            + "\n"
        )
        lower, tight = independent(local, "conditional_local")
        assert tight["conditional_on_actual_parent_identity"] == parent.identity
        before = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed)
        except Exception as error:
            archive_refusal(
                tmp_path,
                class_name + "-" + str(steps) + "-call-" + str(index),
                local_inputs(inputs, parent, index, elapsed),
                error,
            )
            raise
        returned_path, nonfinite = archive_return(
            tmp_path,
            "actual-" + class_name + "-" + str(steps) + "-" + str(index),
            local_inputs(inputs, parent, index, elapsed),
            dict(binding=binding, trial=trial),
        )
        assert not nonfinite, "Nonfinite step RETURN retained at " + str(returned_path)
        assert ions.digest(parent) == before
        material = source["material"]
        exact_phase(trial.material.pump.pump, material)
        for a, b in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (a.stage, a.ion_id) == (b["stage"], b["ion_id"])
            exact(a.values, b["values"])
        for a, b in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            exact_gate(a, b)
        exact_channels(trial, material)
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        if "Ca" in inputs["ion_definition"]["ions"]["ids"]:
            i = inputs["ion_definition"]["ions"]["ids"].index("Ca")
            assert np.any(
                trial.candidate.pump.gated.material.values.cell_mol_m3[i]
                != parent.pump.gated.material.values.cell_mol_m3[i]
            )
        rows, errors, budgets = comparisons(
            binding, trial, tight["history"][0], lower["history"][0]
        )
        archive(
            tmp_path,
            "local-errors-" + class_name + "-" + str(steps) + "-" + str(index),
            dict(errors=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(dict(parent_identity=parent.identity, fields=rows), indent=2) + "\n"
        )
        # Preserve separate carried absolute diagnostics with no propagated bound.
        diagnostic = {
            key: metric(value, carried[1]["history"][index]["final_state"][key])
            for key, value in trial.candidate.pump.gated.material.values._asdict().items()
        }
        (local / "carried-diagnostic.json").write_text(
            json.dumps(dict(fields=diagnostic, no_trajectory_error_bound=True), indent=2) + "\n"
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
        all_rows.append(rows)
        parent = trial.candidate
        elapsed = trial.clock["elapsed_end_s"]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=steps,
                conditional_actual_parent_checks=steps,
                carried_diagnostic_only=True,
                maximum_error_fraction=max(
                    r["normalized_max_error"]
                    for rows in all_rows
                    for r in rows.values()
                    if "normalized_max_error" in r
                ),
            ),
            indent=2,
        )
        + "\n"
    )


def check_nominal_nonfinite_refusal(tmp_path, class_name):
    """The original nominal Cav_G case remains failed positive coverage."""
    inputs = fixtures.fixture(class_name)
    initial = root(tmp_path) / ("preparation-" + class_name + "-nominal-refusal")
    initial.mkdir(parents=True, exist_ok=False)
    (initial / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, class_name + "-nominal-constructor", inputs, error)
        raise
    constructor_path, paths = archive_return(
        tmp_path, class_name + "-nominal-constructor", inputs, dict(binding=binding, parent=parent)
    )
    assert paths, "The unchanged singular nominal constructor must retain its nonfinite return"
    folder, captured = isolated(tmp_path, class_name + "-nominal-refusal", inputs)
    source_material = captured["history"][0]["material"]
    source_initial = source_material["channel_capture"]["initializations"]
    for actual, expected in zip(parent.channel_caches, source_initial, strict=True):
        exact_cache(actual, expected)
    assert nonfinite_paths(source_initial)
    try:
        returned = advance(inputs, binding, parent, 0, inputs["elapsed_start_s"])
    except channels.ChannelJoinRejected as error:
        refusal_path = archive_refusal(tmp_path, class_name + "-nominal-call-0", inputs, error)
        strict_reason = str(error)
    else:
        archive_return(tmp_path, class_name + "-nominal-call-0", inputs, returned)
        raise AssertionError("Strict model must refuse the nonfinite incoming cache")
    (folder / "failure-retention.json").write_text(
        json.dumps(
            dict(
                historical_failed_positive_id="test_native_catalog_actual_parent["
                + class_name
                + "]",
                raw_negative_case_id="test_raw_nominal_catalog_nonfinite[" + class_name + "]",
                historical_failed_positive_id_excluded_from_successor=True,
                nominal_positive_pass=False,
                coverage="explicit nominal nonfinite/refusal evidence only",
                source_status=captured["status"],
                source_failure=captured["failure"],
                source_initializer_return_nonfinite=True,
                model_constructor_return_nonfinite=True,
                nonfinite_paths=paths,
                raw_model_constructor=str(constructor_path),
                raw_model_refusal=str(refusal_path),
                strict_reason=strict_reason,
                strict_model_refused=True,
                exact_native_initialized_cache=True,
                independent_reference_executed=False,
                analytic_limit_substituted=False,
                repair_applied=False,
                physical_acceptance=False,
            ),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


@pytest.mark.parametrize(
    "class_name",
    [name for name in fixtures.CASES if name not in fixtures.SINGULAR_NOMINAL_CASES],
)
def test_native_catalog_actual_parent(tmp_path, class_name):
    check_sequence(tmp_path, class_name, 1)


@pytest.mark.parametrize("class_name", fixtures.SINGULAR_NOMINAL_CASES)
def test_raw_nominal_catalog_nonfinite(tmp_path, class_name):
    check_nominal_nonfinite_refusal(tmp_path, class_name)


@pytest.mark.parametrize("case_id", fixtures.NONSINGULAR_CASES)
def test_native_catalog_nonsingular(tmp_path, case_id):
    check_sequence(tmp_path, case_id, 1, fixtures.nonsingular_fixture(case_id))


@pytest.mark.parametrize("class_name", fixtures.CARRIED_CASES)
def test_native_catalog_carried_diagnostics(tmp_path, class_name):
    check_sequence(tmp_path, class_name, 3)


@pytest.mark.parametrize("order", ("forward", "reverse"))
def test_mixed_native_catalog_populations(tmp_path, order):
    inputs = fixtures.fixture("CatLeak", steps=3)
    names = ["Cav3p1", "HCN4_cAMP", "CatLeak", "Kv1p5S_ML"]
    if order == "reverse":
        names.reverse()
    rows = [
        dict(
            id="population" + str(i),
            class_name=name,
            targets=[8, 2, 8, 0, 4],
            maxDm_m2_s=2e-15,
            init_active=True,
        )
        for i, name in enumerate(names)
    ]
    inputs["channel_definition"]["channels"] = rows
    for drive in inputs["drives"]:
        drive["channels"]["modulators"] = {
            row["id"]: [0.4 + 0.02 * j for j in range(9)] for row in rows
        }
    check_sequence(tmp_path, "mixed_" + order, 3, inputs)


@pytest.mark.parametrize("mechanism", ("CaATP", "ER", "legacy_cag"))
def test_unimplemented_coupled_state_is_explicit(mechanism):
    inputs = fixtures.fixture("CatLeak")
    if mechanism == "CaATP":
        inputs["channel_definition"]["calcium_handler"]["alpha_Ca"] = 1e-6
    elif mechanism == "ER":
        inputs["channel_definition"]["calcium_handler"]["Ca_dyn"] = 1
    else:
        inputs["channel_definition"]["channels"][0]["class_name"] = "cagPotassium"
    with pytest.raises((channels.MissingCoupledState, ValueError)):
        seed(inputs)


@pytest.mark.parametrize(
    "failure",
    ("empty_profile", "Nav1p2_zero_quotient", "Cav2p2_zero_quotient", "Cav_G_zero_quotient"),
)
def test_raw_native_catalog_failures(tmp_path, failure):
    class_name = {
        "empty_profile": "Nav1p6",
        "Nav1p2_zero_quotient": "Nav1p2",
        "Cav2p2_zero_quotient": "Cav2p2",
        "Cav_G_zero_quotient": "Cav_G",
    }[failure]
    inputs = fixtures.fixture(class_name)
    if failure == "empty_profile":
        inputs["channel_definition"]["channels"][0]["targets"] = []
    else:
        inputs["initial"]["voltage_V"] = [
            -0.025 if class_name == "Nav1p2" else 0.020 if class_name == "Cav2p2" else -0.027
        ] * 9
        inputs["ion_definition"]["ions"]["moving_ids"] = []
        inputs["drives"][0]["pump"]["alpha_NaK"] = 0.0
    folder, captured = isolated(tmp_path, "raw-" + failure, inputs)
    with pytest.raises(channels.ChannelJoinRejected) as caught:
        binding, parent = seed(inputs)
        archive_return(
            tmp_path,
            "raw-" + failure + "-constructor",
            inputs,
            dict(binding=binding, parent=parent),
        )
        returned = advance(inputs, binding, parent, 0, inputs["elapsed_start_s"])
        archive_return(tmp_path, "raw-" + failure + "-call-0", inputs, returned)
    error = caught.value
    path = archive(
        tmp_path,
        "raw-model-" + failure,
        dict(
            parent=error.parent,
            material=error.material,
            phases=error.channel_phases,
            initialization=error.initialization,
            reason=str(error),
        ),
    )
    assert captured["status"] == "source_refused"
    if failure == "empty_profile":
        assert captured["failure"]["type"] == "IndexError"
        exact_cache(
            error.initialization["failed_core_cache"],
            captured["channel_initialization_failure"]["failed_core_cache"],
        )
    (folder / "failure-retention.json").write_text(
        json.dumps(
            dict(
                source_status=captured["status"],
                source_failure=captured["failure"],
                raw_model=str(path),
                strict_model_refused=True,
                analytic_limit_substituted=False,
                repair_applied=False,
                physical_acceptance=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    runtime = runtime_inventory()
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
    if value := os.environ.get("CELLS_CATALOG_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(value)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")

"""Source-exact Na/K join plus inherited-budget actual-parent local checks."""

import copy
import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_channel_join as channels
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as join
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_gated_join import exact_gate
from tests.unit.test_betse_normal_ion_join import FLOORS as MATERIAL_FLOORS
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_normal_channel_join_fixtures as fixtures
from validation.betse import betse_normal_channel_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-channel-join"


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, join.data(payload))


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "inputs.json"
    path.write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_channel_join_native",
        "--inputs",
        str(path),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    captured = archive_read(folder / "native")
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"]
    if cpu := os.environ.get("CELLS_CHANNEL_JOIN_CPU"):
        assert captured["runtime"]["measured_cpu_affinity"] == [int(cpu)]
    return folder, captured


def independent(folder, mode="carried"):
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_channel_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--mode",
            mode,
            "--refinement",
            str(level),
        ]
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        answer = json.loads(path.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        if cpu := os.environ.get("CELLS_CHANNEL_JOIN_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer)
    return answers


SOURCE_ROOT = Path(__file__).resolve().parents[2]
PUMP_TOLERANCES = json.loads(
    (SOURCE_ROOT / "validation/betse/pump_loop_preflight/protocol.json").read_text()
)["tolerances"]
GATE_TOLERANCES = json.loads(
    (SOURCE_ROOT / "validation/betse/junction_gate/protocol.json").read_text()
)["tolerances"]


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def seed(case="standard", inputs=None):
    inputs = fixtures.fixture(case) if inputs is None else inputs
    ib = join.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    gb = gated.bind(ib, vb, inputs["gate_definition"])
    binding = pump.bind(gb, inputs["pump_definition"])
    parent = pump.initialize(
        binding,
        join.state(ib, inputs["initial"]),
        initial_gate_block=inputs["initial_gate_block"],
        initial_rate_proxy_mol_m2_s=inputs["initial_rate_proxy_mol_m2_s"],
    )
    binding = channels.bind(binding, inputs["channel_definition"])
    parent = channels.initialize(binding, parent)
    return inputs, binding, parent


def advance(inputs, binding, parent, index=0, elapsed=None):
    forcing = inputs["drives"][index]
    return channels.advance(
        binding,
        parent,
        join.drive(binding.pump_binding.gated_binding.material_binding, **forcing["material"]),
        pump.packet(binding.pump_binding, **forcing["pump"]),
        channels.packet(binding, **forcing["channels"]),
        boundary_V=forcing["boundary_V"],
        extra_charge_C_m3=forcing["extra_charge_C_m3"],
        extra_current_A_m2=forcing["extra_current_A_m2"],
        elapsed_s=inputs["elapsed_start_s"] if elapsed is None else elapsed,
    )


def one(case="standard"):
    inputs, binding, parent = seed(case)
    return inputs, binding, advance(inputs, binding, parent)


def actual_parent_inputs(inputs, parent, index, elapsed):
    local = copy.deepcopy(inputs)
    local["initial"] = plain(parent.pump.gated.material.values._asdict())
    local["initial_rate_proxy_mol_m2_s"] = parent.pump.rate_proxy_mol_m2_s.tolist()
    local["actual_gate_memory"] = plain(parent.pump.gated.memory._asdict())
    local["actual_parent_identity"] = parent.identity
    local["actual_channel_caches"] = plain(join.data(parent.channel_caches))
    local["actual_channel_calls"] = list(parent.channel_calls)
    local["drives"] = [copy.deepcopy(inputs["drives"][index])]
    local["elapsed_start_s"] = elapsed
    local["only_incoming_state_supplied"] = True
    return local


def metric(value, wanted, budget=None):
    a, b = np.asarray(value), np.asarray(wanted)
    error = abs(a - b)
    if not error.size:
        return dict(absolute_max_error=0.0, index_at_absolute_max=[], normalized_max_error=0.0)
    where = np.unravel_index(np.argmax(error), error.shape)
    row = dict(
        absolute_max_error=float(error[where]),
        index_at_absolute_max=[int(index) for index in where],
        model_at_absolute_max=float(a[where]),
        reference_at_absolute_max=float(b[where]),
    )
    if budget is not None:
        budget = np.broadcast_to(budget, error.shape)
        row.update(
            budget_at_absolute_max=float(budget[where]),
            minimum_budget=float(np.min(budget)),
            maximum_budget=float(np.max(budget)),
            normalized_max_error=float(np.max(error / budget)),
        )
    return row


def field_unit(group, key):
    if group == "pump":
        return "mol/(m2*s)"
    if group == "gate":
        return "V" if "voltage" in key else "1/ms" if "per_ms" in key else "dimensionless"
    if "flux" in key:
        return "mol/(m2*s)"
    if "mol_m3" in key:
        return "mol/m3 (mM)"
    if "charge_density" in key:
        return "C/m3"
    if "surface_charge" in key:
        return "C/m2"
    if "conductivity" in key:
        return "S/m"
    if "derivative" in key:
        return "V/s"
    if "field" in key:
        return "V/m"
    if "rhs" in key:
        return "V/m2"
    if "voltage" in key or "potential" in key:
        return "V"
    if "current" in key:
        return "A" if key.endswith("_A") else "A/m2"
    return "dimensionless"


def exact_cache(actual, expected):
    assert set(actual) == set(expected)
    for key in actual:
        a, b = actual[key], expected[key]
        if isinstance(b, np.ndarray):
            assert isinstance(a, np.ndarray) and a.dtype == b.dtype, key
            np.testing.assert_array_equal(a, b, err_msg=key)
        elif isinstance(b, (list, tuple)):
            assert tuple(a) == tuple(b), key
        else:
            assert a == b, (key, a, b)


def exact_channels(trial, source):
    captured = source["channel_capture"]
    for phase, expected in zip(trial.material.channel_phases, captured["events"], strict=True):
        for key in (
            "channel_id",
            "class_name",
            "ion_id",
            "skipped",
            "call_index",
            "dt_s",
            "native_dt",
        ):
            assert getattr(phase, key) == expected[key], key
        exact_cache(phase.cache_before, expected["cache_before"])
        exact_cache(phase.cache_after, expected["cache_after"])
        for key in (
            "voltage_before_V",
            "voltage_after_V",
            "sampled_bulk_mM",
            "sampled_membrane_mM",
            "sampled_bath_mM",
            "diffusion_m2_s",
            "flux_mol_m2_s",
            "network_current_before_A_m2",
            "network_current_after_A_m2",
        ):
            a, b = getattr(phase, key), expected[key]
            if b is None:
                assert a is None
            else:
                assert np.asarray(a).dtype == np.asarray(b).dtype, key
                np.testing.assert_array_equal(a, b, err_msg=key)
        exact(phase.values_before, expected["values_before"])
        exact(phase.values_after, expected["values_after"])
    assert (
        trial.material.network["current_publication"] == captured["network"]["current_publication"]
    )
    assert captured["network"]["aliases_follow_live_rows"]
    for key in ("extra_current_A_m2", "extra_charge_C_m3", "energy_charge"):
        np.testing.assert_array_equal(trial.material.network[key], captured["network"][key])
    for cache, expected in zip(
        trial.candidate.channel_caches, source["channel_caches"], strict=True
    ):
        exact_cache(cache, expected)
    assert tuple(captured["calls"]) == trial.candidate.channel_calls


CHANNEL_PROTOCOLS = {
    name: json.loads((SOURCE_ROOT / path).read_text())["tolerances"]
    for name, path in {
        "Nav1p6": "validation/channels/sodium_catalog_protocol.json",
        "Kv3p2": "validation/channels/potassium_catalog_protocol.json",
        "ClLeak": "validation/channels/leak_channels_protocol.json",
        "Kv1p5": "validation/tissue/surface_channel_protocol.json",
    }.items()
}


def local_comparisons(binding, trial, target, less):
    rows, errors, budgets = pump_local_comparisons(binding, trial, target, less)
    ib = binding.pump_binding.gated_binding.material_binding
    factor = 128 * np.finfo(np.float64).eps * (len(ib.ion_ids) + len(ib.membrane_ids) + 4 + 32)
    for slot, (phase, expected, lesser) in enumerate(
        zip(
            trial.material.channel_phases,
            target["channels"]["events"],
            less["channels"]["events"],
            strict=True,
        )
    ):
        assert phase.skipped == expected["skipped"]
        if phase.skipped:
            continue
        protocol = CHANNEL_PROTOCOLS[phase.class_name]
        for key in ("m", "h", "P", "DChan", "chan_flux"):
            actual, wanted = phase.cache_after[key], np.asarray(expected[key])
            if key in ("m", "h", "P"):
                rtol, atol = (
                    (protocol["decimal_gate_rtol"], protocol["decimal_gate_atol"])
                    if phase.class_name == "Kv1p5"
                    else (protocol["relative"], protocol["gate_atol"])
                )
                budget = atol + rtol * abs(wanted)
                unit = "dimensionless"
            elif key == "chan_flux":
                budget = (
                    factor * np.asarray(expected["flux_gross"])
                    + MATERIAL_FLOORS["membrane_flux_mol_m2_s"]
                )
                unit = "mol/(m2*s)"
            else:
                rows["channel/" + str(slot) + "/" + key] = metric(actual, wanted) | dict(
                    unit="m2/s", diagnostic_only=True
                )
                continue
            name = "channel/" + str(slot) + "/" + key
            # Native unused h may be scalar while the independent equations
            # explicitly repeat it for every target. Shape is exact-native.
            rows[name] = metric(np.broadcast_to(actual, wanted.shape), wanted, budget) | dict(
                unit=unit, budget_source="inherited catalog gate or B24 material flux budget"
            )
            rows["reference/" + name] = metric(lesser[key], wanted, budget)
            errors[name], budgets[name] = abs(np.asarray(actual) - wanted), budget
        name = "channel/" + str(slot) + "/network_current_A_m2"
        budget = (
            32
            * np.finfo(np.float64).eps
            * (len(ib.ion_ids) + len(ib.membrane_ids) + 16)
            * np.asarray(expected["network_current_gross"])
            + 1e-30
        )
        rows[name] = metric(
            phase.network_current_after_A_m2, expected["network_current"], budget
        ) | dict(unit="A/m2", budget_source="B23 current local budget")
        rows["reference/" + name] = metric(
            lesser["network_current"], expected["network_current"], budget
        )
        errors[name], budgets[name] = (
            abs(phase.network_current_after_A_m2 - np.asarray(expected["network_current"])),
            budget,
        )
    return rows, errors, budgets


def pump_local_comparisons(binding, trial, target, less):
    """Registered inherited budgets, conditioned on this actual pre-call state."""
    ib = binding.pump_binding.gated_binding.material_binding
    vb = binding.pump_binding.gated_binding.voltage_binding
    count, membranes = len(ib.ion_ids), len(ib.membrane_ids)
    eps = np.finfo(np.float64).eps
    rows, errors, budgets = {}, {}, {}
    groups = (
        (
            "material",
            trial.material.pump.candidate.gated.material.values,
            target["material_state"],
            target["material_gross"],
            less["material_state"],
        ),
        (
            "current",
            trial.current.values,
            target["current"]["values"],
            target["current"]["gross"],
            less["current"]["values"],
        ),
        (
            "voltage",
            trial.voltage.values,
            target["voltage"]["values"],
            target["voltage"]["gross"],
            less["voltage"]["values"],
        ),
    )
    for group, values, expected, gross, less_values in groups:
        for key, value in values._asdict().items():
            factor = (
                128 * eps * (count + membranes + 4 + 32)
                if group == "material"
                else 32 * eps * (count + membranes + 16)
                if group == "current"
                else 1024 * eps * (count + membranes + np.prod(vb.kernel.shape) + 16 + 64)
            )
            budget = factor * np.asarray(gross[key]) + (
                MATERIAL_FLOORS[key] if group == "material" else 1e-30
            )
            name = group + "/" + key
            rows[name] = metric(value, expected[key], budget) | dict(
                unit=field_unit(group, key),
                budget_source=group + " registered single-call component budget",
            )
            rows["reference/" + name] = metric(less_values[key], expected[key], budget)
            errors[name], budgets[name] = abs(value - np.asarray(expected[key])), budget
    for key, expected in target["pump"]["values"].items():
        value = getattr(trial.material.pump.pump, key)
        budget = PUMP_TOLERANCES["density_mol_per_m2_s"] + PUMP_TOLERANCES["relative"] * abs(
            np.asarray(expected)
        )
        name = "pump/" + key
        rows[name] = metric(value, expected, budget) | dict(
            unit=field_unit("pump", key), budget_source="pump_loop_preflight density/relative"
        )
        rows["reference/" + name] = metric(less["pump"]["values"][key], expected, budget)
        errors[name], budgets[name] = abs(value - np.asarray(expected)), budget
    if target["pump"]["arithmetic"] is not None:
        for key, expected in target["pump"]["arithmetic"].items():
            value = getattr(trial.material.pump.pump.arithmetic, key)
            if key == "zero_denominator_indices":
                np.testing.assert_array_equal(value, expected)
                continue
            name = "pump_arithmetic/" + key
            if "flux" in key or "proxy" in key:
                budget = PUMP_TOLERANCES["density_mol_per_m2_s"] + PUMP_TOLERANCES[
                    "relative"
                ] * abs(np.asarray(expected))
                rows[name] = metric(value, expected, budget) | dict(
                    unit="mol/(m2*s)", budget_source="pump_loop_preflight density/relative"
                )
                rows["reference/" + name] = metric(
                    less["pump"]["arithmetic"][key], expected, budget
                )
                errors[name], budgets[name] = abs(value - np.asarray(expected)), budget
            else:
                rows[name] = metric(value, expected) | dict(
                    unit="dimensionless source activity/coefficient", diagnostic_only=True
                )
    for slot, (event, expected, lesser) in enumerate(
        zip(
            trial.material.pump.gated.gate_updates,
            target["gate_updates"],
            less["gate_updates"],
            strict=True,
        )
    ):
        for key, wanted in expected["values"].items():
            value = getattr(event, key)
            name = "gate/" + str(slot) + "/" + key
            if "opening" in key:
                budget = GATE_TOLERANCES["source_gate_atol"] + GATE_TOLERANCES[
                    "source_gate_rtol"
                ] * abs(np.asarray(wanted))
                rows[name] = metric(value, wanted, budget) | dict(
                    unit="dimensionless source gate",
                    budget_source="junction_gate source_gate_atol/rtol",
                )
                rows["reference/" + name] = metric(lesser["values"][key], wanted, budget)
                errors[name], budgets[name] = abs(value - np.asarray(wanted)), budget
            elif "voltage" in key:
                budget = (
                    128 * eps * (count + membranes + 4 + 32) * np.asarray(expected["gross"][key])
                    + MATERIAL_FLOORS["junction_voltage_V"]
                )
                rows[name] = metric(value, wanted, budget) | dict(
                    unit="V", budget_source="material junction_voltage local budget"
                )
                errors[name], budgets[name] = abs(value - np.asarray(wanted)), budget
            else:
                rows[name] = metric(value, wanted) | dict(unit="1/ms", diagnostic_only=True)
    return rows, errors, budgets


def exact_phase(phase, source):
    observed = source["pump_observations"]
    if phase.arithmetic is None:
        assert not observed
    else:
        for key, value in phase.arithmetic._asdict().items():
            assert value.dtype == observed[key].dtype, key
            np.testing.assert_array_equal(value, observed[key], err_msg=key)
        for key in (
            "sodium_at_mem_mM",
            "potassium_at_mem_mM",
            "sodium_bath_mM",
            "potassium_bath_mM",
            "voltage_before_nonce_V",
        ):
            np.testing.assert_array_equal(getattr(phase, key), observed[key])
        assert phase.runtime_temperature_K == observed["runtime_temperature_K"]
    for key in (
        "scaled_sodium_flux_mol_m2_s",
        "scaled_potassium_flux_mol_m2_s",
        "applied_sodium_flux_mol_m2_s",
        "applied_potassium_flux_mol_m2_s",
    ):
        np.testing.assert_array_equal(
            getattr(phase, key), observed[key] if phase.arithmetic is not None else np.zeros(9)
        )
    frames = source["history"][0]["frames"]
    assert frames[1]["stage"] == "reset_flux" and frames[2]["stage"] == "pump_accumulated"
    np.testing.assert_array_equal(
        phase.storage_before_mol_m2_s, frames[1]["values"]["membrane_flux_mol_m2_s"]
    )
    np.testing.assert_array_equal(
        phase.storage_after_mol_m2_s, frames[2]["values"]["membrane_flux_mol_m2_s"]
    )
    np.testing.assert_array_equal(phase.rate_proxy_before_mol_m2_s, source["rate_proxy_before"])
    np.testing.assert_array_equal(phase.rate_proxy_after_mol_m2_s, source["rate_proxy_after"])


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    if cpu := os.environ.get("CELLS_CHANNEL_JOIN_CPU"):
        assert affinity == [int(cpu)]
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
    (folder / "runtime.json").write_text(
        json.dumps(
            runtime_inventory()
            | dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=pump.SOURCE_REVISION,
                exact_native_primary=True,
                independent_acceptance="actual-parent one-call checks with inherited budgets",
                carried_decimal="diagnostic only, no propagated-trajectory-bound claim",
                maintained_metabolic_pools=True,
                met_argument_used=False,
                coordinated_shared_edit_modules_loaded=[],
                full_native_or_physical_parity=False,
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_full_sequence_and_actual_parent_conditional_local_checks(tmp_path, case):
    inputs = fixtures.fixture(case)
    folder, captured = isolated(tmp_path, case, inputs)
    if case == "empty_targets":
        assert captured["status"] == "source_refused"
        with pytest.raises(channels.ChannelJoinRejected) as caught:
            seed(inputs=inputs)
        actual = caught.value.initialization
        expected = captured["channel_initialization_failure"]
        exact_cache(actual["failed_core_cache"], expected["failed_core_cache"])
        assert actual["source_exception"] == expected["source_exception"] == "IndexError"
        assert actual["channel_id"] == expected["channel_id"]
        archive(tmp_path, "empty-profile-initialization-refusal", actual)
        assert caught.value.stage == "channel_initialization" and actual["no_repair_applied"]
        return
    inputs, binding, parent = seed(inputs=inputs)
    original = join.digest(inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    carried_standard, carried_tight = independent(folder, "carried")
    assert carried_tight["carried_profile_is_diagnostic_only"]
    nmove = len(binding.pump_binding.gated_binding.material_binding.kernel.moving)
    assert nmove == fixtures.CASE_MOVING_COUNTS[case]
    elapsed = inputs["elapsed_start_s"]
    comparisons = []
    material_frames = gate_calls = channel_calls = 0
    for index, source in enumerate(captured["history"]):
        before = join.digest(parent)
        local = folder / ("local-" + str(index))
        local.mkdir()
        conditioned = actual_parent_inputs(inputs, parent, index, elapsed)
        (local / "inputs.json").write_text(
            json.dumps(conditioned, indent=2, allow_nan=False) + "\n"
        )
        less, tight = independent(local, "conditional_local")
        assert tight["conditional_on_actual_parent_identity"] == parent.identity
        assert tight["mode"] == "conditional_local" and len(tight["history"]) == 1
        # Local reference inputs are written and answered before the model's
        # outgoing state is computed. No candidate/current/voltage answers enter.
        trial = advance(inputs, binding, parent, index, elapsed)
        actual_path = archive(
            tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial)
        )
        assert trial.parent is parent and join.digest(parent) == before
        native_material = source["material"]
        exact_phase(trial.material.pump.pump, native_material)
        for frame, native_frame in zip(
            trial.material.pump.gated.material.frames,
            native_material["history"][0]["frames"],
            strict=True,
        ):
            assert (frame.stage, frame.ion_id) == (native_frame["stage"], native_frame["ion_id"])
            exact(frame.values, native_frame["values"])
        for event, native_event in zip(
            trial.material.pump.gated.gate_updates, native_material["gate_updates"], strict=True
        ):
            exact_gate(event, native_event)
        exact_channels(trial, native_material)
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        np.testing.assert_array_equal(
            trial.candidate.pump.rate_proxy_mol_m2_s, native_material["rate_proxy_after"]
        )
        rows, errors, budgets = local_comparisons(
            binding, trial, tight["history"][0], less["history"][0]
        )
        error_path = archive(
            tmp_path,
            "local-errors-" + case + "-" + str(index),
            dict(absolute_error_arrays=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(
                dict(
                    context="conditional local from actual incoming parent",
                    parent_identity=parent.identity,
                    exact_native=True,
                    fields=rows,
                    absolute_error_arrays=str(error_path),
                    physical_accuracy_claim=False,
                ),
                indent=2,
            )
            + "\n"
        )
        # Full carried answers are preserved separately and do not inherit or
        # masquerade as fixed local acceptance budgets.
        carried_rows = {}
        for group, values, expected in (
            (
                "material",
                trial.material.pump.candidate.gated.material.values,
                carried_tight["history"][index]["material_state"],
            ),
            ("current", trial.current.values, carried_tight["history"][index]["current"]["values"]),
            ("voltage", trial.voltage.values, carried_tight["history"][index]["voltage"]["values"]),
        ):
            for key, value in values._asdict().items():
                carried_rows[group + "/" + key] = metric(value, expected[key]) | dict(
                    unit=field_unit(group, key), diagnostic_only=True
                )
        (local / "carried-diagnostic.json").write_text(
            json.dumps(
                dict(
                    fields=carried_rows,
                    no_trajectory_error_bound=True,
                    two_precision_answers_preserved=True,
                    standard_precision=carried_standard["decimal_precision"],
                ),
                indent=2,
            )
            + "\n"
        )
        normalized = max(
            row["normalized_max_error"] for row in rows.values() if "normalized_max_error" in row
        )
        resolution = max(
            row["normalized_max_error"]
            for name, row in rows.items()
            if name.startswith("reference/")
        )
        comparisons.append(
            dict(
                call_index=index + 1,
                maximum_local_error_fraction=normalized,
                reference_resolution_fraction=resolution,
                raw_actual=str(actual_path),
                conditional_comparison=str(local / "comparison.json"),
            )
        )
        material_frames += len(trial.material.pump.gated.material.frames)
        gate_calls += len(trial.material.pump.gated.gate_updates)
        channel_calls += trial.clock["native_channel_calls"]
        parent = trial.candidate
        elapsed = trial.clock["elapsed_end_s"]
    maximum = max(row["maximum_local_error_fraction"] for row in comparisons)
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=3,
                frames=material_frames,
                gate_calls=gate_calls,
                channel_calls=channel_calls,
                comparisons=comparisons,
                exact_host_native_correspondence=True,
                conditional_actual_parent_calls=3,
                fresh_conditional_reference_forms=6,
                fresh_carried_reference_forms=2,
                maximum_error_fraction=maximum,
                carried_decimal_is_diagnostic_only=True,
                physical_accuracy_or_full_native_claim=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert join.digest(inputs) == original
    assert maximum <= 1 and all(
        row["reference_resolution_fraction"] <= 0.1 for row in comparisons
    ), comparisons


def test_late_source_order_and_alias_sampling():
    _, binding, trial = one("stale_membrane")
    frames = trial.material.pump.gated.material.frames
    stages = [f.stage for f in frames]
    assert (
        stages.index("pump_accumulated")
        < stages.index("refresh_at_mem")
        < stages.index("network_clear")
    )
    assert stages.index("network_publish") < stages.index("membrane_commit")
    owner = binding.pump_binding.gated_binding.material_binding.kernel.owner
    for phase in trial.material.channel_phases:
        i = binding.pump_binding.gated_binding.material_binding.ion_ids.index(phase.ion_id)
        np.testing.assert_array_equal(
            phase.sampled_membrane_mM, phase.values_before.cell_mol_m3[i][owner]
        )
        np.testing.assert_array_equal(
            phase.values_before.membrane_flux_mol_m2_s, phase.values_after.membrane_flux_mol_m2_s
        )
    # Later K population sees the immediately updated live alias from Kv1p5.
    np.testing.assert_array_equal(
        trial.material.channel_phases[2].sampled_bulk_mM,
        trial.material.channel_phases[1].values_after.cell_mol_m3[1],
    )


def test_channels_ignore_closed_cluster_boundary_mask():
    _, binding, trial = one()
    mask = binding.pump_binding.gated_binding.material_binding.kernel.boundary
    assert not binding.pump_binding.gated_binding.material_binding.kernel.cluster_open
    phase = trial.material.channel_phases[-1]
    assert np.any(phase.flux_mol_m2_s[mask] != 0)
    assert trial.material.network["source_channel_flux_boundary_mask"] is False


@pytest.mark.parametrize("case", ("publish_off", "standard", "no_channels"))
def test_network_publication_replaces_or_retains_incoming_current(case):
    inputs, _, trial = one(case)
    expected = (
        np.asarray(inputs["drives"][0]["extra_current_A_m2"])
        if case == "publish_off"
        else trial.material.network["extra_current_A_m2"]
    )
    np.testing.assert_array_equal(trial.current.source.extra_current_A_m2, expected)
    assert trial.material.network["current_publication"] == (
        "retain incoming" if case == "publish_off" else "replace"
    )


def test_original_clock_units_and_init_skip_resume_cache():
    inputs, binding, parent = seed("init_skip_restore")
    trial = advance(inputs, binding, parent)
    assert [phase.native_dt for phase in trial.material.channel_phases] == [
        inputs["drives"][0]["material"]["dt_s"] * 1000,
        0.0,
        inputs["drives"][0]["material"]["dt_s"] * 1000,
        0.0,
    ]
    resumed = advance(inputs, binding, trial.candidate, 1, trial.clock["elapsed_end_s"])
    assert resumed.clock["native_channel_calls"] == 4
    assert resumed.material.channel_phases[-1].native_dt == inputs["drives"][1]["material"]["dt_s"]
    for a, b in zip(parent.channel_caches, trial.candidate.channel_caches, strict=True):
        assert "P" not in a
        assert b["time_unit"] in (1.0, 1000.0)


def test_blocked_channels_keep_running_and_restore():
    inputs, binding, parent = seed("blocked_restore")
    trial = advance(inputs, binding, parent)
    assert trial.clock["native_channel_calls"] == 4
    for phase in trial.material.channel_phases:
        np.testing.assert_array_equal(phase.flux_mol_m2_s, 0)
    second = advance(inputs, binding, trial.candidate, 1, trial.clock["elapsed_end_s"])
    assert all(c == 2 for c in second.candidate.channel_calls)
    assert np.any(second.material.network["extra_current_A_m2"] != 0)


def test_targets_duplicate_overwrite_empty_and_state_immutability():
    inputs, binding, parent = seed("duplicate_targets")
    before = join.digest(parent)
    trial = advance(inputs, binding, parent)
    assert join.digest(parent) == before
    for phase in trial.material.channel_phases:
        opened = phase.cache_after["P"]
        np.testing.assert_array_equal(opened[[1, 3, 5, 6, 7]], 0)
        assert opened[8] == opened[2] or phase.class_name != "ClLeak"
        assert not opened.flags.writeable
        with pytest.raises(ValueError):
            opened[0] = 9.0
    with pytest.raises(channels.ChannelJoinRejected) as caught:
        seed("empty_targets")
    assert caught.value.stage == "channel_initialization"


@pytest.mark.parametrize("fault", ("class", "targets", "modulator", "parent"))
def test_invalid_channel_definition_packet_and_parent(fault):
    inputs, binding, parent = seed()
    if fault in ("class", "targets"):
        raw = copy.deepcopy(inputs["channel_definition"])
        raw["channels"][0]["class_name" if fault == "class" else "targets"] = (
            "unknown" if fault == "class" else [99]
        )
        with pytest.raises(ValueError):
            channels.bind(binding.pump_binding, raw)
    elif fault == "modulator":
        live = copy.deepcopy(inputs["drives"][0]["channels"])
        live["modulators"]["nav1p6"][0] = float("nan")
        with pytest.raises(ValueError):
            channels.packet(binding, **live)
    else:
        bad = replace(parent, channel_calls=(99,) + parent.channel_calls[1:])
        with pytest.raises(channels.ChannelJoinRejected):
            advance(inputs, binding, bad)


@pytest.mark.parametrize("failure", ("gate_pole", "channel_flux_overflow"))
def test_raw_source_failures_preserve_native_partial_channel_state(tmp_path, failure):
    inputs = fixtures.fixture()
    inputs["ion_definition"]["ions"]["moving_ids"] = []
    for forcing in inputs["drives"]:
        forcing["pump"]["alpha_NaK"] = 0.0
    inputs["drives"] = inputs["drives"][:1]
    if failure == "gate_pole":
        inputs["initial"]["voltage_V"] = [0.08] * 9
        inputs["channel_definition"]["channels"] = [inputs["channel_definition"]["channels"][1]]
        inputs["drives"][0]["material"]["dt_s"] = -((-0.1163 * 80) + 8.3300) / 1000
        inputs["drives"][0]["channels"]["modulators"] = {"kv1p5": [1.0] * 9}
    else:
        inputs["initial"]["voltage_V"] = [-0.02] * 9
        inputs["drives"][0]["material"]["runtime_temperature_K"] = 1e-12
    _, captured = isolated(tmp_path, failure, inputs)
    _, binding, parent = seed(inputs=inputs)
    with pytest.raises(channels.ChannelJoinRejected) as caught:
        advance(inputs, binding, parent)
    error = caught.value
    path = archive(
        tmp_path,
        "raw-failure-" + failure,
        dict(
            reason=str(error),
            material=error.material,
            phases=error.channel_phases,
            network=error.network,
        ),
    )
    source = captured["history"][0]["material"]
    assert error.channel_phases and source["channel_capture"]["events"]
    for phase, expected in zip(
        error.channel_phases, source["channel_capture"]["events"], strict=True
    ):
        exact_cache(phase.cache_after, expected["cache_after"])
        exact(phase.values_after, expected["values_after"])
    (root(tmp_path) / ("failure-" + failure + ".json")).write_text(
        json.dumps(
            dict(
                source_status=captured["status"],
                source_failure=captured["failure"],
                strict_model_refused=True,
                raw_model=str(path),
                stage=error.stage,
                repair_applied=False,
                physical_acceptance=False,
            ),
            indent=2,
        )
        + "\n"
    )

"""Native active-gate state/order/clock coupling and actual refused source trials."""

import copy
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as join
from cells.processes import betse_normal_voltage as voltage
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS as MATERIAL_FLOORS
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_normal_gated_join_fixtures as fixtures
from validation.betse import betse_normal_gated_join_native as native


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-gated-join"


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
        "validation.betse.betse_normal_gated_join_native",
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
    if cpu := os.environ.get("CELLS_GATED_JOIN_CPU"):
        assert captured["runtime"]["measured_cpu_affinity"] == [int(cpu)]
    return folder, captured


def independent(folder):
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_gated_join_reference",
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
        if cpu := os.environ.get("CELLS_GATED_JOIN_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer)
    return answers


def seed(case="standard", inputs=None):
    inputs = fixtures.fixture(case) if inputs is None else inputs
    ib = join.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    binding = gated.bind(ib, vb, inputs["gate_definition"])
    parent = join.state(ib, inputs["initial"])
    return (
        inputs,
        binding,
        gated.initialize(binding, parent, initial_block=inputs["initial_gate_block"]),
    )


def advance(inputs, binding, parent, index=0, elapsed=None):
    forcing = inputs["drives"][index]
    return gated.advance(
        binding,
        parent,
        join.drive(binding.material_binding, **forcing["material"]),
        boundary_V=forcing["boundary_V"],
        extra_charge_C_m3=forcing["extra_charge_C_m3"],
        extra_current_A_m2=forcing["extra_current_A_m2"],
        elapsed_s=inputs["elapsed_start_s"] if elapsed is None else elapsed,
    )


def one(case="standard"):
    inputs, binding, parent = seed(case)
    return inputs, binding, advance(inputs, binding, parent)


def exact_gate(frame, source):
    assert frame.ion_id == source["ion_id"] and frame.update_index == source["update_index"]
    assert frame.dt_s == source["dt_s"] and frame.dt_ms == source["dt_ms"]
    for key in frame._fields:
        if key not in ("ion_id", "update_index", "dt_s", "dt_ms"):
            value = getattr(frame, key)
            assert value.dtype == source[key].dtype, key
            np.testing.assert_array_equal(value, source[key], err_msg=key)


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    if cpu := os.environ.get("CELLS_GATED_JOIN_CPU"):
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
            dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=gated.SOURCE_REVISION,
                gate_policy="full dt per moving ion; stored-state blocking",
                coordinated_shared_edit_modules_loaded=[],
                physical_gate_law=False,
                environment_HH_Gaussian=False,
                full_native_solver=False,
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_carried_active_gate_material_current_voltage_native_and_independent(tmp_path, case):
    inputs, binding, parent = seed(case)
    original = join.digest(inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    standard, tight = independent(folder)
    nmove = len(binding.material_binding.kernel.moving)
    assert nmove == fixtures.CASE_MOVING_COUNTS[case]
    init = captured["history"][0]["material"]["gate_initialization"]
    for key, source_key in (
        ("alpha_per_ms", "alpha"),
        ("beta_per_ms", "beta"),
        ("class_open", "gjopen"),
    ):
        np.testing.assert_array_equal(
            getattr(parent.memory, key), init["actual_class_cache"][source_key]
        )
    np.testing.assert_array_equal(parent.memory.raw_beta_per_ms, init["raw_beta_per_ms"])
    np.testing.assert_array_equal(init["sim_open_before"], init["sim_open_after"])
    assert {key: init["actual_class_cache"][key] for key in ("lamb", "A1", "A2", "Ao")} == dict(
        lamb=0.0013, A1=0.077, A2=0.14, Ao=0.217
    )
    init_errors = []
    for key in ("alpha_per_ms", "raw_beta_per_ms", "beta_per_ms", "class_open"):
        wanted = np.asarray(tight["initialization"][key])
        budget = (
            128
            * np.finfo(np.float64).eps
            * (len(parent.material.values.voltage_V) + 32)
            * abs(wanted)
            + 1e-30
        )
        init_errors.append(
            float(np.max(abs(getattr(parent.memory, key) - wanted) / budget, initial=0))
        )
    archive(
        tmp_path,
        "initialization-" + case,
        dict(binding=binding, initialized=parent, errors=init_errors),
    )
    elapsed = inputs["elapsed_start_s"]
    comparisons = []
    frame_count = gate_count = 0
    for index, (actual, less, target) in enumerate(
        zip(captured["history"], standard["history"], tight["history"], strict=True)
    ):
        before = join.digest(parent)
        trial = advance(inputs, binding, parent, index, elapsed)
        path = archive(
            tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial)
        )
        assert trial.parent is parent and join.digest(parent) == before
        assert trial.material.parent is parent and trial.voltage.source_current is trial.current
        material = actual["material"]
        for frame, source in zip(
            trial.material.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (frame.stage, frame.ion_id) == (source["stage"], source["ion_id"])
            exact(frame.values, source["values"])
        assert len(trial.material.gate_updates) == nmove
        for gate_frame, source in zip(
            trial.material.gate_updates, material["gate_updates"], strict=True
        ):
            exact_gate(gate_frame, source)
        cache = material["gate_cache"]
        assert trial.candidate.memory.updates == cache["updates"] == (index + 1) * nmove
        for key, source_key in (
            ("alpha_per_ms", "alpha"),
            ("beta_per_ms", "beta"),
            ("class_open", "gjopen"),
        ):
            np.testing.assert_array_equal(
                getattr(trial.candidate.memory, key), cache["attributes"][source_key]
            )
        exact(trial.current.values, actual["current"])
        exact(trial.voltage.values, actual["voltage"])
        exact(trial.candidate.material.values, actual["final_state"])
        factor = (
            1024
            * np.finfo(np.float64).eps
            * (
                len(binding.material_binding.ion_ids)
                + len(binding.material_binding.membrane_ids)
                + np.prod(binding.voltage_binding.kernel.shape)
                + 32 * (index + 1)
                + 96
            )
        )
        errors, budgets = {}, {}
        groups = (
            (
                "material",
                trial.material.candidate.material.values,
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
        for group, values, targets, gross, lesser in groups:
            for key, value in values._asdict().items():
                budget = factor * np.asarray(gross[key]) + (
                    MATERIAL_FLOORS[key] if group == "material" else 1e-30
                )
                errors[group + "/" + key] = float(
                    np.max(abs(value - np.asarray(targets[key])) / budget, initial=0)
                )
                errors["reference/" + group + "/" + key] = float(
                    np.max(
                        abs(np.asarray(lesser[key]) - np.asarray(targets[key])) / budget, initial=0
                    )
                )
                budgets[group + "/" + key] = budget
        for slot, (gate_frame, target_gate, less_gate) in enumerate(
            zip(
                trial.material.gate_updates,
                target["gate_updates"],
                less["gate_updates"],
                strict=True,
            )
        ):
            assert (
                gate_frame.ion_id == target_gate["ion_id"]
                and gate_frame.update_index == target_gate["update_index"]
            )
            for key, wanted in target_gate["values"].items():
                budget = factor * np.asarray(target_gate["gross"][key]) + (
                    1e-40 if key == "voltage_before_nonce_V" else 1e-30
                )
                name = "gate/" + str(slot) + "/" + key
                errors[name] = float(
                    np.max(abs(getattr(gate_frame, key) - np.asarray(wanted)) / budget, initial=0)
                )
                errors["reference/" + name] = float(
                    np.max(
                        abs(np.asarray(less_gate["values"][key]) - np.asarray(wanted)) / budget,
                        initial=0,
                    )
                )
                budgets[name] = budget
        archive(tmp_path, "errors-" + case + "-" + str(index), dict(errors=errors, budgets=budgets))
        comparisons.append(
            dict(
                call_index=index + 1,
                maximum_error_fraction=max(errors.values()),
                reference_resolution_fraction=max(
                    value for key, value in errors.items() if key.startswith("reference/")
                ),
                raw_actual=str(path),
            )
        )
        frame_count += len(trial.material.material.frames)
        gate_count += len(trial.material.gate_updates)
        elapsed = trial.clock["elapsed_end_s"]
        parent = trial.candidate
    maximum = max(*init_errors, *(row["maximum_error_fraction"] for row in comparisons))
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=3,
                frames=frame_count,
                gate_calls=gate_count,
                comparisons=comparisons,
                exact_host_native_correspondence=True,
                fresh_independent_answer_forms=2,
                maximum_error_fraction=maximum,
                physical_gate_or_full_native_parity=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert join.digest(inputs) == original
    assert maximum <= 1 and all(
        row["reference_resolution_fraction"] <= 0.1 for row in comparisons
    ), comparisons


def test_constructor_updates_class_only_and_can_exceed_one(tmp_path):
    inputs = fixtures.fixture()
    inputs["initial"]["junction_voltage_V"] = [0.0] * 9
    inputs["initial_gate_block"] = [1.0] * 9
    inputs["gate_definition"]["minimum"] = 0.3
    inputs["drives"] = inputs["drives"][:1]
    _, actual = isolated(tmp_path, "constructor-class-only", inputs)
    _, _, state = seed(inputs=inputs)
    init = actual["history"][0]["material"]["gate_initialization"]
    np.testing.assert_array_equal(state.memory.class_open, init["actual_class_cache"]["gjopen"])
    np.testing.assert_array_equal(state.material.values.gap_open, init["sim_open_after"])
    assert np.all(state.memory.class_open > 1) and np.all(state.material.values.gap_open < 1)


def test_gate_full_dt_and_block_are_applied_for_every_moving_ion():
    inputs, binding, trial = one("partial_block")
    opening = trial.parent.material.values.gap_open
    for event in trial.material.gate_updates:
        dt = trial.material.material.drive.dt_s * 1e3
        expected = (
            0.5
            * (opening + dt * (event.alpha_per_ms + event.beta_per_ms * binding.minimum))
            / (1 + event.alpha_per_ms * dt + event.beta_per_ms * dt)
        )
        np.testing.assert_array_equal(event.opening_stored, expected)
        opening = event.opening_stored
    assert trial.clock["native_gate_dt_consumed_s"] == 3 * inputs["drives"][0]["material"]["dt_s"]
    assert (
        trial.clock["elapsed_end_s"] - trial.clock["elapsed_start_s"]
        < trial.clock["native_gate_dt_consumed_s"]
    )


def test_ion_count_changes_gate_updates_without_changing_physical_call_dt():
    _, _, one_ion = one("one_moving")
    _, _, all_ions = one("all_moving")
    assert len(one_ion.material.gate_updates) == 1 and len(all_ions.material.gate_updates) == 4
    assert one_ion.clock["dt_s"] == all_ions.clock["dt_s"]
    assert np.any(
        one_ion.candidate.material.values.gap_open != all_ions.candidate.material.values.gap_open
    )


def test_no_moving_ions_retains_cached_gate_state_and_consumes_no_gate_dt():
    _, _, trial = one("no_moving")
    assert not trial.material.gate_updates and trial.clock["native_gate_calls"] == 0
    assert trial.clock["native_gate_dt_consumed_s"] == 0
    assert join.record(trial.parent.memory) == join.record(trial.candidate.memory)
    np.testing.assert_array_equal(
        trial.candidate.material.values.gap_open, trial.parent.material.values.gap_open
    )


def test_native_rates_use_pre_nonce_gap_voltage_and_ignore_temperature_scaling():
    inputs, binding, trial = one("nonce_neutral")
    for event in trial.material.gate_updates:
        np.testing.assert_array_equal(event.voltage_before_nonce_V, np.zeros(9))
    for event, frame in zip(
        trial.material.gate_updates, trial.material.material.frames[3:11:3], strict=True
    ):
        np.testing.assert_array_equal(
            frame.values.junction_voltage_V, event.voltage_before_nonce_V + 1e-25
        )
    changed = copy.deepcopy(inputs)
    changed["drives"][0]["material"]["runtime_temperature_K"] = 330.0
    warmer = advance(changed, binding, trial.parent)
    for a, b in zip(trial.material.gate_updates, warmer.material.gate_updates, strict=True):
        np.testing.assert_array_equal(a.alpha_per_ms, b.alpha_per_ms)
        np.testing.assert_array_equal(a.beta_per_ms, b.beta_per_ms)


def test_gate_state_updates_on_boundary_faces_before_flux_masking():
    _, binding, trial = one()
    mask = binding.material_binding.kernel.boundary
    assert np.any(
        trial.material.gate_updates[0].opening_stored[mask]
        != trial.parent.material.values.gap_open[mask]
    )
    assert np.all(trial.candidate.material.values.junction_flux_mol_m2_s[:, mask] == 0)


def test_active_branch_does_not_remultiply_default_weights():
    inputs, binding, trial = one("zero_weights")
    changed = copy.deepcopy(inputs)
    changed["ion_definition"]["geometry"]["gap_weights"] = [1.0] * 9
    _, other_binding, parent = seed(inputs=changed)
    other = advance(changed, other_binding, parent)
    assert np.all(binding.material_binding.kernel.gap_weights == 0)
    assert np.any(trial.candidate.material.values.junction_flux_mol_m2_s != 0)
    exact(trial.candidate.material.values, other.candidate.material.values._asdict())


def test_zero_block_is_stored_and_restoration_starts_from_zero():
    inputs, binding, first = one("zero_restore")
    assert np.all(first.candidate.material.values.gap_open == 0)
    next_trial = advance(inputs, binding, first.candidate, 1, first.clock["elapsed_end_s"])
    np.testing.assert_array_equal(next_trial.material.gate_updates[0].opening_before, np.zeros(9))
    assert np.all(next_trial.material.gate_updates[0].opening_stored > 0)


def test_explicit_cached_initialization_voltage_is_not_recomputed_from_vm():
    _, binding, initialized = seed("cached_init")
    vm = initialized.material.values.voltage_V
    k = binding.material_binding.kernel
    assert np.any(initialized.initialization.cached_voltage_V != vm[k.partner] - vm)
    np.testing.assert_array_equal(
        initialized.initialization.cached_voltage_V, initialized.material.values.junction_voltage_V
    )


def test_source_finite_gate_above_one_is_retained_without_clipping():
    _, _, trial = one("over_one")
    assert np.any(trial.candidate.material.values.gap_open > 1)


def test_voltage_feedback_changes_next_gate_rates_and_keeps_other_caches_stale():
    inputs, binding, first = one()
    second = advance(inputs, binding, first.candidate, 1, first.clock["elapsed_end_s"])
    previous_vm = first.candidate.material.values.voltage_V
    k = binding.material_binding.kernel
    expected = previous_vm[k.partner] - previous_vm
    np.testing.assert_array_equal(second.material.gate_updates[0].voltage_before_nonce_V, expected)
    np.testing.assert_array_equal(
        first.candidate.material.values.junction_voltage_V,
        first.material.candidate.material.values.junction_voltage_V,
    )
    assert np.any(
        second.material.gate_updates[0].alpha_per_ms != first.material.gate_updates[0].alpha_per_ms
    )


def test_ordered_slots_and_gate_cache_survive_explicit_resume():
    inputs, binding, first = one("reversed")
    assert [frame.ion_id for frame in first.material.gate_updates] == ["Cl", "K", "Na"]
    resumed = advance(inputs, binding, first.candidate, 1, first.clock["elapsed_end_s"])
    assert [frame.update_index for frame in resumed.material.gate_updates] == [4, 5, 6]
    np.testing.assert_array_equal(
        resumed.material.gate_updates[0].opening_before, first.candidate.material.values.gap_open
    )


def test_repeatability_immutability_and_source_parent_preservation():
    inputs, binding, first = one()
    before = join.digest(first.parent)
    again = advance(inputs, binding, first.parent)
    assert first.identity == again.identity and join.digest(first.parent) == before
    for value in (
        *first.candidate.material.values,
        *first.candidate.memory[:4],
        first.material.gate_updates[0].opening_stored,
    ):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)


@pytest.mark.parametrize("defect", ("threshold", "minimum", "shape", "mutable", "dtype", "counter"))
def test_invalid_gate_metadata_refuses_before_material_work(defect, monkeypatch):
    inputs, binding, parent = seed()
    if defect in ("threshold", "minimum"):
        definition = copy.deepcopy(inputs["gate_definition"])
        definition[defect if defect == "minimum" else "threshold_mV"] = (
            2.0 if defect == "minimum" else -1.0
        )
        with pytest.raises(ValueError):
            gated.bind(binding.material_binding, binding.voltage_binding, definition)
        return
    memory = parent.memory
    if defect == "shape":
        memory = memory._replace(alpha_per_ms=join.freeze(memory.alpha_per_ms[:1]))
    elif defect == "mutable":
        memory = memory._replace(alpha_per_ms=memory.alpha_per_ms.copy())
    elif defect == "dtype":
        memory = memory._replace(alpha_per_ms=join.freeze(memory.alpha_per_ms.astype(np.float32)))
    else:
        memory = memory._replace(updates=1)
    parent = gated._state(binding, parent.material, memory, parent.initialization)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid gate cache reached material")

    monkeypatch.setattr(gated, "_material_step", forbidden)
    with pytest.raises(gated.GatedJoinRejected):
        advance(inputs, binding, parent)
    assert not calls


@pytest.mark.parametrize("mode", ("init_overflow", "gate_overflow", "voltage_zero_sigma"))
def test_actual_gate_and_coupled_nonfinite_trials_are_losslessly_preserved(tmp_path, mode):
    inputs = fixtures.fixture()
    inputs["drives"] = inputs["drives"][:1]
    if mode == "init_overflow":
        inputs["initial"]["junction_voltage_V"] = [1e4] * 9
    elif mode == "gate_overflow":
        inputs["initial"]["voltage_V"] = [1000.0 + 100 * j for j in range(9)]
    else:
        inputs["voltage_definition"]["ions"]["free_diffusion_m2_s"] = [0.0] * 4
    _, actual = isolated(tmp_path, mode, inputs)
    ib = join.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    binding = gated.bind(ib, vb, inputs["gate_definition"])
    original = join.state(ib, inputs["initial"])
    before = join.digest(original)
    if mode == "init_overflow":
        with pytest.raises(gated.GatedJoinRejected) as caught:
            gated.initialize(binding, original, initial_block=inputs["initial_gate_block"])
        error = caught.value
        source = actual["history"][0]["material"]["gate_initialization"]
        assert error.initialization is not None and error.parent is original
        np.testing.assert_array_equal(
            error.initialization.memory.beta_per_ms, source["actual_class_cache"]["beta"]
        )
        np.testing.assert_array_equal(
            error.initialization.memory.class_open, source["actual_class_cache"]["gjopen"]
        )
        raw = error.initialization
    else:
        initialized = gated.initialize(
            binding, original, initial_block=inputs["initial_gate_block"]
        )
        with pytest.raises(gated.GatedJoinRejected) as caught:
            advance(inputs, binding, initialized)
        error = caught.value
        assert error.parent is initialized and error.material is not None
        if mode == "gate_overflow":
            assert actual["status"] == "source_refused" and error.voltage_trial is None
            exact(
                error.material.candidate.material.values,
                actual["history"][0]["material"]["final_state"],
            )
            for frame, source in zip(
                error.material.gate_updates,
                actual["history"][0]["material"]["gate_updates"],
                strict=True,
            ):
                exact_gate(frame, source)
        else:
            assert actual["status"] == "source_completed" and error.voltage_trial is not None
            exact(error.voltage_trial.values, actual["history"][0]["voltage"])
        raw = dict(material=error.material, current=error.readout, voltage=error.voltage_trial)
    archived = archive(tmp_path, "actual-" + mode, raw)
    assert (
        join.digest(archive_read(archived)) == join.digest(raw) and join.digest(original) == before
    )

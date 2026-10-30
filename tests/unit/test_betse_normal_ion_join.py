"""Scoped carried native ion/material states, independent equations and failures."""

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

from cells.processes import betse_normal_ion_join as join
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ion_join_fixtures as fixtures
from validation.betse import betse_normal_ion_join_native as native

FLOORS = dict(
    cell_mol_m3=1e-25,
    membrane_mol_m3=1e-25,
    bath_mol_m3=1e-25,
    voltage_V=1e-40,
    membrane_flux_mol_m2_s=1e-30,
    junction_flux_mol_m2_s=1e-30,
    junction_voltage_V=1e-40,
    junction_field_V_m=1e-28,
    junction_field_xy_V_m=1e-28,
    gap_open=1e-30,
)


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-ion-join"


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
        "validation.betse.betse_normal_ion_join_native",
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
    if cpu := os.environ.get("CELLS_ION_JOIN_CPU"):
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
            "validation.betse.betse_normal_ion_join_reference",
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
        if cpu := os.environ.get("CELLS_ION_JOIN_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer["history"])
    return answers


def seed(case="closed"):
    inputs = fixtures.fixture(case)
    binding = join.bind(inputs["definition"])
    return inputs, binding, join.state(binding, inputs["initial"])


def one(case="closed"):
    inputs, binding, parent = seed(case)
    return inputs, binding, join.step(binding, parent, join.drive(binding, **inputs["steps"][0]))


def exact(actual, wanted):
    for key, value in actual._asdict().items():
        assert value.dtype == wanted[key].dtype, key
        np.testing.assert_array_equal(value, wanted[key], err_msg=key)


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    if cpu := os.environ.get("CELLS_ION_JOIN_CPU"):
        assert affinity == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    coordinated_shared_modules = {
        "cells.core.grid",
        "cells.core.runner",
        "cells.core.specs",
        "cells.core.batch",
        "cells.ensemble.ionic",
        "cells.core.surface_cotransport_water_spec",
        "cells.models.surface_energy",
        "cells.models.surface_energy_water",
    }
    assert not coordinated_shared_modules.intersection(sys.modules)
    (folder / "runtime.json").write_text(
        json.dumps(
            dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=join.SOURCE_REVISION,
                source_scope=join.LAW_ID,
                full_native_solver=False,
                gpu=False,
                coordinated_shared_edit_modules_loaded=[],
                loaded_cells_modules=sorted(
                    name for name in sys.modules if name == "cells" or name.startswith("cells.")
                ),
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_carried_native_full_stage_arrays_and_independent_equations(tmp_path, case):
    inputs, binding, parent = seed(case)
    original = join.digest(inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 4
    standard, tight = independent(folder)
    comparisons = []
    frame_count = 0
    for index, (forcing, native_call, less_call, target_call) in enumerate(
        zip(inputs["steps"], captured["history"], standard, tight, strict=True), 1
    ):
        before = join.digest(parent)
        drive = join.drive(binding, **forcing)
        trial = join.step(binding, parent, drive)
        path = archive(
            tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial)
        )
        assert trial.parent is parent and join.digest(parent) == before
        assert trial.candidate.step_index == index
        assert len(trial.frames) == len(native_call["frames"]) == len(target_call["frames"])
        factor = (
            128
            * np.finfo(np.float64).eps
            * (len(binding.ion_ids) + len(binding.membrane_ids) + 4 * index + 32)
        )
        errors = []
        budgets = []
        for frame, actual, less, target in zip(
            trial.frames,
            native_call["frames"],
            less_call["frames"],
            target_call["frames"],
            strict=True,
        ):
            assert (
                (frame.stage, frame.ion_id)
                == (actual["stage"], actual["ion_id"])
                == (target["stage"], target["ion_id"])
            )
            exact(frame.values, actual["values"])
            row, unit_budgets = {}, {}
            for key, value in frame.values._asdict().items():
                wanted = np.asarray(target["values"][key])
                budget = factor * np.asarray(target["gross"][key]) + FLOORS[key]
                row[key] = float(np.max(abs(value - wanted) / budget, initial=0))
                row["reference/" + key] = float(
                    np.max(abs(np.asarray(less["values"][key]) - wanted) / budget, initial=0)
                )
                unit_budgets[key] = budget
            errors.append(row)
            budgets.append(unit_budgets)
        exact(trial.candidate.values, native_call["final_state"])
        archive(
            tmp_path, "comparison-" + case + "-" + str(index), dict(errors=errors, budgets=budgets)
        )
        maximum = max(value for row in errors for value in row.values())
        resolution = max(
            value for row in errors for key, value in row.items() if key.startswith("reference/")
        )
        comparisons.append(
            dict(
                step_index=index,
                frames=len(trial.frames),
                maximum_error_fraction=maximum,
                reference_resolution_fraction=resolution,
                raw_actual=str(path),
            )
        )
        frame_count += len(trial.frames)
        parent = trial.candidate
    maximum = max(row["maximum_error_fraction"] for row in comparisons)
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=4,
                frames=frame_count,
                comparisons=comparisons,
                exact_host_native_correspondence=True,
                fresh_independent_answer_forms=2,
                maximum_error_fraction=maximum,
                full_native_solver_or_conservative_parity=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert join.digest(inputs) == original
    assert maximum <= 1 and all(
        row["reference_resolution_fraction"] <= 0.1 for row in comparisons
    ), comparisons


def test_flux_reads_original_membrane_then_refreshes_from_original_bulk():
    inputs, binding, result = one("membrane_lag")
    first = binding.kernel.moving[0]
    np.testing.assert_array_equal(
        result.frames[2].values.membrane_mol_m3[first], inputs["initial"]["membrane_mol_m3"][first]
    )
    np.testing.assert_array_equal(
        result.frames[4].values.membrane_mol_m3[first],
        np.asarray(inputs["initial"]["cell_mol_m3"])[first, binding.kernel.owner],
    )
    repaired = copy.deepcopy(inputs["initial"])
    repaired["membrane_mol_m3"] = np.asarray(repaired["cell_mol_m3"])[:, binding.kernel.owner]
    altered = join.step(binding, join.state(binding, repaired), result.drive)
    assert np.any(
        result.candidate.values.membrane_flux_mol_m2_s
        != altered.candidate.values.membrane_flux_mol_m2_s
    )


def test_carried_stale_membrane_is_not_repaired_to_post_gap_bulk():
    inputs, binding, first = one("membrane_lag")
    forcing = join.drive(binding, **inputs["steps"][1])
    literal = join.step(binding, first.candidate, forcing)
    values = first.candidate.values._asdict()
    values["membrane_mol_m3"] = first.candidate.values.cell_mol_m3[:, binding.kernel.owner]
    altered = join.step(binding, join.state(binding, values, step_index=1), forcing)
    assert np.any(first.diagnostics["final_membrane_bulk_difference_mol_m3"] != 0)
    assert np.any(
        literal.candidate.values.membrane_flux_mol_m2_s
        != altered.candidate.values.membrane_flux_mol_m2_s
    )


def test_nonce_mutates_each_ion_voltage_after_gap_field_is_constructed():
    _, _, result = one("zero_voltage_neutral")
    voltage = np.zeros(9)
    for i in range(3):
        voltage += join.NONCE
        membrane, gap = result.frames[2 + 3 * i : 4 + 3 * i]
        np.testing.assert_array_equal(membrane.values.voltage_V, voltage)
        np.testing.assert_array_equal(gap.values.junction_voltage_V, np.full(9, join.NONCE))
        np.testing.assert_array_equal(gap.values.junction_field_V_m, np.zeros(9))
    assert result.diagnostics["source_voltage_nonce_delta_V"].any()


def test_moving_ion_order_is_an_explicit_observed_sequence():
    _, binding, result = one("moving_reversed")
    assert result.diagnostics["moving_ids"] == ("Cl", "K", "Na")
    expected = [
        (stage, binding.ion_ids[i])
        for i in binding.kernel.moving
        for stage in ("membrane_flux", "junction_flux", "refresh_at_mem")
    ]
    assert [(f.stage, f.ion_id) for f in result.frames[2:11]] == expected


def test_open_cluster_changes_membrane_boundary_but_never_gap_boundary():
    _, binding, closed = one()
    _, _, opened = one("open")
    mask = binding.kernel.boundary
    assert np.all(closed.candidate.values.membrane_flux_mol_m2_s[:, mask] == 0)
    assert np.any(opened.candidate.values.membrane_flux_mol_m2_s[:, mask] != 0)
    assert np.all(closed.candidate.values.junction_flux_mol_m2_s[:, mask] == 0)
    assert np.all(opened.candidate.values.junction_flux_mol_m2_s[:, mask] == 0)


def test_nonmoving_species_are_not_committed_and_old_fluxes_are_reset():
    _, _, result = one()
    for key in ("cell_mol_m3", "membrane_mol_m3", "bath_mol_m3"):
        np.testing.assert_array_equal(
            getattr(result.parent.values, key)[3], getattr(result.candidate.values, key)[3]
        )
    for key in ("membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
        assert np.all(getattr(result.frames[1].values, key) == 0)
        assert np.all(getattr(result.candidate.values, key)[3] == 0)


def test_no_moving_ions_retains_other_cached_readouts_without_a_refresh():
    _, _, result = one("stationary")
    assert [f.stage for f in result.frames] == ["initial", "reset_flux"]
    for key in join.Values._fields:
        if "flux" not in key:
            np.testing.assert_array_equal(
                getattr(result.parent.values, key), getattr(result.candidate.values, key)
            )


def test_negative_bulk_is_clipped_with_added_moles_and_stale_membrane_retained():
    _, _, result = one("clipping")
    assert np.any(result.diagnostics["clipping_added_mol"] > 0)
    assert np.all(result.candidate.values.cell_mol_m3 >= 0)
    assert np.any(result.diagnostics["final_membrane_bulk_difference_mol_m3"] != 0)
    assert not result.diagnostics["material_conservation_inferred"]


def test_signed_bath_is_retained_and_mixing_is_the_source_unweighted_mean():
    _, binding, result = one("bath_depletion")
    assert result.diagnostics["negative_bath_retained"]
    for i in binding.kernel.moving:
        expected = np.mean(
            result.parent.values.bath_mol_m3[i]
            - result.candidate.values.membrane_flux_mol_m2_s[i]
            * (binding.kernel.area_m2 / binding.kernel.bath_volume_m3)
            * result.drive.dt_s
        )
        assert result.candidate.values.bath_mol_m3[i] == expected
    assert np.any(result.diagnostics["total_cell_bath_change_mol"] != 0)


def test_runtime_membrane_and_configured_gap_temperatures_are_distinct_inputs():
    inputs, binding, first = one()
    hot = join.step(
        binding,
        first.parent,
        join.drive(binding, **(inputs["steps"][0] | dict(runtime_temperature_K=330.0))),
    )
    assert np.any(
        first.candidate.values.membrane_flux_mol_m2_s != hot.candidate.values.membrane_flux_mol_m2_s
    )
    np.testing.assert_array_equal(
        first.candidate.values.junction_flux_mol_m2_s, hot.candidate.values.junction_flux_mol_m2_s
    )
    changed = copy.deepcopy(inputs)
    changed["definition"]["parameters"]["configured_temperature_K"] = 330.0
    another = join.bind(changed["definition"])
    gap_hot = join.step(
        another, join.state(another, changed["initial"]), join.drive(another, **changed["steps"][0])
    )
    np.testing.assert_array_equal(
        first.candidate.values.membrane_flux_mol_m2_s,
        gap_hot.candidate.values.membrane_flux_mol_m2_s,
    )
    assert np.any(
        first.candidate.values.junction_flux_mol_m2_s
        != gap_hot.candidate.values.junction_flux_mol_m2_s
    )


def test_permutation_retains_cell_outputs_and_tracks_all_face_readouts():
    _, _, original = one()
    _, _, permuted = one("permuted")
    for key, value in original.candidate.values._asdict().items():
        other = getattr(permuted.candidate.values, key)
        expected = (
            value
            if key in ("cell_mol_m3", "bath_mol_m3")
            else value[:, ::-1]
            if key in ("membrane_mol_m3", "membrane_flux_mol_m2_s", "junction_flux_mol_m2_s")
            else value[::-1]
        )
        np.testing.assert_allclose(other, expected, rtol=3e-13, atol=1e-25)


def test_explicit_material_ledgers_preserve_clipping_and_source_bath_residual():
    _, binding, result = one("clipping")
    d = result.diagnostics
    scale = (
        np.sum(abs(result.candidate.values.cell_mol_m3) * binding.kernel.cell_volume_m3, axis=1)
        + abs(d["membrane_transfer_mol"])
        + abs(d["junction_transfer_mol"])
        + d["clipping_added_mol"]
    )
    assert np.all(abs(d["cell_accounting_residual_mol"]) <= 2e-12 * scale + 1e-30)
    bath_gross = (
        abs(result.parent.values.bath_mol_m3) + abs(result.candidate.values.bath_mol_m3)
    ) * binding.kernel.bath_volume_m3
    budget = (
        32
        * np.finfo(np.float64).eps
        * (bath_gross + abs(d["membrane_transfer_mol"]) / len(binding.membrane_ids))
        + 1e-30
    )
    assert np.all(abs(d["source_mixed_bath_residual_mol"]) <= budget)


def test_trial_arrays_are_immutable_and_readout_is_repeatable():
    inputs, binding, first = one()
    before = join.digest(first.parent)
    second = join.step(binding, first.parent, join.drive(binding, **inputs["steps"][0]))
    assert first.identity == second.identity and join.digest(first.parent) == before
    for value in (*first.parent.values, *first.candidate.values, *first.frames[2].values):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)


@pytest.mark.parametrize(
    "defect",
    (
        "ecm",
        "voltage_gate",
        "owner",
        "partner",
        "boundary",
        "duplicate_moving",
        "missing_initial",
        "bad_drive",
    ),
)
def test_incomplete_or_extended_scope_refuses_before_execution(defect):
    inputs = fixtures.fixture()
    if defect == "ecm":
        inputs["definition"]["parameters"]["is_ecm"] = True
    elif defect == "voltage_gate":
        inputs["definition"]["parameters"]["v_sensitive_gj"] = True
    elif defect == "owner":
        inputs["definition"]["geometry"]["owner"][0] = 99
    elif defect == "partner":
        inputs["definition"]["geometry"]["partner"][0] = 99
    elif defect == "boundary":
        inputs["definition"]["geometry"]["boundary"] = [0] * 9
    elif defect == "duplicate_moving":
        inputs["definition"]["ions"]["moving_ids"] = ["Na", "Na"]
    if defect in ("missing_initial", "bad_drive"):
        binding = join.bind(inputs["definition"])
        if defect == "missing_initial":
            inputs["initial"].pop("voltage_V")
            with pytest.raises(ValueError):
                join.state(binding, inputs["initial"])
        else:
            with pytest.raises(ValueError):
                join.drive(binding, **(inputs["steps"][0] | dict(dt_s=0)))
    else:
        with pytest.raises(ValueError):
            join.bind(inputs["definition"])


@pytest.mark.parametrize(
    "defect",
    ("state_dtype", "state_mutable", "state_identity", "drive_dtype", "drive_mutable", "binding"),
)
def test_changed_prepared_buffers_refuse_before_flux_arithmetic(defect, monkeypatch):
    inputs, binding, parent = seed()
    drive = join.drive(binding, **inputs["steps"][0])
    if defect == "state_dtype":
        parent = replace(
            parent,
            values=parent.values._replace(cell_mol_m3=parent.values.cell_mol_m3.astype(np.float32)),
        )
    elif defect == "state_mutable":
        parent = replace(
            parent, values=parent.values._replace(cell_mol_m3=parent.values.cell_mol_m3.copy())
        )
    elif defect == "state_identity":
        parent = replace(parent, identity="different")
    elif defect == "drive_dtype":
        drive = drive._replace(junction_block=drive.junction_block.astype(np.float32))
    elif defect == "drive_mutable":
        drive = drive._replace(junction_block=drive.junction_block.copy())
    else:
        binding = replace(
            binding, kernel=binding.kernel._replace(owner_sum=binding.kernel.owner_sum * 0.5)
        )
        binding = replace(binding, identity=join.digest(join.binding_record(binding)))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid input reached flux arithmetic")

    monkeypatch.setattr(join, "_electroflux", forbidden)
    with pytest.raises(join.IonJoinRejected) as caught:
        join.step(binding, parent, drive)
    assert caught.value.trial is None and not calls


@pytest.mark.parametrize("mode", ("nonce_cancel", "overflow", "native_infinity"))
def test_actual_nonfinite_source_and_refused_partial_trials_are_preserved(tmp_path, mode):
    inputs = fixtures.fixture()
    inputs["steps"] = inputs["steps"][:1]
    if mode == "nonce_cancel":
        inputs["initial"]["voltage_V"] = [-1e-25] * 9
    elif mode == "overflow":
        inputs["definition"]["ions"]["membrane_diffusion_m2_s"] = [[1e308] * 9 for _ in range(4)]
    else:
        inputs["definition"]["geometry"]["cell_volume_m3"] = [1e-300] * 3
        inputs["definition"]["parameters"]["junction_surface_fraction"] = 0.0
        inputs["steps"][0]["dt_s"] = 1e30
    _, actual = isolated(tmp_path, mode, inputs)
    binding = join.bind(inputs["definition"])
    parent = join.state(binding, inputs["initial"])
    before = join.digest(parent)
    forcing = join.drive(binding, **inputs["steps"][0])
    with pytest.raises(join.IonJoinRejected) as caught:
        join.step(binding, parent, forcing)
    error = caught.value
    assert error.parent is parent and error.drive is forcing and join.digest(parent) == before
    assert error.stage == "ion_trial" and error.trial is not None
    path = archive(tmp_path, "actual-" + mode, dict(binding=binding, refused=error.trial))
    assert join.digest(archive_read(path)["refused"]) == join.digest(error.trial)
    exact(error.trial.candidate.values, actual["final_state"])
    assert not error.trial.diagnostics["finite"]
    if mode == "native_infinity":
        assert (
            actual["status"] == "source_completed"
            and np.isinf(actual["final_state"]["cell_mol_m3"]).any()
        )
    else:
        assert (
            actual["status"] == "source_refused" and actual["failure"]["type"] == "NativeUnstable"
        )

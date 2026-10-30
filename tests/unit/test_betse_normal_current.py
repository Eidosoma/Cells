"""Literal native current prefix and independent post-flux snapshot equations."""

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

from cells.processes import betse_normal_current as current
from tests.unit.test_betse_fast_solver import archive_read, data
from validation.betse import betse_normal_current_fixtures as fixtures
from validation.betse import betse_normal_current_native as native


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-current"


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, data(payload))


def digest(value):
    return current._digest(data(value))


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "inputs.json"
    path.write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_current_native",
        "--inputs",
        str(path),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    result = archive_read(folder / "native")
    assert (
        result["production_imports_denied"]
        and not result["loaded_production_modules"]
        and result["RNG_unchanged"]
    )
    if cpu := os.environ.get("CELLS_NORMAL_CPU"):
        assert result["runtime"]["measured_cpu_affinity"] == [int(cpu)]
    return folder, result


def independent(folder):
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_current_reference",
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
        if cpu := os.environ.get("CELLS_NORMAL_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer["snapshots"])
    return answers


def native_values(frame):
    state = frame["state"]
    other = frame["intermediates"]
    return dict(
        charge_density_C_m3=state["rho_cells"],
        membrane_current_A_m2=state["Jmem"],
        junction_current_A_m2=state["Jgj"],
        raw_normal_current_A_m2=other["raw_normal_current_A_m2"],
        average_normal_current_A_m2=other["average_normal_current_A_m2"],
        normal_current_A_m2=state["Jn"],
        inward_membrane_current_A=state["I_mem"],
        cell_current_xy_A_m2=np.column_stack((state["J_cell_x"], state["J_cell_y"])),
        projected_cell_current_A_m2=state["Jc"],
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    cpu = os.environ.get("CELLS_NORMAL_CPU")
    if cpu is not None:
        assert affinity == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(
        json.dumps(
            dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=current.SOURCE_REVISION,
                source_prefix_only=True,
                field_or_voltage_solve=False,
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_prefix_exact_and_independent_snapshot_equations(tmp_path, case):
    inputs = fixtures.fixture(case)
    before = digest(inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    standard, tight = independent(folder)
    binding = current.bind(inputs["definition"])
    reports = []
    errors = []
    budgets = []
    factor = 32 * np.finfo(np.float64).eps * (len(binding.ion_ids) + len(binding.membrane_ids) + 16)
    for snapshot, frame, less, target in zip(
        inputs["snapshots"], captured["history"], standard, tight, strict=True
    ):
        source = current.inputs(binding, **snapshot)
        parent = digest(source)
        report = current.evaluate(binding, source)
        reports.append(report)
        archive(
            tmp_path,
            "snapshot-" + case + "-" + str(len(reports) - 1),
            dict(inputs=snapshot, binding=binding, report=report),
        )
        assert report.source is source and digest(source) == parent
        native_actual = native_values(frame)
        row = {}
        unit_budgets = {}
        for key, value in report.values._asdict().items():
            assert value.dtype == native_actual[key].dtype, key
            np.testing.assert_array_equal(value, native_actual[key], err_msg=key)
            wanted = np.asarray(target["values"][key])
            gross = np.asarray(target["gross"][key])
            budget = factor * gross + 1e-30
            row[key] = float(np.max(abs(value - wanted) / budget, initial=0))
            row["reference/" + key] = float(
                np.max(abs(np.asarray(less["values"][key]) - wanted) / budget, initial=0)
            )
            unit_budgets[key] = budget
        np.testing.assert_array_equal(
            binding.kernel.membrane_weight, frame["state"]["smooth_weight_mem"]
        )
        np.testing.assert_array_equal(
            binding.kernel.other_weight, frame["state"]["smooth_weight_o"]
        )
        assert captured["source_parameters"]["smooth_cells"] == binding.kernel.source_smooth_cells
        assert max(value for key, value in row.items() if key.startswith("reference/")) <= 0.1
        errors.append(row)
        budgets.append(unit_budgets)
    path = archive(
        tmp_path,
        "actual-" + case,
        dict(inputs=inputs, binding=binding, reports=reports, errors=errors, budgets=budgets),
    )
    maximum = max(value for row in errors for value in row.values())
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                snapshots=3,
                exact_host_native_correspondence=True,
                fresh_independent_answer_forms=2,
                maximum_error_fraction=maximum,
                raw_actual=str(path),
                trajectory_or_field_parity=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert digest(inputs) == before and maximum <= 1, errors


def test_membrane_and_junction_current_signs_are_distinct():
    inputs = fixtures.fixture("inward_sign")
    binding = current.bind(inputs["definition"])
    frame = inputs["snapshots"][0]
    one = current.evaluate(binding, current.inputs(binding, **frame))
    assert np.all(one.values.membrane_current_A_m2 < 0) and np.all(
        one.values.inward_membrane_current_A > 0
    )
    opposite = copy.deepcopy(frame)
    opposite["junction_flux_mol_m2_s"] = opposite["membrane_flux_mol_m2_s"]
    opposite["membrane_flux_mol_m2_s"] = [[0.0] * 9] * 4
    two = current.evaluate(binding, current.inputs(binding, **opposite))
    assert np.all(two.values.junction_current_A_m2 > 0) and np.all(
        two.values.inward_membrane_current_A < 0
    )


def test_area_mismatch_residual_is_retained_without_repair():
    exact = fixtures.fixture()
    changed = fixtures.fixture("area_mismatch")
    a = current.bind(exact["definition"])
    b = current.bind(changed["definition"])
    first = current.evaluate(a, current.inputs(a, **exact["snapshots"][0]))
    second = current.evaluate(b, current.inputs(b, **changed["snapshots"][0]))
    scale = np.abs(first.diagnostics["surface_current_before_A"])
    assert np.all(abs(first.diagnostics["smoothing_current_difference_A"]) <= 1e-30 + 3e-13 * scale)
    assert np.any(abs(second.diagnostics["smoothing_current_difference_A"]) > 1e-30 + 3e-13 * scale)
    assert not second.diagnostics["physical_charge_conservation_inferred"]


def test_zero_sharpness_preserves_native_parameter_failure(tmp_path):
    inputs = fixtures.fixture()
    inputs["definition"]["parameters"]["sharpness_cell"] = 0.0
    _, actual = isolated(tmp_path, "zero-sharpness", inputs)
    with pytest.raises(ValueError):
        current.bind(inputs["definition"])
    assert actual["status"] == "source_refused" and actual["failure"]["type"] == "ZeroDivisionError"
    assert not actual["history"]


def test_actual_nonfinite_current_trial_is_retained_with_original_source(tmp_path):
    inputs = fixtures.fixture()
    inputs["definition"]["parameters"]["F_C_mol"] = 1e308
    frame = inputs["snapshots"][0]
    frame["membrane_flux_mol_m2_s"] = [[1e308] * 9] * 4
    inputs["snapshots"] = [frame]
    _, actual = isolated(tmp_path, "overflow", inputs)
    binding = current.bind(inputs["definition"])
    source = current.inputs(binding, **frame)
    before = digest(source)
    with pytest.raises(current.NormalCurrentRejected) as caught:
        current.evaluate(binding, source)
    error = caught.value
    path = archive(tmp_path, "actual-overflow", dict(source=source, trial=error.trial))
    assert digest(archive_read(path)["trial"]) == digest(error.trial)
    assert (
        actual["status"] == "source_completed"
        and not np.isfinite(actual["final_state"]["Jn"]).all()
    )
    assert error.source is source and error.stage == "current_trial" and digest(source) == before
    assert not error.trial.diagnostics["finite"]


@pytest.mark.parametrize(
    "defect",
    (
        "concentration_shape",
        "flux_shape",
        "negative_concentration",
        "nonfinite_extra",
        "dtype",
        "mutable",
    ),
)
def test_invalid_source_buffers_refuse_without_current_arithmetic(defect, monkeypatch):
    spec = fixtures.fixture()
    binding = current.bind(spec["definition"])
    frame = spec["snapshots"][0]
    source = current.inputs(binding, **frame)
    if defect in ("dtype", "mutable"):
        source = source._replace(
            **(
                {"cell_mol_m3": source.cell_mol_m3.astype(np.float32)}
                if defect == "dtype"
                else {"extra_current_A_m2": np.array(source.extra_current_A_m2)}
            )
        )
    else:
        frame = copy.deepcopy(frame)
        if defect == "concentration_shape":
            frame["cell_mol_m3"] = [row[:-1] for row in frame["cell_mol_m3"]]
        elif defect == "flux_shape":
            frame["membrane_flux_mol_m2_s"] = [row[:-1] for row in frame["membrane_flux_mol_m2_s"]]
        elif defect == "negative_concentration":
            frame["cell_mol_m3"][0][0] = -1.0
        else:
            frame["extra_charge_C_m3"][0] = float("nan")
        with pytest.raises(ValueError):
            current.inputs(binding, **frame)
        return
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid input reached current arithmetic")

    monkeypatch.setattr(current.np, "dot", forbidden)
    with pytest.raises(current.NormalCurrentRejected) as caught:
        current.evaluate(binding, source)
    assert caught.value.trial is None and not calls


@pytest.mark.parametrize("defect", ("weights", "matrix", "owner", "sharpness"))
def test_resealed_binding_changes_refuse_before_current_arithmetic(defect, monkeypatch):
    spec = fixtures.fixture()
    binding = current.bind(spec["definition"])
    source = current.inputs(binding, **spec["snapshots"][0])
    k = binding.kernel
    if defect == "weights":
        binding = replace(binding, kernel=k._replace(other_weight=k.other_weight * 0.5))
    elif defect == "matrix":
        binding = replace(binding, kernel=k._replace(owner_sum=k.owner_sum * 0.5))
    elif defect == "owner":
        binding = replace(binding, kernel=k._replace(owner=np.roll(k.owner, 1)))
    else:
        binding = replace(binding, sharpness_cell=binding.sharpness_cell * 2)
    binding = replace(binding, identity=current._digest(current.binding_record(binding)))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Changed binding reached current arithmetic")

    monkeypatch.setattr(current.np, "dot", forbidden)
    with pytest.raises(current.NormalCurrentRejected) as caught:
        current.evaluate(binding, source)
    assert caught.value.trial is None and not calls


def test_neutral_species_changes_do_not_create_charge_or_current():
    spec = fixtures.fixture("neutral")
    binding = current.bind(spec["definition"])
    a = spec["snapshots"][0]
    b = copy.deepcopy(a)
    for name in ("cell_mol_m3", "membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
        b[name] = [[value * 1e12 for value in row] for row in b[name]]
    one = current.evaluate(binding, current.inputs(binding, **a))
    two = current.evaluate(binding, current.inputs(binding, **b))
    assert (
        current.record(one.values) == current.record(two.values)
        and one.source_identity != two.source_identity
    )


def test_repeated_readouts_are_exact_and_never_change_inputs():
    spec = fixtures.fixture()
    binding = current.bind(spec["definition"])
    source = current.inputs(binding, **spec["snapshots"][0])
    before = digest(source)
    first = current.evaluate(binding, source)
    second = current.evaluate(binding, source)
    assert first.identity == second.identity and digest(source) == before
    for value in (*source, *first.values):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)


def test_face_permutation_preserves_cell_outputs_and_tracks_face_outputs():
    a = fixtures.fixture()
    b = fixtures.fixture("permuted")
    x = current.bind(a["definition"])
    y = current.bind(b["definition"])
    one = current.evaluate(x, current.inputs(x, **a["snapshots"][0])).values
    two = current.evaluate(y, current.inputs(y, **b["snapshots"][0])).values
    for key in one._fields:
        value = getattr(one, key)
        other = getattr(two, key)
        expected = (
            value
            if key in ("charge_density_C_m3", "average_normal_current_A_m2", "cell_current_xy_A_m2")
            else value[::-1]
        )
        np.testing.assert_allclose(other, expected, rtol=3e-13, atol=1e-28)


def test_sharpness_inverse_and_nonconvex_weights_remain_explicit():
    normal = fixtures.fixture()
    wild = fixtures.fixture("sharpness_large")
    a = current.bind(normal["definition"])
    b = current.bind(wild["definition"])
    assert a.kernel.source_smooth_cells == 2.0 and b.kernel.source_smooth_cells == 0.125
    value = current.evaluate(b, current.inputs(b, **wild["snapshots"][0]))
    assert (
        not value.diagnostics["smoothing_weights_convex"]
        and not value.diagnostics["sharpness_in_documented_range"]
    )
    np.testing.assert_allclose(
        b.kernel.membrane_weight + b.kernel.other_weight, 1.0, rtol=0, atol=3e-15
    )

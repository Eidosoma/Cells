"""Scoped normal source boundary/voltage join with all carried states retained."""

import copy
import hashlib
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
from cells.processes import betse_normal_ion_join as join
from cells.processes import betse_normal_voltage as voltage
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import FLOORS as MATERIAL_FLOORS
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_normal_voltage_fixtures as fixtures
from validation.betse import betse_normal_voltage_native as native


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-voltage"


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
        "validation.betse.betse_normal_voltage_native",
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
    if cpu := os.environ.get("CELLS_NORMAL_VOLTAGE_CPU"):
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
            "validation.betse.betse_normal_voltage_reference",
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
        if cpu := os.environ.get("CELLS_NORMAL_VOLTAGE_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer["history"])
    return answers


def seed(case="simple", inputs=None):
    inputs = fixtures.fixture(case) if inputs is None else inputs
    ib = join.bind(inputs["ion_definition"])
    cb = current.bind(inputs["current_definition"])
    vb = voltage.bind(cb, inputs["voltage_definition"])
    return inputs, ib, vb, join.state(ib, inputs["initial"])


def advance(inputs, ib, vb, parent, index=0, elapsed=None):
    forcing = inputs["drives"][index]
    return voltage.advance(
        ib,
        vb,
        parent,
        join.drive(ib, **forcing["material"]),
        boundary_V=forcing["boundary_V"],
        extra_charge_C_m3=forcing["extra_charge_C_m3"],
        extra_current_A_m2=forcing["extra_current_A_m2"],
        elapsed_s=inputs["elapsed_start_s"] if elapsed is None else elapsed,
    )


def one(case="simple"):
    inputs, ib, vb, parent = seed(case)
    return inputs, ib, vb, advance(inputs, ib, vb, parent)


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    if cpu := os.environ.get("CELLS_NORMAL_VOLTAGE_CPU"):
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
                source_revision=voltage.SOURCE_REVISION,
                dependency_adapter="current-prefix/BVP only",
                coordinated_shared_edit_modules_loaded=[],
                environment_HH_Gaussian=False,
                inverse_preparation=False,
                full_native_solver=False,
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_carried_material_current_boundary_and_voltage_correspondence(tmp_path, case):
    inputs, ib, vb, parent = seed(case)
    original = join.digest(inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    standard, tight = independent(folder)
    elapsed = inputs["elapsed_start_s"]
    comparisons = []
    frames = 0
    for index, (actual, less, target) in enumerate(
        zip(captured["history"], standard, tight, strict=True)
    ):
        before = join.digest(parent)
        trial = advance(inputs, ib, vb, parent, index, elapsed)
        path = archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=vb, trial=trial))
        assert trial.parent is parent and join.digest(parent) == before
        assert trial.material.parent is parent and trial.voltage.source_current is trial.current
        material = actual["material"]["history"][0]
        for frame, source in zip(trial.material.frames, material["frames"], strict=True):
            assert (frame.stage, frame.ion_id) == (source["stage"], source["ion_id"])
            exact(frame.values, source["values"])
        exact(trial.current.values, actual["current"])
        exact(trial.voltage.values, actual["voltage"])
        exact(trial.candidate.values, actual["final_state"])
        np.testing.assert_array_equal(trial.voltage.old_voltage_V, actual["old_voltage_V"])
        factor = (
            1024
            * np.finfo(np.float64).eps
            * (
                len(ib.ion_ids)
                + len(ib.membrane_ids)
                + np.prod(vb.kernel.shape)
                + 16 * (index + 1)
                + 64
            )
        )
        rows = {}
        budgets = {}
        groups = (
            (
                "material",
                trial.material.candidate.values,
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
        for group, values, targets, gross, less_values in groups:
            for key, value in values._asdict().items():
                budget = factor * np.asarray(gross[key]) + (
                    MATERIAL_FLOORS[key] if group == "material" else 1e-30
                )
                rows[group + "/" + key] = float(
                    np.max(abs(value - np.asarray(targets[key])) / budget, initial=0)
                )
                rows["reference/" + group + "/" + key] = float(
                    np.max(
                        abs(np.asarray(less_values[key]) - np.asarray(targets[key])) / budget,
                        initial=0,
                    )
                )
                budgets[group + "/" + key] = budget
        archive(tmp_path, "errors-" + case + "-" + str(index), dict(errors=rows, budgets=budgets))
        comparisons.append(
            dict(
                call_index=index + 1,
                maximum_error_fraction=max(rows.values()),
                reference_resolution_fraction=max(
                    value for key, value in rows.items() if key.startswith("reference/")
                ),
                raw_actual=str(path),
            )
        )
        frames += len(trial.material.frames)
        elapsed = trial.clock["elapsed_end_s"]
        parent = trial.candidate
    maximum = max(row["maximum_error_fraction"] for row in comparisons)
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=3,
                frames=frames,
                comparisons=comparisons,
                exact_host_native_correspondence=True,
                fresh_independent_answer_forms=2,
                maximum_error_fraction=maximum,
                HH_Gaussian_inverse_preparation_or_full_native_parity=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert join.digest(inputs) == original
    assert maximum <= 1 and all(
        row["reference_resolution_fraction"] <= 0.1 for row in comparisons
    ), comparisons


def test_boundary_order_retains_top_bottom_corner_overwrites():
    inputs, _, vb, trial = one("boundary_corners")
    b = inputs["drives"][0]["boundary_V"]
    rhs = trial.voltage.values.boundary_rhs_V_m2
    np.testing.assert_array_equal(rhs[0], np.full(4, -b["B"] / vb.kernel.delta_m**2))
    np.testing.assert_array_equal(rhs[-1], np.full(4, -b["T"] / vb.kernel.delta_m**2))
    assert (
        rhs[1, 0] == -b["L"] / vb.kernel.delta_m**2 and rhs[1, -1] == -b["R"] / vb.kernel.delta_m**2
    )


def test_polarized_branch_omits_boundary_subtraction_and_flag_magnitude():
    inputs, ib, vb, first = one("polarized")
    changed = copy.deepcopy(inputs)
    changed["drives"][0]["boundary_V"] = {key: 0.1 for key in ("R", "L", "T", "B")}
    second = advance(changed, ib, vb, first.parent)
    np.testing.assert_array_equal(first.voltage.values.voltage_V, second.voltage.values.voltage_V)
    assert np.any(
        first.voltage.values.boundary_potential_V != second.voltage.values.boundary_potential_V
    )
    _, _, _, flag = one("pol_flag_magnitude")
    np.testing.assert_array_equal(first.voltage.values.voltage_V, flag.voltage.values.voltage_V)
    assert not first.voltage.diagnostics["direct_boundary_subtraction"]


def test_direct_branch_uses_boundary_and_preserves_alias_mapping():
    inputs, _, vb, trial = one("alias_map")
    cb = vb.current_binding
    expected = (1 / vb.kernel.capacitance_F_m2) * trial.voltage.values.surface_charge_C_m2[
        cb.kernel.owner
    ] - trial.voltage.values.boundary_potential_V[vb.kernel.membrane_to_grid]
    np.testing.assert_array_equal(trial.voltage.values.voltage_V, expected)
    assert (
        inputs["voltage_definition"]["grid"]["membrane_to_grid"][0]
        == inputs["voltage_definition"]["grid"]["membrane_to_grid"][1]
    )


def test_conductivity_is_mean_over_all_ions_including_zero_diffusion():
    _, _, vb, trial = one()
    cb, k = vb.current_binding, vb.kernel
    source = trial.current.source.cell_mol_m3
    rows = np.asarray(
        [
            z**2 * cb.kernel.F_C_mol**2 * c * d * 0.1 / (k.R_J_mol_K * k.configured_temperature_K)
            for z, c, d in zip(cb.kernel.valence, source, k.free_diffusion_m2_s, strict=True)
        ]
    )
    np.testing.assert_array_equal(trial.voltage.values.conductivity_S_m, rows.mean(axis=0))
    assert np.all(rows[-1] == 0) and np.any(rows.mean(axis=0) != rows[:-1].mean(axis=0))


def test_cell_voltage_average_is_unweighted_by_membrane_area():
    _, _, vb, trial = one()
    ck = vb.current_binding.kernel
    expected = np.dot(ck.owner_sum, trial.voltage.values.voltage_V) / np.bincount(ck.owner)
    np.testing.assert_array_equal(trial.voltage.values.mean_voltage_V, expected)
    weighted = (
        np.dot(ck.owner_sum, trial.voltage.values.voltage_V * ck.membrane_area_m2) / ck.cell_area_m2
    )
    assert np.any(abs(weighted - expected) > 1e-14)


def test_voltage_derivative_uses_nonce_updated_pre_voltage_state():
    inputs = fixtures.fixture()
    inputs["initial"]["voltage_V"] = [0.0] * 9
    _, ib, vb, parent = seed(inputs=inputs)
    trial = advance(inputs, ib, vb, parent)
    np.testing.assert_array_equal(
        trial.voltage.old_voltage_V, trial.material.candidate.values.voltage_V
    )
    assert np.any(trial.voltage.old_voltage_V != parent.values.voltage_V)
    np.testing.assert_array_equal(
        trial.voltage.values.derivative_V_s,
        (trial.voltage.values.voltage_V - trial.voltage.old_voltage_V) / trial.voltage.dt_s,
    )


def test_current_reads_post_material_bulk_and_voltage_carries_into_next_flux():
    inputs, ib, vb, first = one("membrane_lag")
    np.testing.assert_array_equal(
        first.current.source.cell_mol_m3, first.material.candidate.values.cell_mol_m3
    )
    np.testing.assert_array_equal(
        first.candidate.values.membrane_mol_m3, first.material.candidate.values.membrane_mol_m3
    )
    np.testing.assert_array_equal(
        first.candidate.values.junction_voltage_V,
        first.material.candidate.values.junction_voltage_V,
    )
    carried = advance(inputs, ib, vb, first.candidate, 1, first.clock["elapsed_end_s"])
    old_voltage = advance(inputs, ib, vb, first.material.candidate, 1, first.clock["elapsed_end_s"])
    assert np.any(
        carried.material.candidate.values.membrane_flux_mol_m2_s
        != old_voltage.material.candidate.values.membrane_flux_mol_m2_s
    )


def test_elapsed_clock_is_explicit_and_records_call_duration():
    inputs, _, _, trial = one()
    assert (
        trial.clock["call_index"] == 1
        and trial.clock["elapsed_start_s"] == inputs["elapsed_start_s"]
    )
    assert (
        trial.clock["elapsed_end_s"]
        == inputs["elapsed_start_s"] + inputs["drives"][0]["material"]["dt_s"]
    )
    assert not trial.clock["event_calendar_claim"]


def test_inverse_is_a_supplied_operator_with_no_preparation(monkeypatch):
    inputs = fixtures.fixture()
    cb = current.bind(inputs["current_definition"])

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected inverse preparation")

    monkeypatch.setattr(np.linalg, "inv", forbidden)
    monkeypatch.setattr(np.linalg, "pinv", forbidden)
    vb = voltage.bind(cb, inputs["voltage_definition"])
    np.testing.assert_array_equal(
        vb.kernel.inverse_m2, inputs["voltage_definition"]["grid"]["inverse_m2"]
    )


def test_repeatable_immutable_full_lineage_and_original_parent():
    inputs, ib, vb, first = one()
    before = join.digest(first.parent)
    again = advance(inputs, ib, vb, first.parent)
    assert first.identity == again.identity and join.digest(first.parent) == before
    for value in (*first.candidate.values, *first.voltage.values, first.voltage.old_voltage_V):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)


@pytest.mark.parametrize("mode", ("F", "owner", "temperature"))
def test_cross_component_source_mismatch_refuses_before_material_work(mode, monkeypatch):
    inputs, ib, _, parent = seed()
    altered = copy.deepcopy(inputs)
    if mode == "F":
        altered["current_definition"]["parameters"]["F_C_mol"] += 1
    elif mode == "owner":
        altered["current_definition"]["geometry"]["owner"][0] = 1
    else:
        altered["voltage_definition"]["parameters"]["configured_temperature_K"] += 1
    vb = voltage.bind(current.bind(altered["current_definition"]), altered["voltage_definition"])
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Mismatched source reached material work")

    monkeypatch.setattr(join, "step", forbidden)
    with pytest.raises(voltage.CouplingRejected) as caught:
        advance(inputs, ib, vb, parent)
    assert caught.value.parent is parent and caught.value.material is None and not calls


@pytest.mark.parametrize(
    "defect", ("shape", "map", "radius", "diffusion", "provenance", "extension")
)
def test_incomplete_voltage_definition_refuses(defect):
    inputs = fixtures.fixture()
    raw = inputs["voltage_definition"]
    if defect == "shape":
        raw["grid"]["shape"] = [1, 4]
    elif defect == "map":
        raw["grid"]["membrane_to_grid"][0] = 99
    elif defect == "radius":
        raw["geometry"]["radius_m"][0] = 0
    elif defect == "diffusion":
        raw["ions"]["free_diffusion_m2_s"] = [1e-9]
    elif defect == "provenance":
        raw["grid"]["operator_provenance"] = ""
    else:
        raw["unexpected"] = 1
    with pytest.raises(ValueError):
        voltage.bind(current.bind(inputs["current_definition"]), raw)


@pytest.mark.parametrize("defect", ("operator", "readout", "old_shape", "boundary", "dt"))
def test_changed_voltage_inputs_preserve_raw_sources_and_refuse(defect):
    inputs, _, vb, trial = one()
    readout = trial.current
    kwargs = dict(
        old_voltage_V=trial.voltage.old_voltage_V,
        dt_s=trial.voltage.dt_s,
        boundary_V=inputs["drives"][0]["boundary_V"],
    )
    if defect == "operator":
        vb = replace(vb, kernel=vb.kernel._replace(inverse_m2=vb.kernel.inverse_m2 * 0.5))
        vb = replace(vb, identity=join.digest(voltage.binding_record(vb)))
    elif defect == "readout":
        readout = replace(
            readout,
            values=readout.values._replace(
                normal_current_A_m2=readout.values.normal_current_A_m2 * 0.5
            ),
        )
    elif defect == "old_shape":
        kwargs["old_voltage_V"] = [0.0]
    elif defect == "boundary":
        kwargs["boundary_V"] = dict(R=0.0)
    else:
        kwargs["dt_s"] = 0
    with pytest.raises(voltage.VoltageRejected) as caught:
        voltage.evaluate(vb, readout, **kwargs)
    assert caught.value.trial is None and caught.value.source["current"] is readout


@pytest.mark.parametrize("mode", ("zero_sigma", "infinity", "nan_gate"))
def test_actual_source_nonfinite_voltage_fields_and_coupled_refusal_are_preserved(tmp_path, mode):
    inputs = fixtures.fixture()
    inputs["drives"] = inputs["drives"][:1]
    if mode == "zero_sigma":
        inputs["voltage_definition"]["ions"]["free_diffusion_m2_s"] = [0.0] * 4
    else:
        inputs["voltage_definition"]["geometry"]["diviterm_m"] = [1e308] * 3
        inputs["drives"][0]["extra_charge_C_m3"] = [1e5] * 3
        if mode == "nan_gate":
            inputs["voltage_definition"]["grid"]["inverse_m2"] = [[1e308] * 12 for _ in range(12)]
            inputs["drives"][0]["boundary_V"] = {key: 1.0 for key in ("R", "L", "T", "B")}
    _, actual = isolated(tmp_path, mode, inputs)
    _, ib, vb, parent = seed(inputs=inputs)
    before = join.digest(parent)
    with pytest.raises(voltage.CouplingRejected) as caught:
        advance(inputs, ib, vb, parent)
    error = caught.value
    assert error.parent is parent and join.digest(parent) == before
    assert (
        error.material is not None and error.readout is not None and error.voltage_trial is not None
    )
    path = archive(
        tmp_path,
        "actual-" + mode,
        dict(material=error.material, current=error.readout, voltage=error.voltage_trial),
    )
    restored = archive_read(path)
    assert join.digest(restored["voltage"]) == join.digest(error.voltage_trial)
    exact(error.voltage_trial.values, actual["history"][0]["voltage"])
    assert not error.voltage_trial.diagnostics["finite"]
    assert actual["status"] == ("source_refused" if mode == "nan_gate" else "source_completed")


def test_original_unstable_material_dependency_replay_retains_complete_failure(tmp_path):
    path = Path(fixtures.__file__).with_name("betse_normal_voltage_material_failure.json")
    protocol = json.loads(native.PROTOCOL.read_text())
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == protocol["retained_material_failure"]["inputs_sha256"]
    )
    inputs = json.loads(path.read_text())
    _, actual = isolated(tmp_path, "material-dependency-failure", inputs)
    _, ib, vb, parent = seed(inputs=inputs)
    completed = []
    elapsed = inputs["elapsed_start_s"]
    with pytest.raises(voltage.CouplingRejected) as caught:
        for index in range(len(inputs["drives"])):
            before = join.digest(parent)
            trial = advance(inputs, ib, vb, parent, index, elapsed)
            archive(tmp_path, "material-failure-prefix-" + str(index), trial)
            completed.append(trial)
            parent = trial.candidate
            elapsed = trial.clock["elapsed_end_s"]
    error = caught.value
    assert error.parent is parent and join.digest(parent) == before
    assert error.material is not None and error.readout is None and error.voltage_trial is None
    assert (
        actual["status"] == "source_refused"
        and actual["failure"]["type"] == "MaterialDependencyRefused"
    )
    assert len(completed) == len(actual["history"]) - 1
    for trial, source in zip(completed, actual["history"][:-1], strict=True):
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.values, source["final_state"])
    source = actual["history"][-1]["material"]
    assert source["status"] == "source_refused" and not error.material.diagnostics["finite"]
    exact(error.material.candidate.values, source["final_state"])
    archived = archive(tmp_path, "actual-material-dependency-failure", error.material)
    assert join.digest(archive_read(archived)) == join.digest(error.material)

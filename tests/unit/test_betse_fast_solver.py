"""Source-equation circuit qualification; no conservative-tissue parity claim."""

import copy
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_native_calendar as clocks
from cells.processes import betse_fast_solver as fast
from validation.betse import betse_fast_solver_fixtures as fixtures
from validation.betse import betse_fast_solver_native as native

PROTOCOL = json.loads(native.PROTOCOL.read_text())
HISTORIES = [(case, phase) for case in fixtures.CASES for phase in ("INIT", "SIM")]


def data(value):
    if is_dataclass(value):
        return {field.name: data(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "_asdict"):
        return {key: data(item) for key, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [data(item) for item in value]
    return value


def archive_read(directory):
    path = Path(directory)
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["complete"] is True
    assert set(manifest["files"]) == {"arrays.npz", "data.json"}
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((path / name).read_bytes()).hexdigest() == expected
    used = set()

    def read(node, arrays):
        if not isinstance(node, dict):
            return node
        if "array" in node:
            value = arrays[node["array"]]
            assert value.dtype.str == node["dtype"] and list(value.shape) == node["shape"]
            used.add(node["array"])
            return np.array(value, copy=True)
        if "mapping" in node:
            return {key: read(value, arrays) for key, value in node["mapping"]}
        if "sequence" in node:
            return [read(value, arrays) for value in node["sequence"]]
        if "float64_bits" in node:
            return struct.unpack("<d", bytes.fromhex(node["float64_bits"]))[0]
        raise ValueError("Unknown numerical archive node")

    with np.load(path / "arrays.npz", allow_pickle=False) as arrays:
        result = read(json.loads((path / "data.json").read_text()), arrays)
        assert used == set(arrays.files) and len(arrays.files) == len(used)
    return result


def evidence_root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "fast-solver"


def archive(tmp_path, name, payload):
    path = evidence_root(tmp_path) / name
    return native.write_archive(path, data(payload))


def prepared(inputs):
    calendar = clocks.bind(**inputs["calendar"])
    model = fast.bind(inputs["definition"], calendar)
    packet = fast.drive(model, **inputs["initial_drive"])
    return model, fast.initialise(model, inputs["initial_voltage_V"], packet)


def isolated(tmp_path, name, inputs):
    folder = evidence_root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    input_path = folder / "inputs.json"
    input_path.write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_fast_solver_native",
        "--inputs",
        str(input_path),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    record = archive_read(folder / "native")
    assert record["production_imports_denied"] and not record["loaded_production_modules"]
    return folder, record


def independent(folder, inputs):
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_fast_solver_reference",
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
        assert len(answer["answer"]["endpoints"]) == len(inputs["drives"])
        answers.append(answer["answer"])
    return answers


def digest(value):
    return fast._digest(data(value))


def tolerance(key, expected):
    absolute = (
        1e-9 if "divergence" in key else 3e-14 if ("voltage" in key or "reversal" in key) else 3e-13
    )
    return absolute + PROTOCOL["tolerances"]["relative"] * abs(np.asarray(expected))


def compare(actual, expected, prefix=""):
    errors = {}
    if isinstance(expected, dict):
        for key, value in expected.items():
            errors.update(compare(actual[key], value, prefix + "/" + key))
    else:
        a, b = np.asarray(actual), np.asarray(expected)
        assert a.shape == b.shape, (prefix, a.shape, b.shape)
        if b.dtype.kind == "b":
            assert np.array_equal(a, b), prefix
        else:
            assert np.isfinite(a).all() and np.isfinite(b).all(), prefix
            errors[prefix] = float(np.max(abs(a - b) / tolerance(prefix, b), initial=0))
    return errors


def native_coefficients(state):
    return dict(
        leak_reversal_V=state["E_Leak"],
        leak_conductance_S_m2=state["G_Leak"],
        junction_conductance_S_m2=state["G_gj"],
        init_dynamics_sigma_S_m=state["init_dynamics_sigma"],
        sigma_cell_S_m=state["sigma_cell"],
        membrane_conductivity_S_m2=state["sigma_mem"],
        ion_reversal_V=state["rev_E_dic"],
        ion_mean_mol_m3=state["cbar_dic"],
        cbar_all_mol_m3=state["cbar_all"],
        cbar_sum_mol_m3=state["cbar_sum"],
    )


def native_values(frame):
    state = frame["state"]
    return dict(
        cell_voltage_V=state["vm_ave"],
        membrane_voltage_V=state["vm"],
        old_gap_voltage_V=state["vgj"],
        junction_open=state["gjopen"],
        normal_current_A_m2=state["Jn"],
        cell_current_xy_A_m2=np.column_stack((state["J_cell_x"], state["J_cell_y"])),
        cell_field_xy_V_m=np.column_stack((state["E_cell_x"], state["E_cell_y"])),
        membrane_field_xy_V_m=np.column_stack((state["Emx"], state["Emy"])),
        corrected_divergence_V_m2=frame["corrected_divergence"],
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    cpu = os.environ.get("CELLS_FAST_CPU")
    affinity = sorted(os.sched_getaffinity(0))
    if cpu is not None:
        assert affinity == [int(cpu)]
    root = evidence_root(tmp_path_factory.getbasetemp())
    root.mkdir(parents=True, exist_ok=True)
    phase = os.environ.get("CELLS_FAST_PHASE", "local")
    (root / ("runtime-" + phase + ".json")).write_text(
        json.dumps(
            dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=fast.SOURCE_REVISION,
                actual_solver="Separate NumPy equivalent circuit",
                native_capture="Authenticated isolated source bodies",
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize(
    "case,phase", HISTORIES, ids=[case + "-" + phase for case, phase in HISTORIES]
)
def test_source_and_independent_carried_histories(tmp_path, case, phase):
    inputs = fixtures.fixture(case, phase)
    before = digest(inputs)
    folder, captured = isolated(tmp_path, case + "-" + phase, inputs)
    assert captured["status"] == "source_completed" and captured["RNG_unchanged"]
    standard, tight = independent(folder, inputs)
    model, point = prepared(inputs)
    original_ions = digest(model.definition["ions"])
    rows = []
    receipts = []
    coefficients = {
        key: value
        for key, value in model.coefficients._asdict().items()
        if key not in ("checks", "valid")
    }
    errors = compare(coefficients, tight["coefficients"], "coefficients")
    errors.update(
        compare(
            native_coefficients(captured["initial"]), tight["coefficients"], "native_coefficients"
        )
    )
    errors.update(
        compare(standard["coefficients"], tight["coefficients"], "reference_coefficients")
    )
    for i, packet in enumerate(inputs["drives"]):
        parent = digest(point)
        receipt = fast.advance(
            model, point, None if phase == "INIT" else fast.drive(model, **packet)
        )
        assert digest(point) == parent
        point = receipt.checkpoint
        receipts.append(receipt)
        expected = tight["endpoints"][i]
        values = data(receipt.trial.values)
        values.update(
            event_label_s=receipt.trial.event_label_s,
            start_s=receipt.trial.start_s,
            end_s=receipt.trial.end_s,
        )
        row = compare(values, expected, "actual")
        row.update(
            compare(
                native_values(captured["history"][i]),
                {key: expected[key] for key in native_values(captured["history"][i])},
                "native",
            )
        )
        resolution = compare(standard["endpoints"][i], expected, "reference")
        row.update(resolution)
        rows.append(row)
        assert max(resolution.values(), default=0) <= 0.1
        assert receipt.trial.event_label_s == float(captured["labels_s"][i])
        assert receipt.trial.start_s == i * model.calendar.dt_s
        assert receipt.trial.end_s == (i + 1) * model.calendar.dt_s
        assert not point.cell_voltage_V.flags.writeable
    archive(
        tmp_path,
        "actual-" + case + "-" + phase,
        dict(inputs=inputs, model=model, receipts=receipts, errors=errors, history_errors=rows),
    )
    assert len(captured["event_call_labels_s"]) == (0 if phase == "INIT" else len(receipts))
    assert captured["callbacks"].count("sample") == len(captured["sampled_s"])
    assert digest(inputs) == before and digest(model.definition["ions"]) == original_ions
    assert point.elapsed_s == model.calendar.step_count * model.calendar.dt_s
    all_errors = [*errors.values(), *(value for row in rows for value in row.values())]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=len(receipts),
                fresh_native_capture=True,
                fresh_independent_answer_forms=2,
                maximum_error_fraction=max(all_errors),
                no_RNG_consumption=True,
                physical_tissue_parity=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert max(all_errors) <= 1, (errors, rows)


@pytest.mark.parametrize("case", ("no_ecm", "ecm"))
def test_junction_gate_is_readout_only_in_literal_source(tmp_path, case):
    inputs = fixtures.fixture(case)
    changed = copy.deepcopy(inputs)
    for packet in changed["drives"]:
        packet["junction_block"] = [0.0] * 9
    for packet in inputs["drives"]:
        packet["junction_block"] = [1.0] * 9
    _, one = isolated(tmp_path, case + "-gate-one", inputs)
    _, zero = isolated(tmp_path, case + "-gate-zero", changed)
    for a, b in zip(one["history"], zero["history"], strict=True):
        np.testing.assert_array_equal(a["state"]["vm_ave"], b["state"]["vm_ave"])
        np.testing.assert_array_equal(a["state"]["Jn"], b["state"]["Jn"])
        assert np.any(a["state"]["gjopen"] != b["state"]["gjopen"])


def test_leak_changes_voltage_but_is_absent_from_current_readout(tmp_path):
    inputs = fixtures.fixture()
    inputs["initial_voltage_V"] = [-0.03] * 3
    packet = dict(extra_current_A_m2=[0.0] * 9, junction_block=[1.0] * 9)
    inputs["initial_drive"] = packet
    inputs["drives"] = [packet] * 5
    _, record = isolated(tmp_path, "leak-readout", inputs)
    first = record["history"][0]["state"]
    assert np.any(first["vm_ave"] != np.asarray(inputs["initial_voltage_V"]))
    np.testing.assert_array_equal(first["Jn"], np.zeros(9))
    model, source = prepared(inputs)
    result = fast.advance(model, source, fast.drive(model, **packet))
    np.testing.assert_array_equal(result.trial.values.normal_current_A_m2, np.zeros(9))


def test_live_diffusion_temperature_inputs_do_not_reinitialize_native_conductances(tmp_path):
    baseline = fixtures.fixture()
    changed = copy.deepcopy(baseline)
    for i, packet in enumerate(changed["drives"]):
        packet["permeability_m2_s"] = [
            [value * (3 + i) for value in row]
            for row in baseline["definition"]["ions"]["membrane_diffusion_m2_s"]
        ]
        packet["temperature_K"] = 270.0 + i * 10
    _, original = isolated(tmp_path, "fixed-coefficients-original", baseline)
    _, modified = isolated(tmp_path, "fixed-coefficients-modified", changed)
    for a, b in zip(original["history"], modified["history"], strict=True):
        np.testing.assert_array_equal(a["state"]["vm_ave"], b["state"]["vm_ave"])
        np.testing.assert_array_equal(a["state"]["G_Leak"], b["state"]["G_Leak"])
        np.testing.assert_array_equal(a["state"]["E_Leak"], b["state"]["E_Leak"])
    assert modified["final_state"]["T"] != original["final_state"]["T"]
    assert not np.array_equal(
        modified["final_state"]["Dm_cells"], original["final_state"]["Dm_cells"]
    )


def test_sampling_changes_storage_without_changing_native_evolution(tmp_path):
    first = fixtures.fixture()
    second = copy.deepcopy(first)
    second["calendar"]["sample_stride"] = 2.0
    _, a = isolated(tmp_path, "sampling-first", first)
    _, b = isolated(tmp_path, "sampling-second", second)
    assert len(a["history"]) == len(b["history"]) == 5
    assert a["callbacks"].count("sample") == 4 and b["callbacks"].count("sample") == 2
    for x, y in zip(a["history"], b["history"], strict=True):
        np.testing.assert_array_equal(x["state"]["vm_ave"], y["state"]["vm_ave"])


def test_source_nan_only_gate_and_stricter_finite_guard_preserve_actual_trials(tmp_path):
    inputs = fixtures.fixture()
    inputs["calendar"].update(step_count=1, dt_s=1e4)
    packet = dict(extra_current_A_m2=[1e308] * 9, junction_block=[1.0] * 9)
    inputs["initial_drive"] = packet
    inputs["drives"] = [packet]
    _, actual = isolated(tmp_path, "infinite-source", inputs)
    model, point = prepared(inputs)
    before = digest(point)
    with pytest.raises(fast.FastRejected) as caught:
        fast.advance(model, point, fast.drive(model, **packet))
    trial = caught.value.trial
    path = archive(tmp_path, "actual-infinite-component", dict(source=point, trial=trial))
    restored = archive_read(path)
    assert digest(restored["trial"]) == digest(trial)
    assert actual["status"] == "source_completed"
    assert np.isinf(actual["history"][0]["state"]["vm_ave"]).all()
    assert bool(trial.values.native_voltage_nan_gate) and not bool(trial.values.finite)
    assert np.isinf(trial.values.cell_voltage_V).all() and digest(point) == before


def test_singular_GHK_keeps_native_and_component_coefficient_failures(tmp_path):
    inputs = fixtures.fixture()
    inputs["definition"]["ions"]["membrane_diffusion_m2_s"] = [[0.0] * 9] * 3
    _, actual = isolated(tmp_path, "singular-GHK", inputs)
    with pytest.raises(fast.FastRejected) as caught:
        prepared(inputs)
    archive(
        tmp_path,
        "actual-singular-coefficients",
        dict(source=caught.value.source, coefficients=caught.value.coefficients),
    )
    assert actual["status"] == "source_refused" and np.isnan(actual["initial"]["E_Leak"]).all()
    assert np.isnan(caught.value.coefficients.leak_reversal_V).all()
    assert caught.value.stage == "coefficients" and not caught.value.coefficients.valid


def test_zero_readout_conductivity_is_an_explicit_stricter_component_refusal(tmp_path):
    inputs = fixtures.fixture()
    inputs["definition"]["ions"]["free_diffusion_m2_s"] = [0.0] * 3
    _, actual = isolated(tmp_path, "zero-readout-conductivity", inputs)
    with pytest.raises(fast.FastRejected) as caught:
        prepared(inputs)
    archive(
        tmp_path,
        "actual-zero-conductivity",
        dict(source=caught.value.source, coefficients=caught.value.coefficients),
    )
    assert actual["status"] == "source_completed"
    assert all(np.isfinite(frame["state"]["vm_ave"]).all() for frame in actual["history"])
    assert np.any(~np.isfinite(actual["final_state"]["Emx"]))
    assert not caught.value.coefficients.checks["positive_readout_conductivity"]


def test_monotone_euler_bound_is_diagnostic_without_dt_repair():
    inputs = fixtures.fixture()
    model, point = prepared(inputs)
    initial = fast.advance(model, point, fast.drive(model, **inputs["drives"][0]))
    bound = float(np.min(initial.trial.values.monotone_dt_limit_s))
    inputs["calendar"].update(step_count=1, dt_s=1.5 * bound)
    model, point = prepared(inputs)
    result = fast.advance(model, point, fast.drive(model, **inputs["drives"][0]))
    assert not np.all(result.trial.values.monotone_step)
    assert result.trial.end_s == inputs["calendar"]["dt_s"] and result.trial.values.finite


@pytest.mark.parametrize(
    "defect",
    (
        "owner",
        "empty_cell",
        "normal",
        "environment",
        "concentration",
        "valence",
        "ion",
        "temperature",
    ),
)
def test_incomplete_or_undefined_inputs_refuse_before_coefficients(defect, monkeypatch):
    inputs = fixtures.fixture()
    raw = inputs["definition"]
    if defect == "owner":
        raw["geometry"]["owner"][0] = 99
    elif defect == "empty_cell":
        raw["geometry"]["owner"] = [0] * 9
    elif defect == "normal":
        raw["geometry"]["normal_xy"][0] = [2.0, 0.0]
    elif defect == "environment":
        raw["ions"]["environment_mol_m3"] = [row[:-1] for row in raw["ions"]["environment_mol_m3"]]
    elif defect == "concentration":
        raw["ions"]["cell_mol_m3"][0][0] = 0.0
    elif defect == "valence":
        raw["ions"]["valence"][0] = 0.0
    elif defect == "ion":
        raw["ions"]["ids"][0] = "invented"
    else:
        raw["parameters"]["temperature_K"] = -1.0

    def forbidden(*args):
        raise AssertionError("Invalid input reached coefficient arithmetic")

    monkeypatch.setattr(fast, "prepare_coefficients", forbidden)
    with pytest.raises(ValueError):
        prepared(inputs)


@pytest.mark.parametrize(
    "defect", ("voltage", "membrane", "clock", "drive", "coefficient", "calendar")
)
def test_resealed_context_changes_refuse_before_euler(defect, monkeypatch):
    inputs = fixtures.fixture()
    model, point = prepared(inputs)
    one = fast.advance(model, point, fast.drive(model, **inputs["drives"][0])).checkpoint
    if defect == "voltage":
        one = replace(one, cell_voltage_V=one.cell_voltage_V + 1e-3)
    elif defect == "membrane":
        one = replace(one, membrane_voltage_V=one.membrane_voltage_V.astype(np.float32))
    elif defect == "clock":
        one = replace(one, elapsed_s=0.0)
    elif defect == "drive":
        one = replace(one, drive=one.drive._replace(extra_current_A_m2=np.full(9, np.nan)))
    elif defect == "coefficient":
        model = replace(
            model,
            coefficients=model.coefficients._replace(
                leak_conductance_S_m2=model.coefficients.leak_conductance_S_m2 * 2
            ),
        )
        model = replace(model, identity=fast._digest(fast.model_record(model)))
        one = replace(one, model_identity=model.identity)
    else:
        model = replace(model, calendar=clocks.bind(**(inputs["calendar"] | dict(step_count=0))))
        model = replace(model, identity=fast._digest(fast.model_record(model)))
        one = replace(one, model_identity=model.identity)
    one = fast._seal(one)
    before = digest(one)
    calls = []

    def forbidden(*args):
        calls.append(True)
        raise AssertionError("Stale source reached Euler arithmetic")

    monkeypatch.setattr(fast, "_values", forbidden)
    with pytest.raises(fast.FastRejected) as caught:
        fast.advance(model, one)
    assert caught.value.trial is None and digest(one) == before and not calls


@pytest.mark.parametrize("count", (0, 1))
@pytest.mark.parametrize("phase", ("INIT", "SIM"))
def test_empty_single_and_terminal_original_phase_bounds(tmp_path, count, phase, monkeypatch):
    inputs = fixtures.fixture(phase=phase)
    inputs["calendar"]["step_count"] = count
    inputs["drives"] = inputs["drives"][:count]
    _, actual = isolated(tmp_path, "bounds-" + phase + "-" + str(count), inputs)
    assert actual["status"] == "source_completed" and len(actual["history"]) == count
    model, point = prepared(inputs)
    if count:
        receipt = fast.advance(model, point)
        assert (
            receipt.trial.event_label_s == 0.0
            and receipt.checkpoint.elapsed_s == model.calendar.dt_s
        )
        point = receipt.checkpoint
    before = digest(point)
    calls = []

    def forbidden(*args):
        calls.append(True)
        raise AssertionError("Terminal phase attempted another Euler call")

    monkeypatch.setattr(fast, "_values", forbidden)
    with pytest.raises(fast.FastRejected) as caught:
        fast.advance(model, point)
    assert caught.value.trial is None and digest(point) == before and not calls


def test_INIT_refuses_a_new_event_packet_and_keeps_original_parent():
    inputs = fixtures.fixture(phase="INIT")
    model, point = prepared(inputs)
    before = digest(point)
    with pytest.raises(fast.FastRejected):
        fast.advance(model, point, fast.drive(model, **inputs["drives"][0]))
    assert digest(point) == before


def test_definition_and_trial_buffers_are_immutable_and_detached_from_callers():
    inputs = fixtures.fixture()
    model, point = prepared(inputs)
    definition = digest(model.definition)
    inputs["definition"]["ions"]["cell_mol_m3"][0][0] = 99.0
    assert digest(model.definition) == definition
    result = fast.advance(model, point)
    for value in (
        point.cell_voltage_V,
        model.definition["geometry"]["owner"],
        result.trial.values.cell_voltage_V,
    ):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)

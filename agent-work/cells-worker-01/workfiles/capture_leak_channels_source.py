"""Actual pinned leak ASTs: ion metadata, target assignment and auxiliary clocks."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from abc import ABCMeta, abstractmethod
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.channels import leak_channels_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads((ROOT / "validation/channels/leak_channels_protocol.json").read_text())


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def gates(obj):
    return np.stack((np.asarray(obj.m), np.asarray(obj.h)))


def run_argument(obj, voltage, parameters):
    """Record and forward the actual native calculate-state argument unchanged."""
    original, observed = obj._calculate_state, []

    def record(value):
        observed.append(np.asarray(value).copy())
        return original(value)

    obj._calculate_state = record
    try:
        obj.run(voltage, parameters)
    finally:
        obj._calculate_state = original
    assert len(observed) == 1
    return observed[0]


def auxiliary_recovery(namespace, name, output):
    settings = PROTOCOL["auxiliary_recovery"]
    for trial, initial in enumerate(settings["initial_states"]):
        voltage = settings["voltage_V"][trial]
        summaries, errors = {}, []
        for refinement in settings["native_refinements"]:
            obj = namespace[name]()
            obj.init(
                np.array([voltage]), SimpleNamespace(mem_i=np.arange(1)), SimpleNamespace(dt=0.0)
            )
            obj.m, obj.h = (np.array([v]) for v in initial)
            p, clock = SimpleNamespace(dt=0.0), reference.clamp_clock()
            actual, expected, opened = [np.asarray(initial)], [np.asarray(initial)], [1.0]
            for left, right in zip(clock, clock[1:], strict=False):
                p.dt = (right - left) / refinement
                for _ in range(refinement):
                    obj.run(np.array([voltage]), p)
                actual.append(gates(obj)[:, 0].copy())
                expected.append(np.asarray(reference.relaxation(initial, voltage, name, right)))
                opened.append(float(np.asarray(obj.P)[0]))
            actual, expected, opened = np.stack(actual), np.stack(expected), np.asarray(opened)
            error = float(np.max(np.abs(actual - expected)))
            errors.append(error)
            stem = f"native-auxiliary-{name}-{trial}-{refinement}"
            np.savez_compressed(
                output / (stem + ".npz"),
                times_s=clock,
                gates=actual,
                expected_continuous=expected,
                opening=opened,
            )
            record = dict(
                status="captured",
                kind="native-auxiliary-relaxation-refinement",
                name=name,
                initial_gates=initial,
                voltage_V=voltage,
                duration_s=clock[-1],
                refinement=refinement,
                maximum_continuous_error=error,
                independent_auxiliary_preparation=True,
                arrays=stem + ".npz",
            )
            write(output / (stem + ".json"), record)
            assert np.isfinite(actual).all() and np.all((actual >= 0) & (actual <= 1))
            np.testing.assert_array_equal(opened, 1)
            assert clock[-1] == settings["duration_s"] == 12.0
            record["status"] = "passed"
            write(output / (stem + ".json"), record)
            summaries[str(refinement)] = record
        summary = dict(status="captured", name=name, trial=trial, errors=errors, traces=summaries)
        path = output / f"native-auxiliary-{name}-{trial}.json"
        write(path, summary)
        assert errors[2] < errors[1] < errors[0] and 0.40 < errors[2] / errors[1] < 0.65
        summary["status"] = "passed"
        write(path, summary)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = PROTOCOL["native_probe"]
    installed, checkout = Path(source["installed"]), Path(source["checkout"])
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = dict(status="capturing", revision=revision, files={})
    write(output / "source-manifest.json", manifest)
    assert revision == PROTOCOL["source_revision"]
    for relative, expected in PROTOCOL["source_files"].items():
        data = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(data).hexdigest(),
            checkout_match=data == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    version = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert version == PROTOCOL["source_version"]
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *_: None),
        __name__="pinned_leak_probe",
    )
    for filename in ("channelsabc.py", "vg_cl.py", "cation.py"):
        path = installed / "betse/science/channels" / filename
        nodes = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    manifest.update(version=version, classes=PROTOCOL["classes"], native_tissue_simulation=False)
    write(output / "source-manifest.json", manifest)
    voltage, p = np.asarray(source["voltage_V"]), SimpleNamespace(dt=source["update_dt_s"])
    cells = SimpleNamespace(mem_i=np.arange(voltage.size))
    target_cases = 0
    for name in PROTOCOL["classes"]:
        for label, target_input in source["target_scenarios"].items():
            target = None if target_input is None else np.asarray(target_input, np.int64)
            obj = namespace[name]()
            path = output / f"native-target-{name}-{label}.json"
            record = dict(
                status="prepared",
                kind="native-target-and-clock-source-evidence",
                name=name,
                target_argument=target_input,
                voltage_V=voltage,
                dt_s=p.dt,
                duplicate_targets_are_not_physical_populations=True,
            )
            write(path, record)
            obj.init(voltage, cells, p, targets=target)
            indices = np.arange(voltage.size) if obj.targets is None else np.asarray(obj.targets)
            initial = np.stack(
                (np.linspace(0.2, 0.6, indices.size), np.linspace(0.7, 0.3, indices.size))
            )
            record.update(
                native_targets=None if obj.targets is None else np.asarray(obj.targets),
                native_initialized_gates=gates(obj),
                native_P_set_by_init=hasattr(obj, "P"),
                native_ions=obj.ions,
                native_relative_permeability=obj.rel_perm,
                time_unit=float(obj.time_unit),
                gate_powers=[float(obj._mpower), float(obj._hpower)],
                nominal_vrev_assigned=hasattr(obj, "vrev"),
                prepared_auxiliary_gates=initial,
            )
            obj.m, obj.h = initial[0].copy(), initial[1].copy()
            obj.v_corr = source["voltage_correction_mV"]
            with np.errstate(all="raise"):
                argument = run_argument(obj, voltage, p)
            actual = gates(obj)
            record.update(
                status="actual_captured",
                native_calculate_voltage_mV=argument,
                after_update=actual,
                native_global_opening=obj.P,
            )
            write(path, record)
            ordered = reference.ORDERED_PERMEABILITIES[name]
            assert obj.ions == [v[0] for v in ordered] and obj.rel_perm == [v[1] for v in ordered]
            assert obj.time_unit == 1.0 and obj._mpower == obj._hpower == 0
            assert not hasattr(obj, "vrev")
            np.testing.assert_array_equal(record["native_initialized_gates"], 1)
            expected = np.empty_like(initial)
            for i, index in enumerate(indices):
                expected[:, i] = reference.backward_euler(
                    initial[:, i].tolist(), float(voltage[index]), name, p.dt
                )
            np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-12)
            expected_global = np.zeros(voltage.size)
            expected_global[indices] = 1.0  # Native assignment; never add repeated targets.
            np.testing.assert_array_equal(obj.P, expected_global)
            expected_argument = voltage[indices] * 1000 + (obj.v_corr if name == "ClLeak" else 0.0)
            np.testing.assert_array_equal(argument, expected_argument)
            if label == "default":
                assert (obj.targets is None) == (name == "ClLeak")
            record["status"] = "passed"
            write(path, record)
            target_cases += 1
    for name in PROTOCOL["classes"]:
        auxiliary_recovery(namespace, name, output)
    manifest.update(
        status="passed",
        target_initialization_clock_cases=target_cases,
        auxiliary_recovery_groups=6,
        auxiliary_refinements=PROTOCOL["auxiliary_recovery"]["native_refinements"],
        auxiliary_duration_s=12.0,
        source_singular_failures=0,
    )
    write(output / "source-manifest.json", manifest)
    print(json.dumps(manifest | dict(files="captured separately")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as exc:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(exc).__name__, message=str(exc)))
        raise
